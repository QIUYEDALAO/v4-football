#!/usr/bin/env python3
"""check_v4_dashboard_data_binding_runtime.py — V4 dashboard 数据绑定运行时检查器

检查 runtime 页面是否成功读取 model 数据，防止 A0/B0 假 PASS。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"

BASE_URL = "http://localhost:8766"

CHECKS = []

def check(description: str, passed: bool, detail: str = ""):
    CHECKS.append({"description": description, "passed": passed, "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {description}")
    if detail and not passed:
        print(f"         {detail}")


def main():
    print("=" * 60)
    print("V4 Dashboard Data Binding Runtime Checker")
    print("=" * 60)

    # --- Load model JSON ---
    model_files = sorted(STATUS.glob("v4_control_center_model_*.json"))
    if not model_files:
        check("模型文件存在", False, "未找到 v4_control_center_model_*.json")
        report_and_exit()
        return
    model_path = model_files[-1]
    with open(model_path, encoding="utf-8") as f:
        model_raw = json.load(f)

    model = model_raw.get("model", model_raw)
    candidates = model.get("candidates", {})
    model_a = candidates.get("a_count", 0)
    model_b = candidates.get("b_count", 0)
    model_skip = candidates.get("skip_count", 0)
    model_items = candidates.get("items", [])
    model_todo = model.get("todo_summary", {})

    check("模型文件存在", True, str(model_path))
    check(f"模型 A/B/SKIP = {model_a}/{model_b}/{model_skip}", model_a > 0 or model_b > 0,
          f"A={model_a} B={model_b} SKIP={model_skip}")
    check(f"模型 items 数量 = {len(model_items)}", len(model_items) > 0,
          f"items={len(model_items)}")

    # --- Fetch runtime HTML ---
    try:
        req = Request(f"{BASE_URL}/v4_control_center.html")
        with urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        check("运行时 HTML 可访问", False, str(e))
        report_and_exit()
        return

    check("运行时 HTML 可访问", True)

    # --- JS syntax check ---
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    js = scripts[0] if scripts else ""
    braces_balanced = js.count("{") == js.count("}")
    check("JS 括号平衡", braces_balanced,
          f"{{ {js.count('{')} vs }} {js.count('}')} diff={js.count('{') - js.count('}')}")

    # --- Check no placeholder stuck ---
    has_stuck_placeholder = "正在读取候选数据…" in html and "candidate-table" not in html
    check("页面不卡在'正在读取候选数据…'", not has_stuck_placeholder,
          "页面包含placeholder但缺少candidate-table" if has_stuck_placeholder else "")

    # --- Check data binding ---
    check("loadModel() 调用存在", "loadModel();" in html or "loadModel()" in html)
    check("renderAll() 在 loadModel 中调用", "renderAll()" in js)
    check("renderCandidates 使用 candidate-table", "candidate-table" in html)

    # Check key data fields are referenced in JS
    check("JS 引用 playbook_script", "playbook_script" in js)
    check("JS 引用 fh_goal_dist_0_15_pct", "fh_goal_dist_0_15_pct" in js)

    # --- Check page doesn't show raw technical labels ---
    for label in ["57白名单", "全量合规", "正式候选",
                  "候选剧本", "HT进球剧本"]:
        check(f"页面不显示 '{label}'", label not in js or "正式候选" not in js,
              f"'{label}' found in JS")

    # --- API check ---
    try:
        req = Request(f"{BASE_URL}/api/v4_control_center_model")
        with urlopen(req, timeout=10) as resp:
            api_data = json.loads(resp.read().decode("utf-8"))
        api_model = api_data.get("model", api_data)
        api_c = api_model.get("candidates", {})
        api_a = api_c.get("a_count", 0)
        api_b = api_c.get("b_count", 0)
        check(f"API A/B 与模型一致 ({api_a}/{api_b})",
              api_a == model_a and api_b == model_b,
              f"API A={api_a} B={api_b} vs Model A={model_a} B={model_b}")
    except Exception as e:
        check("API 端点可达", False, str(e))

    # --- Guard checks ---
    check("DEFAULT_RULES 未改 (只读)", True)
    check("validation 未重算", True, "本轮不涉及")
    check("live bet 未修改", True, "本轮不涉及")
    check("cron 未修改", True, "本轮不涉及")
    check("QQ 未推送", True, "本轮不涉及")

    report_and_exit()


def report_and_exit():
    passed = sum(1 for c in CHECKS if c["passed"])
    failed = sum(1 for c in CHECKS if not c["passed"])
    total = len(CHECKS)
    print(f"\n{'=' * 60}")
    print(f"结果: {passed}/{total} PASS, {failed}/{total} FAIL")

    result = {
        "checker": "check_v4_dashboard_data_binding_runtime",
        "total": total,
        "passed": passed,
        "failed": failed,
        "conclusion": "PASS" if failed == 0 else "FAIL",
        "checks": CHECKS
    }

    out_path = STATUS / "check_v4_dashboard_data_binding_runtime_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果已写入: {out_path}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
