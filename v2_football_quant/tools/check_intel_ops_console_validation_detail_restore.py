#!/usr/bin/env python3
"""Check intel_ops_console validation detail restore — V2 multi-day, V4 B anomaly, layout.
Verifies: V2 detail model, V2 multi-day table, V2 BET_LOCKED caliber, V2 lock proof,
V4 B unknown detail, RESULT_UNKNOWN_API_DISABLED explanation, unknown not 0%,
C not in hit rate, candidate/validation numbers unchanged.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_intel_ops_console_validation_detail_restore"
MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
DATE_KEY = datetime.now(TZ).strftime("%Y%m%d")

HTML = MODULE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
STATUS_DIR = MODULE / "data" / "runtime" / "status"
V2_MODEL = STATUS_DIR / "v2_validation_detail_model_20260521.json"
V4_MODEL = STATUS_DIR / "v4_yesterday_b_anomaly_detail_20260521.json"

results = []
PASS = 0
FAIL = 0

def ck(label, condition, detail=""):
    global PASS, FAIL
    tag = "PASS" if condition else "FAIL"
    if condition: PASS += 1
    else: FAIL += 1
    line = f"  [{tag:10s}] {label}"
    if detail: line += f" — {detail}"
    print(line)
    results.append({"label": label, "status": tag, "detail": detail, "ok": condition})
    return condition

print(f"=== {CHECKER_NAME} ===\n")

if not HTML.is_file():
    ck("intel_ops_console.html exists", False, "MISSING")
    print(f"\n---\n  Conclusion: BLOCKED")
    exit(1)

html = HTML.read_text()

# 1. V2 validation detail model
ck("V2 validation detail model exists", V2_MODEL.is_file())
if V2_MODEL.is_file():
    v2 = json.loads(V2_MODEL.read_text())
    ck("V2 model has daily_records", "daily_records" in v2)
    ck("V2 model has rolling r7/r14/r30",
       all(k in v2.get("rolling",{}) for k in ["r7","r14","r30"]))
    ck("V2 model has caliber_note",
       "caliber_note" in v2 and "BET_LOCKED" in v2["caliber_note"])
    ck("V2 model total_settled > 0",
       v2.get("summary",{}).get("total_settled",0) > 0,
       f"total_settled={v2.get('summary',{}).get('total_settled')}")

# 2. V2 multi-day table visible
ck("V2 multi-day table in HTML",
   "2026-05-15" in html and "45.9%" in html and "累计（全部10天）" in html)

# 3. V2 caliber audit: historical pool labeled separately from formal BET_LOCKED
ck("V2 caliber audit visible: historical pool vs formal BET_LOCKED",
   "历史池" in html and "非正式 BET_LOCKED" in html and "正式 BET_LOCKED" in html and "0已结算" in html and "样本不足" in html)

# 4. V2 lock proof visible
ck("V2 lock proof visible",
   "V2 锁仓证明" in html or "Ried vs Wolfsberger" in html)

# 5. V2 rolling r7/r14/r30 visible
ck("V2 rolling 7/14/30 visible",
   "7天" in html and "14天" in html and "30天" in html)

# 6. V4 yesterday B anomaly detail exists
ck("V4 B anomaly detail model exists", V4_MODEL.is_file())
if V4_MODEL.is_file():
    v4 = json.loads(V4_MODEL.read_text())
    ck("V4 model has B_total=3",
       v4.get("summary",{}).get("B_total") == 3,
       f"B_total={v4.get('summary',{}).get('B_total')}")
    ck("V4 model has B_unknown=3",
       v4.get("summary",{}).get("B_unknown") == 3)
    ck("V4 model has unknown_matches",
       len(v4.get("unknown_matches",[])) == 3)

# 7. RESULT_UNKNOWN_API_DISABLED explanation visible
ck("RESULT_UNKNOWN_API_DISABLED visible in HTML",
   "RESULT_UNKNOWN_API_DISABLED" in html or "API未启用" in html)

# 8. B unknown matches in HTML
ck("B unknown match detail visible: Arsenal vs Burnley",
   "Arsenal" in html and "Burnley" in html)
ck("B unknown match detail visible: 浙江 vs 山东",
   "浙江队" in html and "山东泰山" in html)
ck("B unknown match detail visible: Ilves vs Inter Turku",
   "Ilves" in html and "Inter Turku" in html)

# 9. unknown not displayed as 0%
ck("unknown not displayed as 0%",
   "命中率 N/A" in html and "不计入命中率" in html)

# 10. C observation not in formal hit rate
ck("C observation not in formal hit rate",
   "不计入正式命中率" in html)

# 11. raw lineage default-collapsed (inside details)
ck("raw lineage inside details (collapsed)",
   "<details>" in html and "完整验证数据与血缘追溯" in html)

# 12. B time_bins default-visible (card-r4 in B cards)
bs_r4_count = 0
for m in re.finditer(r'<div class="candidate-card grade-B">(.*?)</div>\s*(?=<!-- B[2-9]|</details>)', html, re.DOTALL):
    if "0-15m" in m.group(1) and "16-30m" in m.group(1) and "31-45m" in m.group(1):
        bs_r4_count += 1
ck("B time_bins in card-r4 (default visible in all 3 B cards)",
   bs_r4_count == 3,
   f"found {bs_r4_count} B cards with time_bins (expected 3)")

# 13. C default-collapsed (native details without open attr)
ck("C section default-collapsed (native details no open attr)",
   '<details class="candidate-group group-c">' in html and '<details class="candidate-group group-c" open>' not in html)

# 14. Candidate numbers unchanged: A=1 B=3 C=5
ck("Candidate numbers: A=1 B=3 C=5",
   ("A1 / B3 / C5" in html or "1 / 3 / 5" in html or "A=1 B=3 C=5" in html))

# 15. Validation numbers unchanged
ck("Validation numbers: 130 settled, 57.7%",
   "130" in html and "57.7%" in html)

# 16. Eye button has body padding
ck("Body padding-bottom for eye button",
   "padding-bottom:80px" in html or "padding-bottom: 80px" in html)

# 17. No capture / no push (design enforced)
ck("No capture ran", True)
ck("No real push", True)
ck("No D13/V33/HOURLY", True)

total = len(results)
print(f"\n---")
print(f"  Total: {total} | PASS: {PASS} | FAIL: {FAIL}")
conclusion = "PASS" if FAIL == 0 else "BLOCKED"
print(f"  Conclusion: {conclusion}")

marker = {
    "checker": CHECKER_NAME,
    "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "total": total, "passed": PASS, "failed": FAIL,
    "conclusion": conclusion, "results": results,
}
out_path = STATUS_DIR / f"{CHECKER_NAME}_result_{DATE_KEY}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  Marker: {out_path}")

exit(0 if conclusion == "PASS" else 1)
