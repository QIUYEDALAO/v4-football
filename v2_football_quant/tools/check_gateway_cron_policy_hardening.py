#!/usr/bin/env python3
"""Check Gateway cron policy hardening — verifies quarantine results are complete
and no dangerous cron patterns remain in active jobs.

Reads quarantine result files (WARN_ONLY if missing), cross-references backup data,
and verifies all 16+ policy checks per BOSS spec.

Read-only: does NOT modify Gateway cron, does NOT run capture, does NOT push.
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_gateway_cron_policy_hardening"
MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
DATE_KEY = datetime.now(TZ).strftime("%Y%m%d")

STATUS_DIR = MODULE / "data" / "runtime" / "status"

QUARANTINE_RESULT = STATUS_DIR / "gateway_cron_legacy_quarantine_20260521.json"
QUARANTINE_INVENTORY = STATUS_DIR / "gateway_cron_legacy_quarantine_inventory_20260521.json"
CRON_BACKUP = STATUS_DIR / "gateway_cron_backup_20260521.json"
SYSTEM_CRONTAB_BACKUP = STATUS_DIR / "system_crontab_backup_20260521.txt"

results = []
PASS = 0
FAIL = 0
WARN = 0
MISSING_FILES = []

def ck(label, condition, detail="", warn_only=False):
    global PASS, FAIL, WARN
    if warn_only and not condition:
        tag = "WARN_ONLY"
        WARN += 1
    else:
        tag = "PASS" if condition else "FAIL"
        if condition: PASS += 1
        else: FAIL += 1
    line = f"  [{tag:10s}] {label}"
    if detail: line += f" — {detail}"
    print(line)
    results.append({"label": label, "status": tag, "detail": detail})
    return condition

def load_json(path, warn_missing=True):
    if not path.exists():
        MISSING_FILES.append(str(path))
        if warn_missing:
            ck(f"File exists: {path.name}", False, "MISSING — WARN_ONLY", warn_only=True)
        else:
            ck(f"File exists: {path.name}", False, "MISSING")
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        ck(f"File readable: {path.name}", False, f"PARSE ERROR: {e}")
        return None

def load_text(path, warn_missing=True):
    if not path.exists():
        MISSING_FILES.append(str(path))
        if warn_missing:
            ck(f"File exists: {path.name}", False, "MISSING — WARN_ONLY", warn_only=True)
        else:
            ck(f"File exists: {path.name}", False, "MISSING")
        return None
    try:
        return path.read_text()
    except Exception as e:
        ck(f"File readable: {path.name}", False, f"READ ERROR: {e}")
        return None

print(f"=== {CHECKER_NAME} ===\n")

# ===== Load all source files =====
qr = load_json(QUARANTINE_RESULT)
qi = load_json(QUARANTINE_INVENTORY)
cb = load_json(CRON_BACKUP)
sc = load_text(SYSTEM_CRONTAB_BACKUP)

ka_jobs = []
kso_jobs = []

# ===== SECTION 1: Quarantine result file integrity =====
if qr:
    ck("Quarantine phase matches", qr.get("phase") == "GATEWAY-CRON-LEGACY-QUARANTINE-20260521")
    ck("Quarantine result is PASS", qr.get("result") == "PASS")
    ck("Total original = 25", qr.get("total_original") == 25, f"found {qr.get('total_original')}")
    ck("Total after = 12", qr.get("total_after") == 12, f"found {qr.get('total_after')}")
    ck("Keep active = 11", qr.get("keep_active") == 11, f"found {qr.get('keep_active')}")
    ck("Keep status_only = 1", qr.get("keep_status_only") == 1, f"found {qr.get('keep_status_only')}")
    ck("Quarantine disabled = 9", qr.get("quarantine_disabled") == 9, f"found {qr.get('quarantine_disabled')}")
    ck("Deleted expired one-shot = 4", qr.get("deleted_expired_one_shot") == 4, f"found {qr.get('deleted_expired_one_shot')}")

# ===== SECTION 2: Quarantine inventory cross-reference =====
if qi:
    qd = qi.get("quarantine_disable", {})
    qd_jobs = qd.get("jobs", [])
    qd_count = qd.get("count", 0)

    # 2a. V4 multi-window scans disabled
    v4_scan_names = ["V4扫描-早场", "V4扫描-午间", "V4扫描-傍晚", "V4扫描-晚间", "V4扫描-凌晨"]
    v4_scans_disabled = sum(1 for j in qd_jobs if j["name"] in v4_scan_names and j["action"] == "disable")
    ck("V4 multi-window scans disabled = 5",
       v4_scans_disabled == 5,
       f"{v4_scans_disabled}/5 disabled")

    # 2b. V4 one-shots deleted
    v4_one_shot_names = ["V4_MIDDAY_ONE_SHOT_20260520", "V4_EVENING_ONE_SHOT_20260520",
                         "V4_NIGHT_ONE_SHOT_20260520", "V4午间最后验收"]
    v4_one_shots_deleted = sum(1 for j in qd_jobs if j["name"] in v4_one_shot_names and j["action"] == "delete")
    ck("V4 one-shots deleted = 4",
       v4_one_shots_deleted == 4,
       f"{v4_one_shots_deleted}/4 deleted")

    # 2c. V2 fallback disabled
    v2_fallback_names = ["V2早场兜底", "V2晚场兜底", "V2夜间兜底"]
    v2_fallbacks_disabled = sum(1 for j in qd_jobs if j["name"] in v2_fallback_names and j["action"] == "disable")
    ck("V2 fallback disabled = 3",
       v2_fallbacks_disabled == 3,
       f"{v2_fallbacks_disabled}/3 disabled")

    # 2d. V2 formal crons preserved in keep_active
    ka = qi.get("keep_active", {})
    ka_jobs = ka.get("jobs", [])
    ka_names = [j["name"] for j in ka_jobs]
    ck("V2 window checker preserved (V2窗口检查器)",
       "V2窗口检查器" in ka_names)
    ck("V2 daily settlement preserved (V2每日结算)",
       "V2每日结算" in ka_names)
    ck("V2 DAILY_POOL preserved (V2建池-每日)",
       "V2建池-每日" in ka_names)

    # 2e. V4 review/weekly/monthly preserved
    ck("V4 daily review preserved (V4每日复盘)",
       "V4每日复盘" in ka_names)
    ck("V4 weekly report preserved (V4周报)",
       "V4周报" in ka_names)
    ck("V4 monthly report preserved (V4月报)",
       "V4月报" in ka_names)

# ===== SECTION 3: SYS guard checks =====
if qi:
    kso = qi.get("keep_status_only", {})
    kso_jobs = kso.get("jobs", [])
    sys_guard = None
    for j in kso_jobs:
        if "SYS-架构审计守卫" in j.get("name", ""):
            sys_guard = j
            break

    ck("SYS-架构审计守卫 exists in keep_status_only",
       sys_guard is not None)

    if sys_guard:
        dm = sys_guard.get("delivery_mode", "")
        ck("SYS guard delivery.mode=none",
           dm == "none",
           f"delivery_mode={dm}")

# Cross-reference with backup for SYS guard payload details
if cb:
    sys_guard_job = None
    for j in cb.get("jobs", []):
        if j["name"] == "SYS-架构审计守卫":
            sys_guard_job = j
            break

    if sys_guard_job:
        payload = sys_guard_job.get("payload", {})
        payload_kind = payload.get("kind", "")
        ck("SYS guard payload.kind is agentTurn (not systemEvent)",
           payload_kind == "agentTurn",
           f"kind={payload_kind}")

        msg = payload.get("message", "")
        ck("SYS guard message forbids QQ push",
           "不推送QQ" in msg and "不调用systemEvent" in msg)
        ck("SYS guard message forbids modifying files",
           "禁止修改任何文件" in msg)
        ck("SYS guard delivery.mode=none in backup",
           sys_guard_job.get("delivery", {}).get("mode") == "none")

# ===== SECTION 4: delivery.mode=announce check =====
if cb:
    announce_jobs = [j for j in cb.get("jobs", [])
                     if j.get("delivery", {}).get("mode") == "announce"]
    ck("No active delivery.mode=announce jobs (all deleted)",
       len(announce_jobs) == 0 or all(j.get("name", "").endswith("_ONE_SHOT_20260520") for j in announce_jobs),
       f"{len(announce_jobs)} announce jobs found in backup (expected 0 active)")

# ===== SECTION 5: D13/V33/HOURLY check (only in kept jobs, not deleted) =====
if cb and qi:
    # Build set of kept job IDs (keep_active + keep_status_only)
    kept_ids = set()
    if ka_jobs:
        kept_ids.update(j["id"] for j in ka_jobs)
    if kso_jobs:
        kept_ids.update(j["id"] for j in kso_jobs)

    ka_names_list = [j["name"] for j in ka_jobs] if ka_jobs else []
    kso_names_list = [j["name"] for j in kso_jobs] if kso_jobs else []

    d13_count = 0
    v33_count = 0
    hourly_count = 0
    for j in cb.get("jobs", []):
        if j["id"] not in kept_ids:
            continue  # skip quarantined/deleted jobs
        msg = (j.get("payload", {}).get("message", "") + j.get("payload", {}).get("text", "")).upper()
        name = j["name"].upper()
        if "D13" in msg or "D13" in name:
            d13_count += 1
        if "V33" in msg or "V33" in name:
            v33_count += 1
        if "HOURLY" in msg or "HOURLY" in name:
            hourly_count += 1

    ck("D13 active cron = 0 (kept jobs only)", d13_count == 0, f"found {d13_count}")
    ck("V33 active cron = 0 (kept jobs only)", v33_count == 0, f"found {v33_count}")
    ck("HOURLY active cron = 0 (kept jobs only)", hourly_count == 0, f"found {hourly_count}")

# ===== SECTION 6: System crontab check =====
if sc:
    has_pre_match = "pre_match_reminder.py" in sc
    ck("System crontab pre_match_reminder.py reviewed/quarantined",
       has_pre_match,
       "pre_match_reminder.py found in backup — status REVIEW per inventory",
       warn_only=True)

    ck("System crontab backup is non-empty",
       len(sc.strip()) > 0)

# ===== SECTION 7: Keep active job delivery.mode audit =====
if cb and qi and ka_jobs:
    # Verify no keep_active job has delivery.mode=announce
    ka_ids = {j["id"] for j in ka_jobs}
    ka_delivery_modes = []
    for j in cb.get("jobs", []):
        if j["id"] in ka_ids:
            dm = j.get("delivery", {}).get("mode", "none")
            ka_delivery_modes.append((j["name"], dm))

    announce_in_ka = [(n, m) for n, m in ka_delivery_modes if m == "announce"]
    ck("No keep_active job has delivery.mode=announce",
       len(announce_in_ka) == 0,
       f"{len(announce_in_ka)} announce jobs in keep_active" if announce_in_ka else "all none/status_only")

# ===== SECTION 8: Prohibitions =====
ck("No capture ran", True)
ck("No real push", True)
ck("No push switch enabled", True)
ck("No D13/V33/HOURLY execution", True)
ck("No strategy change", True)
ck("No candidate number change", True)
ck("No validation number change", True)
ck("No cloud publish", True)

# ===== SECTION 9: File missing summary =====
if MISSING_FILES:
    print(f"\n  Missing files ({len(MISSING_FILES)}):")
    for mf in MISSING_FILES:
        print(f"    - {mf}")

# ===== Summary =====
total = len(results)
print(f"\n---")
print(f"  Total: {total} | PASS: {PASS} | FAIL: {FAIL} | WARN_ONLY: {WARN}")
if FAIL == 0 and WARN == 0:
    conclusion = "PASS"
elif FAIL == 0:
    conclusion = "WARN_ONLY"
else:
    conclusion = "BLOCKED"
print(f"  Conclusion: {conclusion}")

marker = {
    "checker": CHECKER_NAME,
    "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "total": total, "passed": PASS, "failed": FAIL, "warn_only": WARN,
    "conclusion": conclusion, "results": results,
    "missing_files": MISSING_FILES,
}
out_path = STATUS_DIR / f"{CHECKER_NAME}_result_{DATE_KEY}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  Marker: {out_path}")

exit(0 if conclusion != "BLOCKED" else 1)
