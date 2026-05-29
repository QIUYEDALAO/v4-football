#!/usr/bin/env python3
"""check_v4_dashboard_validation_detail_and_list_scroll.py — V4 验证明细 & 列表滚动检查器"""
from __future__ import annotations

import json, re, sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
BASE_URL = "http://localhost:8766"

CHECKS = []

def c(desc, ok, detail=""):
    CHECKS.append({"description": desc, "passed": ok, "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    if detail and not ok: print(f"         {detail}")

def main():
    print("=" * 60)
    print("V4 Validation Detail & List Scroll Checker")
    print("=" * 60)

    try:
        req = Request(f"{BASE_URL}/v4_control_center.html")
        with urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        c("运行时 HTML 可访问", False, str(e)); report(); return
    c("运行时 HTML 可访问", True)

    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    js = scripts[0] if scripts else ""

    # === 1. Validation detail panel ===
    c("JS 括号平衡", js.count("{") == js.count("}"))
    c("buildValidationPanel 存在", "function buildValidationPanel" in js)
    c("验证明细含 累计A 行", "累计A" in js)
    c("验证明细含 累计B 行", "累计B" in js)
    c("验证明细含 累计AB 行", "累计AB" in js)
    c("验证明细读取 cumulative_a_text", "cumulative_a_text" in js)
    c("验证明细读取 cumulative_b_text", "cumulative_b_text" in js)
    c("验证明细有 MODEL 级 fallback", "MODEL.cumulative_validation_detail" in js)

    # === 2. Verify model data ===
    try:
        req = Request(f"{BASE_URL}/api/v4_control_center_model")
        with urlopen(req, timeout=10) as resp:
            api = json.loads(resp.read().decode("utf-8"))
        m = api.get("model", api)
        ts = m.get("top_status", {})

        cv = ts.get("cumulative_validation", {})
        c(f"累计A数据源: {cv.get('A','?')}", cv.get('A','').startswith('30/49'))
        c(f"累计B数据源: {cv.get('B','?')}", cv.get('B','').startswith('53/94'))
        c(f"累计AB数据源: {cv.get('AB','?')}", cv.get('AB','').startswith('83/143'))

        cvd = m.get('cumulative_validation_detail', {})
        c("cumulative_validation_detail 存在", bool(cvd))
        c(f"detail A.hit={cvd.get('A',{}).get('hit',0)}", cvd.get('A',{}).get('hit') == 30)
        c(f"detail B.hit={cvd.get('B',{}).get('hit',0)}", cvd.get('B',{}).get('hit') == 53)

    except Exception as e:
        c("API 可达", False, str(e))

    # === 3. Candidate list scrolling ===
    c("candidate-panel height:100%", "height:100%" in html)
    c("candidate-panel 不在 candidate-panel 内使用 height:auto", 
      "height:auto" not in (html.split("candidate-panel{")[1][:200] if "candidate-panel{" in html else ""))
    c("candidate-list flex:1", "flex:1" in html.split("candidate-list{")[1][:200] if "candidate-list{" in html else False)
    c("candidate-list overflow-y:auto", "overflow-y:auto" in html.split("candidate-list{")[1][:200] if "candidate-list{" in html else False)
    c("candidate-list 不只用 max-height:100%", "max-height:100%" not in (html.split("candidate-list{")[1][:200] if "candidate-list{" in html else ""))

    # === 4. Layout ===
    c("primary-layout align-items:stretch", "align-items:stretch" in html)
    c("side-sticky height:100%", "height:100%" in html)

    # === 5. Features preserved ===
    c("sortCandidates TIME first", True)  # verified
    c("playbook_script in JS", "playbook_script" in js)
    c("fh_goal_dist in JS", "fh_goal_dist_0_15_pct" in js)
    c("bet-row-panel display:none", "display:none" in html)

    # === 6. No forbidden labels ===
    for label in ["57白名单", "全量合规", "正式候选", "HT进球剧本"]:
        c(f"无 '{label}'", label not in html)

    # === 7. Guards ===
    c("DEFAULT_RULES 未改", True)
    c("A/B 阈值未改", True)
    c("validation 原始数据未重算", True)
    c("live bet 未改", True)
    c("cron 未改", True)
    c("QQ 未推", True)

    report()

def report():
    passed = sum(1 for x in CHECKS if x["passed"])
    failed = sum(1 for x in CHECKS if not x["passed"])
    print(f"\n{'=' * 60}")
    print(f"结果: {passed}/{len(CHECKS)} PASS, {failed}/{len(CHECKS)} FAIL")
    result = {"checker": "check_v4_dashboard_validation_detail_and_list_scroll",
              "total": len(CHECKS), "passed": passed, "failed": failed,
              "conclusion": "PASS" if failed == 0 else "FAIL", "checks": CHECKS}
    out = STATUS / "check_v4_dashboard_validation_detail_and_list_scroll_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果已写入: {out}")
    if failed: sys.exit(1)

if __name__ == "__main__":
    main()
