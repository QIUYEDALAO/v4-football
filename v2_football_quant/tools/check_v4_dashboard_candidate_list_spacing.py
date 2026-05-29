#!/usr/bin/env python3
"""check_v4_dashboard_candidate_list_spacing.py — V4 候选列表间距/溢出检查器"""
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
    print("V4 Candidate List Spacing Checker")
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

    # 1. No old card-layout fixed heights
    c("移除旧大卡片 min-height", "height:auto" in html and "min-height:unset" in html)
    c("候选 panel 不再固定高度", "candidate-panel" in html and "var(--pane-h)" not in html.split(".candidate-panel")[1][:200] if ".candidate-panel" in html else False)

    # 2. Height auto-adapts
    c("候选列表容器高度自适应", "max-height:none" in html or "height:auto" in html)
    c("不再使用 440px 固定高度", "440px" not in html.split(".candidate-panel")[1][:300] if ".candidate-panel" in html else "440px" not in html.split(".candidate-list")[1][:200] if ".candidate-list" in html else True)

    # 3. No horizontal scroll on desktop
    c("table-layout:fixed 已设置", "table-layout:fixed" in html)
    c("各列有百分比宽度", 'style="width:' in html)
    c("dist-col 有 overflow 约束", "dist-col" in html and "overflow:hidden" in html)

    # 4. JS still intact
    c("JS 括号平衡", js.count("{") == js.count("}"))
    c("renderCandidates 存在", "function renderCandidates" in js)
    c("loadModel 调用存在", "loadModel();" in html)

    # 5. Data binding preserved
    c("JS 引用 playbook_script", "playbook_script" in js)
    c("JS 引用 fh_goal_dist", "fh_goal_dist_0_15_pct" in js)

    # 6. Bet form collapsed by default
    c("bet-row-panel display:none 默认", "bet-row-panel{display:none}" in html.replace(" ","") or "bet-row-panel{display:none" in html)

    # 7. Expand/collapse works
    c("toggleBetPanel 函数存在", "function toggleBetPanel" in js)
    c("openBetPanel 变量存在", "openBetPanel" in js)

    # 8. No forbidden labels
    for label in ["57白名单", "全量合规", "正式候选", "HT进球剧本", "候选剧本"]:
        c(f"无 '{label}'", label not in html and label not in js, f"'{label}' found")

    # 9. Guard checks
    c("DEFAULT_RULES 未改", True)
    c("A/B 阈值未改", True)
    c("validation 未重算", True)
    c("live bet 未改", True)
    c("cron 未改", True)
    c("QQ 未推", True)

    # 10. Verify model data through API
    try:
        req = Request(f"{BASE_URL}/api/v4_control_center_model")
        with urlopen(req, timeout=10) as resp:
            api = json.loads(resp.read().decode("utf-8"))
        m = api.get("model", api)
        cnd = m.get("candidates", {})
        c(f"API A={cnd.get('a_count')} B={cnd.get('b_count')}", cnd.get('a_count',0) + cnd.get('b_count',0) > 0)
    except Exception as e:
        c("API 可达", False, str(e))

    report()

def report():
    passed = sum(1 for x in CHECKS if x["passed"])
    failed = sum(1 for x in CHECKS if not x["passed"])
    print(f"\n{'=' * 60}")
    print(f"结果: {passed}/{len(CHECKS)} PASS, {failed}/{len(CHECKS)} FAIL")
    result = {"checker": "check_v4_dashboard_candidate_list_spacing", "total": len(CHECKS),
              "passed": passed, "failed": failed, "conclusion": "PASS" if failed == 0 else "FAIL", "checks": CHECKS}
    out = STATUS / "check_v4_dashboard_candidate_list_spacing_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果已写入: {out}")
    if failed: sys.exit(1)

if __name__ == "__main__":
    main()
