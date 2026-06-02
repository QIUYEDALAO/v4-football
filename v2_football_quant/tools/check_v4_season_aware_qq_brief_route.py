#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
REPORT = ROOT / "data" / "daily_reports"
LOCAL_TZ = timezone(timedelta(hours=8))


def _ok(checks: list[dict], name: str, cond: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(cond), "detail": detail})


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _latest_candidate_date() -> str:
    files = sorted(STATUS.glob("v4_official_candidate_view_*.json"))
    if not files:
        return datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    return files[-1].stem.split("_")[-1]


def main() -> int:
    checks: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []

    brief_src = (ROOT / "engine" / "v4_openclaw_brief.py").read_text(encoding="utf-8")
    scan_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    notify_src = (ROOT / "tools" / "notify_cron_task_complete_qq.py").read_text(encoding="utf-8")

    _ok(checks, "season_aware_brief_builder_exists", "_build_brief_season_aware" in brief_src)
    if "_build_brief_season_aware" not in brief_src:
        blockers.append("missing_season_aware_brief_builder")

    _ok(checks, "build_brief_mode_aware", "production_grade_mode" in brief_src and "candidate_view_path" in brief_src)
    _ok(checks, "scan_calls_mode_aware_brief", "production_grade_mode=str(args.production_grade_mode" in scan_src)
    _ok(checks, "scan_push_marker_has_brief_sha", "brief_sha256" in scan_src and "sent_marker_path" in scan_src)
    _ok(checks, "legacy_brief_path_preserved", "_build_brief_legacy" in brief_src and "official_legacy" in brief_src)

    _ok(checks, "notify_cron_is_not_recommend_sender", "任务完成" in notify_src and "notify_cron_task_complete_qq" in notify_src)

    date = _latest_candidate_date()
    dryrun_tool = ROOT / "tools" / "run_v4_season_aware_qq_recommendation_dryrun.py"
    _ok(checks, "qq_recommendation_dryrun_tool_exists", dryrun_tool.exists(), str(dryrun_tool))
    if not dryrun_tool.exists():
        blockers.append("missing_dryrun_tool")
    else:
        p = subprocess.run(["python3", str(dryrun_tool), "--date", date], capture_output=True, text=True)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        _ok(checks, "qq_route_dryrun_exec", p.returncode == 0, out[-260:])
        if p.returncode != 0:
            blockers.append("dryrun_exec_failed")

    route_path = STATUS / f"v4_scan_midday_dryrun_{date}.json"
    route = _load(route_path, {})
    _ok(checks, "route_artifact_exists", route_path.exists(), str(route_path))
    if not route_path.exists():
        blockers.append("route_artifact_missing")

    brief_path = REPORT / f"v4_openclaw_brief_{date}.txt"
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""

    _ok(checks, "brief_path_generated", route.get("brief_path") == str(brief_path), str(route.get("brief_path")))
    _ok(checks, "brief_sha256_generated", bool(route.get("brief_sha256")))
    _ok(checks, "brief_contains_mode", "production_grade_mode=season_aware_rf" in brief_text)
    _ok(checks, "brief_contains_official_source", "official_grade_source=market_adjusted_shadow_grade" in brief_text)
    _ok(checks, "brief_has_A_title", "A级强推荐" in brief_text)
    _ok(checks, "brief_has_B_title", "B级达标推荐" in brief_text)
    _ok(checks, "brief_has_final_conclusion", "V4最终结论" in brief_text)

    # Main recommendation purity
    _ok(checks, "brief_main_no_C_reco", "C级上半场主推荐" not in brief_text)
    _ok(checks, "brief_main_no_SKIP_reco", "SKIP上半场主推荐" not in brief_text)
    _ok(checks, "brief_main_no_shadow_only", "shadow-only" not in brief_text.lower())
    _ok(checks, "brief_main_no_dryrun_only", "dryrun-only" not in brief_text.lower())

    _ok(checks, "route_real_send_false", (route.get("push_mode") or {}).get("real_send") is False)
    _ok(checks, "route_v4_qq_enabled_false", (route.get("push_mode") or {}).get("V4_QQ_ENABLED") is False)
    _ok(checks, "route_sent_marker_not_written", (route.get("markers") or {}).get("sent_marker_written") is False)
    _ok(checks, "duplicate_guard_present", "duplicate_sent_exists" in (route.get("route_guard") or {}))

    cv_path = STATUS / f"v4_official_candidate_view_{date}.json"
    cv = _load(cv_path, {})
    _ok(checks, "candidate_view_input_supported", cv_path.exists(), str(cv_path))
    _ok(checks, "official_ab_rendered", int(cv.get("A_count", 0) or 0) + int(cv.get("B_count", 0) or 0) == int(route.get("main_recommendation_count", 0) or 0))

    # Safety checks from existing guard
    guard_default = subprocess.run(["python3", str(ROOT / "tools" / "check_v4_production_default_rules_guard.py")], capture_output=True, text=True)
    _ok(checks, "default_rules_guard_pass", guard_default.returncode == 0, (guard_default.stdout + guard_default.stderr)[-220:])
    if guard_default.returncode != 0:
        blockers.append("default_rules_guard_failed")

    # Staging safety
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    staged_files = [x.strip() for x in staged.stdout.splitlines() if x.strip()]
    runtime_hit = [x for x in staged_files if x.startswith("v2_football_quant/data/runtime/")]
    pending_hit = [x for x in staged_files if "pending" in x.lower()]
    marker_hit = [x for x in staged_files if "scan_" in x.lower() and "push_" in x.lower()]
    secret_hit = [x for x in staged_files if any(t in x.lower() for t in [".env", "secret", "token", "apikey", "api_key"])]
    _ok(checks, "runtime_artifacts_not_staged", len(runtime_hit) == 0, ",".join(runtime_hit))
    _ok(checks, "pending_runtime_not_staged", len(pending_hit) == 0, ",".join(pending_hit))
    _ok(checks, "qq_marker_not_staged", len(marker_hit) == 0, ",".join(marker_hit))
    _ok(checks, "no_secrets_staged", len(secret_hit) == 0, ",".join(secret_hit))
    if runtime_hit:
        blockers.append("runtime_staged")
    if pending_hit:
        blockers.append("pending_staged")
    if marker_hit:
        blockers.append("qq_marker_staged")
    if secret_hit:
        blockers.append("secrets_staged")

    out = {
        "checker": "check_v4_season_aware_qq_brief_route",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "date": date,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    STATUS.mkdir(parents=True, exist_ok=True)
    out_path = STATUS / f"check_v4_season_aware_qq_brief_route_{date}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
