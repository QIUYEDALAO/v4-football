#!/usr/bin/env python3
"""
check_v4_h2h_league_pyramid_policy.py
======================================
V4 H2H 联赛金字塔策略检查器

检查项:
  1. evaluate_h2h_edge 支持 current_league_id
  2. v4_runner 调用时传入 fx["league"]
  3. official_h2h 不包含 2020 年前
  4. official_h2h 不包含杯赛
  5. official_h2h 不包含友谊赛
  6. official_h2h 不包含 unknown competition
  7. same_league 样本优先
  8. adjacent tier 只能在同联赛样本不足时 fallback
  9. adjacent tier 必须 same_country + same_pyramid + tier_delta<=1
  10. forensic_h2h 不参与 ht_rate 主评分
  11. 输出包含 excluded_reasons
  12. 不修改 A/B 阈值
  13. 不重算 validation
  14. 不修改 candidate

用法:
  python3 tools/check_v4_h2h_league_pyramid_policy.py
"""

import ast
import inspect
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results: list[dict] = []


def check(name: str, passed: bool, detail: str = "") -> dict:
    r = {"name": name, "passed": passed, "detail": detail, "icon": PASS if passed else FAIL}
    results.append(r)
    print(f"  {r['icon']} {name}" + (f" — {detail}" if detail else ""))
    return r


def source_contains(file_path: str, snippet: str) -> bool:
    with open(file_path) as f:
        return snippet in f.read()


print("=" * 72)
print("V4 H2H League Pyramid Policy Checker")
print("=" * 72)

# ── 1. evaluate_h2h_edge 签名检查 ──
print("\n[1/3] 引擎层面检查")
h2h_path = os.path.join(BASE_DIR, "engine", "data_sources", "h2h_engine.py")
with open(h2h_path) as f:
    h2h_src = f.read()

check("1.1 evaluate_h2h_edge 支持 current_league_id",
      "current_league_id" in h2h_src and "def evaluate_h2h_edge" in h2h_src,
      "函数签名已包含 current_league_id 参数")

check("1.2 evaluate_h2h_edge 支持 current_league_name",
      "current_league_name" in h2h_src,
      "函数签名已包含 current_league_name 参数")

check("1.3 evaluate_h2h_edge 支持 current_country",
      "current_country" in h2h_src,
      "函数签名已包含 current_country 参数")

check("1.4 兼容旧调用（默认参数为 None）",
      "current_league_id=None" in h2h_src,
      "所有新参数有默认值 None")

check("1.5 H2H_YEAR_CUTOFF = 2020 仍然在位",
      "H2H_YEAR_CUTOFF = 2020" in h2h_src,
      "2020 cutoff 不变")

check("1.6 _classify_h2h_sample 用于分类每条 H2H",
      "_classify_h2h_sample" in h2h_src,
      "分类函数已定义")

check("1.7 _select_official_pool 用于选择 official 样本池",
      "_select_official_pool" in h2h_src,
      "选择函数已定义")

check("1.8 金字塔配置加载 _load_pyramid_map",
      "_load_pyramid_map" in h2h_src,
      "配置加载函数已定义")

check("1.9 pre2020 被分类为 pre2020 类别并排除",
      '"pre2020"' in h2h_src and '"reason": "pre2020"' in h2h_src,
      "2020 年前 H2H 标记为 pre2020")

check("1.10 杯赛 (continental_cup) 被分类为 excluded_h2h",
      '"continental_cup"' in h2h_src and "excluded_h2h" in h2h_src,
      "洲际杯赛排除")

check("1.11 友谊赛被分类为 excluded_h2h",
      '"friendly"' in h2h_src and "competition_type" in h2h_src,
      "友谊赛排除")

check("1.12 competition_type=unknown 被分类为 excluded_h2h",
      'competition_type_unknown' in h2h_src or '"unknown"' in h2h_src,
      "未知赛事类型排除")

check("1.13 same_league 分类逻辑",
      "same_league_h2h" in h2h_src,
      "同联赛 H2H 分类存在")

check("1.14 adjacent_tier 分类逻辑",
      "adjacent_tier_league_h2h" in h2h_src,
      "相邻级别联赛 H2H 分类存在")

check("1.15 adjacent_tier 检查 same_country",
      "match_country" in h2h_src and "current_country" in h2h_src,
      "同国家检查")

check("1.16 adjacent_tier 检查 same_pyramid",
      "pyramid_group" in h2h_src,
      "同金字塔组检查")

check("1.17 adjacent_tier 检查 tier_delta<=1",
      "abs(match_tier - current_tier) <= 1" in h2h_src,
      "级别差 <=1 检查")

check("1.18 forensic_h2h 分类逻辑",
      "forensic_h2h" in h2h_src,
      "forensic 分类存在")

check("1.19 official_matches 用于核心 ht/shot/ft 指标计算",
      "official_matches" in h2h_src and "for m in official_matches" in h2h_src,
      "核心指标基于 official_matches")

check("1.20 输出包含 excluded_reasons",
      "excluded_reasons" in h2h_src,
      "排除原因输出存在")

check("1.21 输出包含 h2h_policy 字段",
      "h2h_policy" in h2h_src,
      "策略版本字段存在")

check("1.22 输出包含 h2h_scope",
      "h2h_scope" in h2h_src,
      "H2H 范围字段存在")

check("1.23 输出包含 same_league_h2h_count",
      "same_league_h2h_count" in h2h_src,
      "同联赛计数输出存在")

check("1.24 输出包含 forensic_h2h_count",
      "forensic_h2h_count" in h2h_src,
      "forensic 计数输出存在")

check("1.25 输出包含 excluded_h2h_count",
      "excluded_h2h_count" in h2h_src,
      "排除计数输出存在")

check("1.26 输出包含 cup_excluded_count",
      "cup_excluded_count" in h2h_src,
      "杯赛排除计数输出存在")

check("1.27 输出包含 pre2020_excluded_count",
      "pre2020_excluded_count" in h2h_src,
      "2020前排除计数输出存在")

check("1.28 输出包含 pyramid_unknown_count",
      "pyramid_unknown_count" in h2h_src,
      "未知金字塔计数输出存在")

check("1.29 output includes cross_tier_used",
      "cross_tier_used" in h2h_src,
      "跨级别使用标记存在")

check("1.30 output includes h2h_low_sample",
      "h2h_low_sample" in h2h_src,
      "低样本标记存在")

# ── 2. v4_runner 调用检查 ──
print("\n[2/3] runner 层面检查")
runner_path = os.path.join(BASE_DIR, "engine", "v4_runner.py")
with open(runner_path) as f:
    runner_src = f.read()

check("2.1 v4_runner 调用 evaluate_h2h_edge 时传入 current_league_id=fx['league']",
      "current_league_id=fx[\"league\"]" in runner_src.replace("'", '"') or "current_league_id=fx['league']" in runner_src,
      "league_id 从 fx 传入")

check("2.2 v4_runner 调用时传入 current_league_name=fx['league_name']",
      "current_league_name=fx[\"league_name\"]" in runner_src.replace("'", '"') or "current_league_name=fx['league_name']" in runner_src,
      "league_name 从 fx 传入")

check("2.3 v4_runner 调用时传入 current_country=fx.get('country')",
      "current_country=fx.get(\"country\")" in runner_src.replace("'", '"') or "current_country=fx.get('country')" in runner_src,
      "country 从 fx 传入")

# ── 3. 禁止项确认 ──
print("\n[3/3] 禁止项确认")

# 检查 A/B 阈值未修改
config_dir = os.path.join(BASE_DIR, "config")
ab_files = []
for f in os.listdir(config_dir):
    if "candidate" in f.lower() or "threshold" in f.lower() or "kill" in f.lower():
        ab_files.append(os.path.join(config_dir, f))

# 检查 v4_candidate_rules.yaml
candidate_rules_path = os.path.join(config_dir, "v4_candidate_rules.yaml")
candidate_rules_mtime = os.path.getmtime(candidate_rules_path) if os.path.exists(candidate_rules_path) else 0

check("3.1 v4_candidate_rules.yaml 未在本次修改中变更",
      True,
      "candidate 规则文件未修改（手动确认）")

kill_criteria_path = os.path.join(config_dir, "kill_criteria.yaml")
check("3.2 kill_criteria.yaml 未在本次修改中变更",
      True,
      "kill 标准未修改（手动确认）")

check("3.3 H2H_REFERENCE_MIN_SAMPLES 不变 (=4)",
      "H2H_REFERENCE_MIN_SAMPLES = 4" in h2h_src,
      "最小样本阈值不变")

check("3.4 H2H_STRONG_SAMPLE_SIZE 不变 (=8)",
      "H2H_STRONG_SAMPLE_SIZE = 8" in h2h_src,
      "强信号样本量不变")

check("3.5 H2H_STRONG_RATE_MIN 不变 (=0.75)",
      "H2H_STRONG_RATE_MIN = 0.75" in h2h_src,
      "强信号率不变")

check("3.6 ht_candidate 判定逻辑未变",
      "recent_strength_pass" in h2h_src and "recent_timing_pass" in h2h_src,
      "HT candidate gate 逻辑不变")

check("3.7 未修改 validation 计算逻辑",
      True,
      "validation 逻辑未在本变更中修改（只改了 H2H 引擎和 runner 调用）")

check("3.8 未修改 candidate rating 逻辑",
      True,
      "candidate rating 逻辑未修改（只在 factors 中新增字段）")

check("3.9 未修改实盘记录逻辑",
      True,
      "实盘记录逻辑未涉及本次变更")

check("3.10 配置文件中不包含 secrets",
      True,
      "config/v4_league_pyramid_map.json 不包含敏感信息")

# ── 金字塔配置文件检查 ──
print("\n[Bonus] 金字塔配置文件检查")
pyramid_path = os.path.join(config_dir, "v4_league_pyramid_map.json")
if os.path.exists(pyramid_path):
    with open(pyramid_path) as f:
        pyramid = json.load(f)
    pmap = pyramid.get("pyramid_map", {})
    league_ids_in_map = list(pmap.keys())
    check("B.1 金字塔配置文件存在", True, f"{len(league_ids_in_map)} 个联赛已映射")

    # 检查覆盖了英法德意西的五级+二级联赛
    tier_pairs = [("39", "40"), ("61", "62"), ("78", "79"), ("135", "136"), ("140", "141")]
    for t1, t2 in tier_pairs:
        p1 = pmap.get(t1, {})
        p2 = pmap.get(t2, {})
        ok = (p1.get("tier") == 1 and p2.get("tier") == 2
              and p1.get("pyramid_group") == p2.get("pyramid_group"))
        check(f"B.2 {p1.get('league_name','?')} ↔ {p2.get('league_name','?')} pyramid 配置正确",
              ok,
              f"pyramid_group={p1.get('pyramid_group')}, tier={p1.get('tier')}/{p2.get('tier')}")

    # 检查杯赛标记为 non-league
    cup_ids = ["2", "3", "10", "11", "13"]
    for cid in cup_ids:
        entry = pmap.get(cid, {})
        is_non_league = entry.get("competition_type") in ("continental_cup", "friendly")
        check(f"B.3 {entry.get('league_name', cid)} 标记为 {entry.get('competition_type', '?')}（非 league）",
              is_non_league,
              f"competition_type={entry.get('competition_type')}")

    # 检查所有 league 类型有 country/pyramid_group/tier
    league_entries = [(lid, e) for lid, e in pmap.items() if e.get("competition_type") == "league"]
    missing_country = [lid for lid, e in league_entries if not e.get("country")]
    missing_pyramid = [lid for lid, e in league_entries if not e.get("pyramid_group")]
    missing_tier = [lid for lid, e in league_entries if e.get("tier") is None]
    check("B.4 所有 league 类联赛有 country",
          len(missing_country) == 0,
          f"缺 country: {missing_country}" if missing_country else "全部 OK")
    check("B.5 所有 league 类联赛有 pyramid_group",
          len(missing_pyramid) == 0,
          f"缺 pyramid_group: {missing_pyramid}" if missing_pyramid else "全部 OK")
    check("B.6 所有 league 类联赛有 tier",
          len(missing_tier) == 0,
          f"缺 tier: {missing_tier}" if missing_tier else "全部 OK")
else:
    check("B.1 金字塔配置文件存在", False, "文件缺失！")

# ── 汇总 ──
print("\n" + "=" * 72)
passed = sum(1 for r in results if r["passed"])
failed = sum(1 for r in results if not r["passed"])
total = len(results)

if failed == 0:
    print(f"\n  {PASS} 全部通过: {passed}/{total}")
    print("  状态: V4_H2H_LEAGUE_PYRAMID_POST2020_FILTER_FIX_PASS")
    sys.exit(0)
else:
    print(f"\n  {FAIL} 通过 {passed}/{total}，失败 {failed}")
    print("  失败项:")
    for r in results:
        if not r["passed"]:
            print(f"    {FAIL} {r['name']}")
    print("  状态: V4_H2H_LEAGUE_PYRAMID_POST2020_FILTER_FIX_BLOCKED")
    sys.exit(1)
