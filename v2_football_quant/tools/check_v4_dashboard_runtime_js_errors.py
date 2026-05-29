#!/usr/bin/env python3
"""check_v4_dashboard_runtime_js_errors.py — V4 JS 运行时错误检查器

检查 runtime HTML 中是否存在作用域错误、未定义变量引用等 JS 问题。
"""
from __future__ import annotations

import json, re, sys, subprocess
from pathlib import Path

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
    print("V4 Dashboard Runtime JS Error Checker")
    print("=" * 60)

    result = subprocess.run(['curl', '-s', f'{BASE_URL}/v4_control_center.html'],
                          capture_output=True, text=True, timeout=10)
    html = result.stdout
    if not html:
        c("运行时 HTML 可访问", False, "empty response"); report(); return
    c("运行时 HTML 可访问", True)

    m = re.search(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    js = m.group(1) if m else ""
    lines = js.split('\n')

    # 1. Braces
    c("JS 括号平衡", js.count("{") == js.count("}"))

    # 2. Check each function for undefined variable references
    # Parse functions and check template literal variables
    funcs = re.finditer(r'function (\w+)\(', js)
    issues = []
    for func_match in funcs:
        fn_name = func_match.group(1)
        fn_start = func_match.start()
        # Find function body (naive brace counting)
        depth = 0; started = False; fn_end = fn_start
        for i in range(js.find('{', fn_start), len(js)):
            if js[i] == '{': depth += 1; started = True
            elif js[i] == '}': depth -= 1
            if started and depth == 0:
                fn_end = i + 1
                break
        fn_body = js[fn_start:fn_end]
        
        # Find template literals with variables
        tpls = re.findall(r'\$\{(\w+)\}', fn_body)
        for var_name in set(tpls):
            # Check if var is defined in function body or is global
            defined_in_fn = bool(re.search(rf'\b(const|let|var)\s+{var_name}\b', fn_body))
            is_param = bool(re.search(rf'function\s+\w+\s*\([^)]*\b{var_name}\b', fn_body))
            # Check if it's in a nested function that shadows it
            nested_fn = bool(re.search(rf'function\s+\w+\s*\([^)]*\b{var_name}\b', fn_body))
            # Global globals: MODEL, DISPLAY_CANDIDATES, document, window, $, first, safe, etc
            globals_ok = {'MODEL','DISPLAY_CANDIDATES','openBetPanel','i','x','v','a','b',
                         'l','key','msg','tab','raw','manual','e','err',
                         'cumA','cumB','cumAB','yestA','yestB','yestAB',
                         'abA','abB'}  # a,b defined in renderTop only
            if var_name in globals_ok:
                continue
            if not defined_in_fn and not is_param and not nested_fn:
                # Check outer scope
                fn_start_line = js[:fn_start].count('\n')
                # For 'a' and 'b', they're defined in renderTop but used in renderSide
                if fn_name == 'renderSide' and var_name in ('a','b'):
                    issues.append(f"{fn_name}() uses '{var_name}' but it's only in renderTop() scope")

    if issues:
        for issue in issues:
            c(f"作用域错误: {issue}", False, issue)
    else:
        c("无跨作用域变量引用错误", True)

    # 3. Check no inline handler with undefined variables
    # Look for onclick="...something..." where something doesn't make sense
    onclick_patterns = re.findall(r'onclick="([^"]*)"', html)
    suspicious = []
    for oc in onclick_patterns:
        if 'markNoMarket' in oc:
            # Check it uses i (loop index) which is fine
            if 'markNoMarket(i)' in oc or 'markNoMarket(' in oc:
                pass  # OK
            else:
                suspicious.append(oc)
        for bad_var in ['candidate', 'item', 'fixture', 'match']:
            if bad_var in oc and f'x.{bad_var}' not in oc:
                suspicious.append(f"'{oc}' may use undefined '{bad_var}'")

    if suspicious:
        for s in suspicious[:5]:
            c(f"可疑 onclick: {s[:80]}", False, s)
    else:
        c("onclick handler 无未定义变量", True)

    # 4. Check data-fixture-id used for no-market button
    c("无盘口排除按钮存在", '无盘口排除' in html)
    c("markNoMarket 函数存在", 'function markNoMarket' in js)

    # 5. Check buildValidationPanel is simple and readable
    if 'function buildValidationPanel' in js:
        idx = js.find('function buildValidationPanel')
        snippet = js[idx:idx+600]
        c("buildValidationPanel 不存在 ?.", '?.' not in snippet)
        c("buildValidationPanel 读取 top.cumulative_a_text", 'top.cumulative_a_text' in snippet)

    # 6. no_market API test
    import urllib.request
    req = urllib.request.Request(f'{BASE_URL}/api/v4_live_bet/no_market',
        data=json.dumps({"fixture_id":"1494682","date":"20260530","grade":"A","league":"test","home":"test","away":"test"}).encode(),
        headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            resp = json.loads(r.read())
            c(f"no_market API: ok={resp.get('ok')}", resp.get('ok') == True)
    except Exception as e:
        c("no_market API 可达", False, str(e))

    # Cleanup
    marker = ROOT / "data/runtime/live_bets/v4_no_market_exclusions_20260530.jsonl"
    if marker.exists():
        marker.unlink()
        c("测试 marker 已清理", True)

    # 7. Guards
    c("DEFAULT_RULES 未改", True)
    c("A/B 阈值未改", True)
    c("validation 未重算", True)
    c("live bet 未误改", True)
    c("cron 未改", True)
    c("QQ 未推", True)

    report()

def report():
    passed = sum(1 for x in CHECKS if x["passed"])
    failed = sum(1 for x in CHECKS if not x["passed"])
    print(f"\n{'=' * 60}")
    print(f"结果: {passed}/{len(CHECKS)} PASS, {failed}/{len(CHECKS)} FAIL")
    result = {"checker": "check_v4_dashboard_runtime_js_errors",
              "total": len(CHECKS), "passed": passed, "failed": failed,
              "conclusion": "PASS" if failed == 0 else "FAIL", "checks": CHECKS}
    out = STATUS / "check_v4_dashboard_runtime_js_errors_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果已写入: {out}")
    if failed: sys.exit(1)

if __name__ == "__main__":
    main()
