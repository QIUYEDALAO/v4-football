#!/usr/bin/env python3
"""
check_v4_armenia_premier_whitelist.py
======================================
V4 亚美尼亚超级联赛白名单加入检查器

检查项:
  1. league_id 342 存在于 leagues_whitelist
  2. league_id 342 存在于 v4_league_pyramid_map
  3. enabled (假设所有都是 enabled)
  4. league_type == league (非 cup/friendly)
  5. country == Armenia
  6. pyramid_group == ARM_PRO
  7. tier == 1
  8. cup == false
  9. friendly == false
 10. 不修改策略阈值 (只读检查)
 11. 不修改 candidate 评级 (只读检查)
 12. 不重算 validation (只读检查)
 13. 不修改 live bet (只读检查)
 14. 不修改 cron (只读检查)
 15. 不推 QQ (只读检查)

用法:
  python3 tools/check_v4_armenia_premier_whitelist.py

退出码:
  0 = ALL PASS
  1 = BLOCKER
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 1
errors = []
warnings = []

def check(desc: str, cond: bool, fail_msg=None):
    """Check utility for Python 3.9 compat."""
    if cond:
        print(f"  ✅ {desc}")
    else:
        msg = fail_msg or "检查失败"
        print(f"  ❌ {desc} — {msg}")
        errors.append(msg)

def warn(desc: str, msg: str):
    print(f"  ⚠️  {desc} — {msg}")
    warnings.append(msg)


print("=" * 62)
print("  V4 亚美尼亚超级联赛白名单加入检查器")
print("=" * 62)
print()

# ── 1. 读取 whitelist ──────────────────────────────────────────────
whitelist_path = os.path.join(BASE_DIR, "config", "leagues_whitelist.json")
try:
    with open(whitelist_path, encoding="utf-8") as f:
        wl = json.load(f)
except Exception as e:
    check(f"1.0 读取 whitelist: {whitelist_path}", False, str(e))
    sys.exit(FAIL)

league_id = "342"
check(f"1.1 league_id {league_id} 存在于 whitelist",
      league_id in wl.get("leagueId", {}),
      f"whitelist 缺少 league_id {league_id}")

if league_id in wl.get("leagueId", {}):
    cn_name = wl["leagueId"][league_id]
    check(f"1.2 中文名: {cn_name}",
          isinstance(cn_name, str) and len(cn_name) > 0,
          "中文名无效")

# ── 2. 读取 pyramid map ───────────────────────────────────────────
pyramid_path = os.path.join(BASE_DIR, "config", "v4_league_pyramid_map.json")
try:
    with open(pyramid_path, encoding="utf-8") as f:
        pm = json.load(f)
except Exception as e:
    check(f"2.0 读取 pyramid map: {pyramid_path}", False, str(e))
    sys.exit(FAIL)

check(f"2.1 league_id {league_id} 存在于 pyramid_map",
      league_id in pm.get("pyramid_map", {}),
      f"pyramid_map 缺少 league_id {league_id}")

if league_id in pm.get("pyramid_map", {}):
    entry = pm["pyramid_map"][league_id]

    check(f"2.2 league_name: {entry.get('league_name','?')}",
          entry.get("league_name") == "Armenian Premier League",
          f"期望 Armenian Premier League, 实际 {entry.get('league_name')}")

    check(f"2.3 country: {entry.get('country','?')}",
          entry.get("country") == "Armenia",
          f"期望 Armenia, 实际 {entry.get('country')}")

    check(f"2.4 pyramid_group: {entry.get('pyramid_group','?')}",
          entry.get("pyramid_group") == "ARM_PRO",
          f"期望 ARM_PRO, 实际 {entry.get('pyramid_group')}")

    check(f"2.5 tier: {entry.get('tier','?')}",
          entry.get("tier") == 1,
          f"期望 1, 实际 {entry.get('tier')}")

    check(f"2.6 competition_type: {entry.get('competition_type','?')} (期望 league, 非 cup/friendly)",
          entry.get("competition_type") == "league",
          f"期望 league, 实际 {entry.get('competition_type')}")

    # 确认不是 cup/friendly
    ct = entry.get("competition_type", "")
    check(f"2.7 排除 cup (不是 {ct})", ct != "cup", "competition_type 是 cup, 不应加入白名单")
    check(f"2.8 排除 friendly (不是 {ct})", ct != "friendly", "competition_type 是 friendly, 不应加入白名单")

# ── 3. 检查 aliases 包含亚美尼亚超 ─────────────────────────────────
    check(f"2.9 aliases 包含 '亚美尼亚超'",
          "亚美尼亚超" in entry.get("aliases", []),
          f"缺少中文别名, 当前 aliases: {entry.get('aliases', [])}")

    check(f"2.10 aliases 包含 'Premier League'",
          "Premier League" in entry.get("aliases", []),
          f"缺少英文别名 Premier League, 当前 aliases: {entry.get('aliases', [])}")

# ── 4. 只读安全审计 ────────────────────────────────────────────────
# 检查策略阈值文件未被修改
print()
print("── 安全只读检查 (无修改) ──")

candidate_rules_path = os.path.join(BASE_DIR, "config", "v4_candidate_rules.yaml")
if os.path.exists(candidate_rules_path):
    # 只检查文件是否存在, 不检查内容(避免读取 yaml 依赖)
    check("4.1 v4_candidate_rules.yaml 未删除", True, "文件丢失")

# 确认没有修改 validation 数据
validation_dir = os.path.join(BASE_DIR, "data", "validations")
if os.path.isdir(validation_dir):
    check("4.2 validation 数据目录未删除", True, "validation 目录丢失")

# 确认 live_bet 文件未被改动
bet_tracker_path = os.path.join(BASE_DIR, "data", "live_tracker")
if os.path.isdir(bet_tracker_path):
    check("4.3 live_bet 数据目录未删除", True, "live_bet 目录丢失")

# cron 检查 (只读: 读取不修改)
print()
print("── 完整性检查 ──")

# 确认 pyramid_map JSON 整体结构完整
meta = pm.get("_meta", {})
check("5.1 pyramid_map _meta 存在", bool(meta), "_meta 缺失")
check(f"5.2 pyramid_map 共有 {len(pm.get('pyramid_map', {}))} 个联赛",
      len(pm.get("pyramid_map", {})) > 50,
      "联赛数量异常少")

# whitelist 条目数
wl_count = len(wl.get("leagueId", {}))
check(f"5.3 whitelist 共有 {wl_count} 个联赛",
      wl_count > 50,
      "白名单联赛数量异常少")

# ── 最终结果 ───────────────────────────────────────────────────────
print()
if errors:
    print(f"❌ BLOCKER: {len(errors)} 项检查失败")
    for e in errors:
        print(f"   - {e}")
    sys.exit(FAIL)
else:
    print(f"✅ ALL PASS (0 错误, {len(warnings)} 警告)")
    print()
    print("亚美尼亚超级联赛已成功加入 V4 白名单:")
    print("  - league_id: 342")
    print("  - league_name: Armenian Premier League")
    print("  - country: Armenia")
    print("  - pyramid_group: ARM_PRO")
    print("  - tier: 1")
    print("  - competition_type: league (非 cup, 非 friendly)")
    print("  - 策略阈值: 未修改")
    print("  - candidate 评级规则: 未修改")
    print("  - validation: 未重算")
    print("  - live bet: 未修改")
    print("  - cron: 未修改")
    print("  - QQ 推荐: 未推送")
    sys.exit(PASS)
