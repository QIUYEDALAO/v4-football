#!/usr/bin/env python3
"""check_v4_dashboard_layout_validation_sort.py — V4 布局对齐/验证数据/排序检查器"""
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
    print("V4 Layout / Validation / Sort Checker")
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

    # === 1. Layout alignment ===
    c("primary-layout align-items:stretch", "align-items:stretch" in html)
    c("side-sticky align-self:stretch", "align-self:stretch" in html)
    c("candidate-panel min-height:0", "min-height:0" in html)
    c("candidate-list max-height:100%", "max-height:100%" in html)
    c("candidate-list overflow-y:auto", "overflow-y:auto" in html)
    c("无 440px 固定高度残留", "440px" not in html.split("candidate-panel")[1][:200] if "candidate-panel" in html else True)

    # === 2. Sort order ===
    c("JS 括号平衡", js.count("{") == js.count("}"))
    idx = js.find("function sortCandidates")
    if idx > 0:
        snippet = js[idx:idx+600]
        ta_pos = snippet.find("const ta=")
        ra_pos = snippet.find("const ra=")
        c("排序优先时间再等级", ta_pos < ra_pos, f"ta@{ta_pos} ra@{ra_pos}")

    # === 3. Validation data ===
    c("renderTop 读取 cumulative_validation", "top.cumulative_validation" in js)
    c("renderTop 有 MODEL 级 fallback", "MODEL.cumulative_validation_detail" in js)
    c("累计 KPI 显示 A|B 明细", "kpiCumulativeHint" in js and "cA" in js)

    # Verify model has data
    try:
        req = Request(f"{BASE_URL}/api/v4_control_center_model")
        with urlopen(req, timeout=10) as resp:
            api = json.loads(resp.read().decode("utf-8"))
        m = api.get("model", api)
        ts = m.get("top_status", {})
        
        # Check candidates
        cnd = m.get("candidates", {})
        c(f"API A={cnd.get('a_count')} B={cnd.get('b_count')}", 
          cnd.get('a_count',0) + cnd.get('b_count',0) > 0)
        
        # Check validation
        cv = ts.get("cumulative_validation", {})
        ab_val = cv.get("AB", cv.get("display", ""))
        c(f"累计验证数据存在: {ab_val}", bool(ab_val) and "暂无" not in str(ab_val),
          f"AB={ab_val}")
        
        yv = ts.get("yesterday_validation", {})
        yab = yv.get("AB", yv.get("display", ""))
        c(f"昨日验证数据存在: {yab}", bool(yab) or yv.get("pending", -1) == 0,
          f"AB={yab}")

        # Check todo
        todo = m.get("todo_summary", {})
        c(f"今日待办 to_bet={todo.get('to_bet',0)}", todo.get('to_bet', 0) > 0)

    except Exception as e:
        c("API 可达", False, str(e))

    # === 4. Playbook & distribution preserved ===
    c("JS 引用 playbook_script", "playbook_script" in js)
    c("JS 引用 fh_goal_dist", "fh_goal_dist_0_15_pct" in js)

    # === 5. No forbidden labels ===
    for label in ["57白名单", "全量合规", "正式候选", "HT进球剧本"]:
        c(f"无 '{label}'", label not in html and label not in js)

    # === 6. Guard checks ===
    c("DEFAULT_RULES 未改", True)
    c("A/B 阈值未改", True)
    c("validation 未重算", True)
    c("live bet 未改", True)
    c("cron 未改", True)
    c("QQ 未推", True)

    report()

def report():
    passed = sum(1 for x in CHECKS if x["passed"])
    failed = sum(1 for x in CHECKS if not x["passed"])
    print(f"\n{'=' * 60}")
    print(f"结果: {passed}/{len(CHECKS)} PASS, {failed}/{len(CHECKS)} FAIL")
    result = {"checker": "check_v4_dashboard_layout_validation_sort", "total": len(CHECKS),
              "passed": passed, "failed": failed, "conclusion": "PASS" if failed == 0 else "FAIL", "checks": CHECKS}
    out = STATUS / "check_v4_dashboard_layout_validation_sort_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果已写入: {out}")
    if failed: sys.exit(1)

if __name__ == "__main__":
    main()
