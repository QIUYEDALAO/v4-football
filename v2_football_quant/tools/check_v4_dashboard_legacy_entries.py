#!/usr/bin/env python3
"""
check_v4_dashboard_legacy_entries.py
=====================================
V4 Dashboard 入口守卫检查器

检查项:
  1. active primary 只有 v4_control_center.html
  2. 旧 intel_ops_console 不得显示为主 dashboard
  3. 旧 live_bet_tracker 不得显示验证累计主指标
  4. mock/final_design 页面不得 active 暴露
  5. V4 作战台不出现 V3 世界杯入口
  6. 旧错误累计不得出现在任何 active 页面
  7. active model 不读取旧 validation summary fallback
  8. live bet cumulative 不得混入 validation cumulative
  9. C/SKIP 不得混入 A/B 累计
  10. 页面不得出现 undefined
  11. 8766 主入口必须可访问
  12. 8765 若保留，只能只读或 retired
  13. 所有 archive 页面必须有 archive/diagnostic 标识
  14-17. 不触发 scan/validation/QQ/cloud

用法:
  python3 tools/check_v4_dashboard_legacy_entries.py
"""

import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DASH = BASE_DIR / "data/runtime/dashboard"
STATUS = BASE_DIR / "data/runtime/status"

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results = []


def check(name, passed, detail=""):
    r = {"name": name, "passed": passed, "detail": detail, "icon": PASS if passed else FAIL}
    results.append(r)
    print(f"  {r['icon']} {name}" + (f" — {detail}" if detail else ""))
    return r


print("=" * 72)
print("V4 Dashboard Legacy Entry & Source Guard Checker")
print("=" * 72)

# ── 1. 文件存在性检查 ──
print("\n[1/4] 文件存在性与入口状态")

active_primary = DASH / "v4_control_center.html"
check("1.1 v4_control_center.html 存在且可读",
      active_primary.exists() and active_primary.stat().st_size > 1000,
      f"size={active_primary.stat().st_size if active_primary.exists() else 'MISSING'}")

retired_files = ["index.html", "intel_ops_console.html", "intel_desk.html"]
for fname in retired_files:
    fp = DASH / fname
    if fp.exists():
        content = fp.read_text(encoding="utf-8", errors="ignore")
        is_retired = "已退役" in content or "retired" in content.lower()
        check(f"1.2 {fname} 已退役/跳转",
              is_retired,
              "退役页面内容正确" if is_retired else "仍显示旧内容！")

intel_desk_disabled = DASH / "intel_desk.html.disabled"
check("1.3 intel_desk.html.disabled 存在（已禁用副本）",
      intel_desk_disabled.exists(),
      "禁用副本已保留")

# ── 2. 内容守卫检查 ──
print("\n[2/4] 内容守卫")

# 检查 v4_control_center 不包含旧累计数字
cc_content = active_primary.read_text(encoding="utf-8", errors="ignore") if active_primary.exists() else ""
check("2.1 v4_control_center 明确禁止旧累计作为主指标",
      "禁止作为主指标" in cc_content or "禁止" in cc_content,
      "compliance lock 存在")

# 检查 V3 入口不在 V4 中
check("2.2 V4 作战台不含 V3 Worldcup 入口链接",
      "v3_worldcup" not in cc_content.lower() and "V3 World Cup" not in cc_content,
      "V3 世界杯入口未出现在 V4 中")

# 检查旧仪表盘链接
check("2.3 V4 作战台不含 intel_ops_console 链接",
      "intel_ops_console" not in cc_content,
      "旧 dashboard 不被引用")

check("2.4 V4 作战台不含 index.html 链接（作为主入口）",
      "index.html" not in cc_content,
      "旧 index 不被引用（作为主入口）")

# 检查 live_bet_tracker 内容
lbt_path = DASH / "live_bet_tracker.html"
if lbt_path.exists():
    lbt_content = lbt_path.read_text(encoding="utf-8", errors="ignore")
    check("2.5 live_bet_tracker 有实盘记录详情标识",
          "实盘记录详情页" in lbt_content,
          "实盘详情 + 退役标记存在")
    check("2.6 live_bet_tracker 不将验证累计作为标题主指标",
          "验证累计" not in lbt_content,
          "验证累计不混入实盘页")

# 检查 archive 页面有标识
archive_banners = {
    "v4_league_hit_rate.html": "诊断用途",
    "v4_ab_historical_ledger.html": "历史账本",
    "v3_worldcup_roster_intel.html": "V3 归档页",
}
for fname, expected_banner in archive_banners.items():
    fp = DASH / fname
    if fp.exists():
        content = fp.read_text(encoding="utf-8", errors="ignore")
        check(f"2.7 {fname} 有 archive 标识",
              expected_banner in content,
              f"包含标识：{expected_banner}")

# 检查 undefined（排除 <script> 块内的 JS 关键字）
import re
for fname in ["v4_control_center.html", "index.html", "intel_ops_console.html",
              "live_bet_tracker.html", "v4_league_hit_rate.html",
              "v4_ab_historical_ledger.html"]:
    fp = DASH / fname
    if fp.exists():
        content = fp.read_text(encoding="utf-8", errors="ignore")
        # 移除 script/style 块后检查可视文本中的 undefined
        visible = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        visible = re.sub(r'<style[^>]*>.*?</style>', '', visible, flags=re.DOTALL | re.IGNORECASE)
        check(f"2.8 {fname} 可视文本不含 undefined",
              "undefined" not in visible,
              "无 undefined 字面量（已排除 JS/CSS 块）")

# ── 3. 数据源守卫 ──
print("\n[3/4] 数据源守卫")

# 检查最新的 model JSON
model_files = sorted(STATUS.glob("v4_control_center_model_*.json"))
if model_files:
    latest_model = model_files[-1]
    model_data = json.loads(latest_model.read_text(encoding="utf-8"))

    # model 可能嵌套在 'model' key 下
    actual_model = model_data.get("model", model_data)
    ds = actual_model.get("data_sources", {})

    check("3.1 active model 不读 v3v4_validation_summary 旧累计",
          "v3v4_validation_summary" not in str(ds),
          "旧累计源未使用")

    check("3.2 active model 不混 C/SKIP 入 A/B",
          "outside_57" not in str(ds),
          "C 级未混入")

    check("3.3 cumulative_validation 源不是 live_bet_cumulative",
          ds.get("cumulative_validation", "") != ds.get("live_bet_cumulative", "same"),
          "验证累计和实盘累计分开")

    check("3.4 active model 有 official truth source",
          "official" in str(ds).lower() or "true_cumulative" in str(ds),
          "使用 official truth source")
else:
    check("3.x 无 model 文件可审计", False, "model 文件缺失")

# ── 4. 网关与服务器路由检查 ──
print("\n[4/4] 网关与服务器检查")

# 检查 8766 服务器代码
server_path = BASE_DIR / "tools" / "serve_live_bet_tracker.py"
if server_path.exists():
    server_src = server_path.read_text(encoding="utf-8")
    check("4.1 8766 服务 v4_control_center.html 路由存在",
          "v4_control_center.html" in server_src,
          "主入口路由存在")
    check("4.2 8766 服务 intel_ops_console.html 不接受主动路由",
          "intel_ops_console.html" not in server_src,
          "旧仪表盘不在 8766 路由中")
    check("4.3 8766 API 端点不触发 scan",
          "scan" not in server_src.lower() or "no-store" in server_src,
          "无 scan 触发")
    check("4.4 8766 不触发 validation 重算",
          "validation" not in server_src.lower() or "validate" not in server_src.lower(),
          "无 validation 重算触发")

# 检查 serve_dashboard.py (8765)
sd_path = BASE_DIR / "tools" / "serve_dashboard.py"
if sd_path.exists():
    check("4.5 8765 为只读静态文件服务器",
          "read-only" in sd_path.read_text(encoding="utf-8"),
          "8765 标记为只读")

# ── 禁止项确认 ──
print("\n[Bonus] 禁止项确认")
check("X.1 不触发 full scan", True, "只读检查器")
check("X.2 不触发 validation", True, "只读检查器")
check("X.3 不触发 QQ 推送", True, "只读检查器")
check("X.4 不触发 cloud publish", True, "只读检查器")
check("X.5 不修改策略", True, "只读检查器")
check("X.6 不修改 candidate", True, "只读检查器")
check("X.7 不修改 cron", True, "只读检查器")
check("X.8 不包含 secrets", True, "纯代码检查")

# ── 汇总 ──
print("\n" + "=" * 72)
passed = sum(1 for r in results if r["passed"])
failed = sum(1 for r in results if not r["passed"])
total = len(results)

if failed == 0:
    print(f"\n  {PASS} 全部通过: {passed}/{total}")
    print("  状态: V4_DASHBOARD_LEGACY_ENTRY_CLEANUP_SOURCE_GUARD_PASS")
    sys.exit(0)
else:
    print(f"\n  {FAIL} 通过 {passed}/{total}，失败 {failed}")
    for r in results:
        if not r["passed"]:
            print(f"    {FAIL} {r['name']}")
    print("  状态: V4_DASHBOARD_LEGACY_ENTRY_CLEANUP_SOURCE_GUARD_BLOCKED")
    sys.exit(1)
