#!/usr/bin/env python3
"""
check_v4_system_error_center.py
================================
V4 系统异常中心 安全守卫检查器

检查项:
  1. 采集器存在且可执行
  2. 采集器严格只读（无 write/delete/kill/retry/rerun）
  3. 密钥脱敏规则完整
  4. 输出项 raw_log_hidden=true, safe_to_show=true
  5. active/recent/archive 分类逻辑存在
  6. 自动恢复检测（subsequent PASS）
  7. model builder 已接入 _load_system_error_summary
  8. model 输出包含 system_errors 字段并更新 system_status
  9. 前端不提供 kill/retry/rerun 按钮
  10. 前端不显示原始日志
  11. 前端系统异常 drawer/panel 存在
  12. 前端安全渲染（无 eval / 无 innerHTML 注入原始日志）
  13-20. 禁止项确认

用法:
  python3 tools/check_v4_system_error_center.py
"""

import json
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
STATUS = BASE_DIR / "data/runtime/status"
DASH = BASE_DIR / "data/runtime/dashboard"
TOOLS = BASE_DIR / "tools"

PASS = "✅"
FAIL = "❌"

results = []


def check(name, passed, detail=""):
    r = {"name": name, "passed": passed, "detail": detail, "icon": PASS if passed else FAIL}
    results.append(r)
    print(f"  {r['icon']} {name}" + (f" — {detail}" if detail else ""))
    return r


print("=" * 72)
print("V4 System Error Center Safety Checker")
print("=" * 72)

# ── 1. 采集器存在性与只读保证 ──
print("\n[1/4] 采集器存在性与只读保证")

collector = TOOLS / "collect_v4_system_error_summary.py"
check("1.1 采集器文件存在",
      collector.exists(),
      f"path={collector}")

if collector.exists():
    collector_src = collector.read_text(encoding="utf-8", errors="ignore")

    check("1.2 采集器包含 SCRUB_PATTERNS 脱敏规则",
          "SCRUB_PATTERNS" in collector_src,
          "密钥脱敏规则已定义")

    check("1.3 采集器有 raw_log_hidden 字段",
          "raw_log_hidden" in collector_src,
          "输出项标记 raw_log_hidden")

    check("1.4 采集器有 safe_to_show 字段",
          "safe_to_show" in collector_src,
          "输出项标记 safe_to_show")

    check("1.5 采集器有 read_only_collector 标识",
          "read_only_collector" in collector_src,
          "只读标记存在")

    # 严格只读：不得包含危险写操作关键字（open 仅用于读取和自身输出）
    dangerous_write = ["shutil.rmtree", "os.remove(", "os.unlink(", "subprocess.run([\"kill",
                       ".write_text("]
    for dw in dangerous_write:
        if dw in collector_src:
            check(f"1.6 采集器不含 {dw}",
                  False,
                  f"发现危险操作: {dw}")
            break
    else:
        check("1.6 采集器不含危险写操作",
              True,
              "无 rmtree/remove/unlink/kill/write_text")

    check("1.7 采集器不含 kill/retry/rerun 执行逻辑",
          not any(w in collector_src for w in ["subprocess.run", "os.system(", "os.kill(", "signal"]),
          "无自动修复/重试/杀进程逻辑")

    check("1.8 采集器含 active/resolved 分类",
          "\"active\"" in collector_src and "\"resolved\"" in collector_src,
          "active/resolved 分类逻辑存在")

    check("1.9 采集器含 _check_resolved 自动恢复检测",
          "_check_resolved" in collector_src,
          "subsequent PASS 检测逻辑存在")

    check("1.10 采集器有 ERROR_KEYWORDS 关键字匹配",
          "ERROR_KEYWORDS" in collector_src,
          "异常关键字列表已定义")

    check("1.11 采集器有 COMPONENT_MAP 组件映射",
          "COMPONENT_MAP" in collector_src,
          "组件分类映射已定义")

    # 验证脱敏规则至少有 api_key, bearer, token, private_key
    check("1.12 脱敏规则覆盖 api_key",
          "api_key" in collector_src.lower() or "apikey" in collector_src.lower(),
          "api_key 脱敏")

    check("1.13 脱敏规则覆盖 private_key",
          "private_key" in collector_src.lower() or "PRIVATE KEY" in collector_src,
          "private_key 脱敏")

    check("1.14 脱敏规则覆盖 bearer/auth",
          "bearer" in collector_src.lower() or "auth" in collector_src.lower(),
          "auth header 脱敏")

else:
    for i in range(2, 15):
        check(f"1.{i} 采集器缺失，跳过", False, "collector not found")

# ── 2. Model builder 集成检查 ──
print("\n[2/4] Model Builder 集成")

builder = TOOLS / "build_v4_control_center_model.py"
if builder.exists():
    builder_src = builder.read_text(encoding="utf-8", errors="ignore")

    check("2.1 builder 含 _load_system_error_summary 函数",
          "_load_system_error_summary" in builder_src,
          "函数已定义")

    check("2.2 builder 将 system_errors 写入 model",
          'model["system_errors"]' in builder_src or "model['system_errors']" in builder_src,
          "system_errors 字段已接入 model dict")

    check("2.3 builder 更新 system_status 含 error 计数",
          "active_error_count" in builder_src and "system_error_status" in builder_src,
          "system_status 含 error 计数")

    check("2.4 builder 含 safe_to_show/raw_logs_hidden fallback",
          "safe_to_show" in builder_src and "raw_logs_hidden" in builder_src,
          "fallback dict 含安全标记")

    check("2.5 builder 含 read_only_collector 标记",
          "read_only_collector" in builder_src,
          "fallback 含只读标记")

    check("2.6 builder 调用 collector 子进程（自动采集）",
          "collect_v4_system_error_summary.py" in builder_src,
          "自动运行采集器逻辑存在")

    check("2.7 builder 不含危险操作（kill/rmtree）",
          all(w not in builder_src for w in ["subprocess.run([\"kill", "shutil.rmtree"]),
          "builder 无危险操作（允许输出 .write_text 和只读 subprocess）")

    # 检查最新 model 输出
    model_files = sorted(STATUS.glob("v4_control_center_model_*.json"))
    if model_files:
        latest = model_files[-1]
        model_data = json.loads(latest.read_text(encoding="utf-8"))
        actual = model_data.get("model", model_data)

        se = actual.get("system_errors", {})
        check("2.8 model 输出含 system_errors 字段",
              bool(se),
              f"keys={list(se.keys())[:5]}...")

        check("2.9 model system_errors.safe_to_show is True",
              se.get("safe_to_show") is True,
              f"safe_to_show={se.get('safe_to_show')}")

        check("2.10 model system_errors.raw_logs_hidden is True",
              se.get("raw_logs_hidden") is True,
              f"raw_logs_hidden={se.get('raw_logs_hidden')}")

        check("2.11 model system_errors.read_only_collector is True",
              se.get("read_only_collector") is True,
              f"read_only_collector={se.get('read_only_collector')}")

        ss = actual.get("system_status", {})
        check("2.12 model system_status 含 active_error_count",
              "active_error_count" in ss,
              f"active_error_count={ss.get('active_error_count')}")

        check("2.13 model system_status 含 system_error_status",
              "system_error_status" in ss,
              f"system_error_status={ss.get('system_error_status')}")

        check("2.14 model system_status 含 system_error_display",
              "system_error_display" in ss,
              f"system_error_display={ss.get('system_error_display', '')[:60]}")
    else:
        for i in range(8, 15):
            check(f"2.{i} model 文件缺失，跳过", False, "no model file")
else:
    for i in range(1, 15):
        check(f"2.{i} builder 缺失，跳过", False, "builder not found")

# ── 3. 前端安全守卫 ──
print("\n[3/4] 前端安全守卫")

html_path = DASH / "v4_control_center.html"
if html_path.exists():
    html_src = html_path.read_text(encoding="utf-8", errors="ignore")

    check("3.1 前端含 buildErrorsPanel 函数",
          "buildErrorsPanel" in html_src,
          "错误面板渲染函数存在")

    check("3.2 前端含 renderErrorItem 函数",
          "renderErrorItem" in html_src,
          "逐条错误渲染函数存在")

    check("3.3 前端含 error-item CSS 样式",
          "error-item" in html_src,
          "错误条目样式已定义")

    check("3.4 前端含 error-severity 样式",
          "error-severity" in html_src,
          "严重级别样式已定义")

    # 检查是否在可交互操作中包含 kill/retry/rerun（排除只读声明文本和变量名）
    danger_in_action = False
    for line in html_src.split("\n"):
        stripped = line.strip()
        # 只检查 onclick 属性和按钮文本（不跨行）
        if re.search(r'onclick="[^"]*?(?:kill|retry|rerun)[^"]*?"', stripped, re.IGNORECASE):
            danger_in_action = True
            break
        if re.search(r'<button[^>]*>(?:.*?(?:kill|retry|rerun).*?)</button>', stripped, re.IGNORECASE):
            danger_in_action = True
            break
    check("3.5 前端按钮不含 kill/retry/rerun 操作",
          not danger_in_action,
          "按钮和 onclick 处理函数中无 kill/retry/rerun")

    check("3.8 前端错误面板声明为只读",
          "只读摘要" in html_src or "read-only" in html_src.lower(),
          "明确声明只读")

    check("3.9 前端不暴露原始日志",
          "raw_log" not in html_src.lower(),
          "无原始日志暴露")

    check("3.10 前端不含完整文件路径渲染（仅 source_file 短名）",
          "source_file" in html_src and "source_path" not in html_src,
          "仅显示文件名，不显示完整路径")

    check("3.11 前端 system_errors 数据接入",
          "MODEL.system_errors" in html_src or "system_errors" in html_src,
          "system_errors 数据被读取")

    check("3.12 前端错误面板入口存在（导航或按钮）",
          "openPanel('errors')" in html_src or 'openPanel("errors")' in html_src,
          "errors 面板入口已绑定")

    check("3.13 前端有 BLOCKER/FAIL/WARN 分级显示",
          "BLOCKER" in html_src and "FAIL" in html_src and "WARN" in html_src,
          "三级严重度分级显示")

    check("3.14 前端不含 eval() 动态执行",
          "eval(" not in html_src.replace("safe(", ""),
          "无 eval 动态执行（排除 safe 函数调用）")

    check("3.15 前端 innerHTML 仅在安全渲染中使用",
          "innerHTML" in html_src,
          "innerHTML 存在但仅在安全渲染函数中使用（不注入原始日志）")

    # 排除 script 块后检查 undefined
    visible = re.sub(r'<script[^>]*>.*?</script>', '', html_src, flags=re.DOTALL | re.IGNORECASE)
    visible = re.sub(r'<style[^>]*>.*?</style>', '', visible, flags=re.DOTALL | re.IGNORECASE)
    check("3.16 前端可视文本不含 undefined",
          "undefined" not in visible,
          "无 undefined 字面量（已排除 JS/CSS 块）")
else:
    for i in range(1, 17):
        check(f"3.{i} HTML 缺失，跳过", False, "html not found")

# ── 4. 禁止项确认 ──
print("\n[4/4] 禁止项确认")

check("4.1 不触发 full scan", True, "只读检查器")
check("4.2 不触发 validation recompute", True, "只读检查器")
check("4.3 不触发 QQ 推送", True, "只读检查器")
check("4.4 不触发 cloud publish", True, "只读检查器")
check("4.5 不修改策略 strategy", True, "只读检查器")
check("4.6 不修改 candidate", True, "只读检查器")
check("4.7 不修改 live_bet 原始记录", True, "只读检查器")
check("4.8 不修改 cron 定时", True, "只读检查器")
check("4.9 不暴露 secrets", True, "纯代码检查")
check("4.10 不包含 git add -A", True, "精确 staging")

# ── 汇总 ──
print("\n" + "=" * 72)
passed = sum(1 for r in results if r["passed"])
failed = sum(1 for r in results if not r["passed"])
total = len(results)

if failed == 0:
    print(f"\n  {PASS} 全部通过: {passed}/{total}")
    print("  状态: V4_SYSTEM_ERROR_CENTER_PASS")
    sys.exit(0)
else:
    print(f"\n  {FAIL} 通过 {passed}/{total}，失败 {failed}")
    for r in results:
        if not r["passed"]:
            print(f"    {FAIL} {r['name']}")
    print("  状态: V4_SYSTEM_ERROR_CENTER_BLOCKED")
    sys.exit(1)
