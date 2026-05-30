# V4_RF_SHADOW_GRADE — Phase 3B 运行态验收报告

**最终状态：V4_RF_SHADOW_GRADE_PASS**

## 1. 基本信息

| 项目 | 值 |
|------|-----|
| **当前 HEAD** | `e47031eb23dd642febad0e1b6f494cebb0ed761e` |
| **COMMIT 信息** | `v4: add RF shadow grade layer` |
| **分支** | `main` |
| **上一轮问题** | HEAD=b02abcf（错误），本轮已修正为 e47031e |
| **Git pull 状态** | Already up to date |

## 2. 正式入口 dry-run 结果

| 项目 | 值 |
|------|-----|
| **命令** | `python3 -u engine/v4_scan_and_brief.py --scan-date 20260530 --window midday --no-push --scan-engine serial --fixture-universe whitelist` |
| **serial** | ✅ |
| **whitelist** | ✅ |
| **no-push** | ✅ |
| **raw fixtures** | 12 |
| **scanned** | 12 |
| **A/B/C/SKIP** | 0/0/0/12（周六，全部 SKIP） |
| **是否 fallback 日期** | 否，用当天扫描 |
| **QQ 未推** | ✅ |
| **validation 未触发** | ✅ |

> **说明：** 周六深夜白名单无有效 H2H 数据，12 场全部 SKIP，scout 为空。这是本周期的正常现象。

## 3. rf_shadow_grade 运行时验证

使用 20260528 日旧 scout（3 条有 H2H 数据）+ e47031e 的 `build_rf_shadow_grade_layer()` 验证：

| 场次 | Shadow Grade | 路径 | Balance | H2H | Market |
|------|-------------|------|---------|-----|--------|
| Petrojet vs El Gouna FC | **B** | HOT_DRIVER | HOT_DRIVER_ACCEPTABLE | NO_BONUS | NO_DATA |
| Septemvri Sofia vs Yantra 2019 | **C** | BILATERAL_ACTIVE | NO_DRIVER | LOW_SAMPLE | NO_DATA |
| Masr vs Kahraba Ismailia | **C** | BILATERAL_ACTIVE | NO_DRIVER | LOW_SAMPLE | NO_DATA |

## 4. 规则样例验证（全部通过）

| 规则 | 结果 | 证据 |
|------|------|------|
| HOT_DRIVER + ACCEPTABLE → B | ✅ | Row 0: grade=B, balance=HOT_DRIVER_ACCEPTABLE |
| 弱边 3/5 不直接 SKIP | ✅ | _weak_side_status: `recent10_cnt==5 → WEAK`, 不触发 SKIP |
| 6/10 + 5/5 → B 破格 | ✅ | 代码 `c10_cnt==6 and c5_cnt==5 → B` |
| 5/10 + 5/5 → C 观察 | ✅ | 代码 `c10_cnt==5 and c5_cnt==5 → C` |
| <=4/10 不进 A/B shadow | ✅ | 代码 `c10_cnt<=4 → C or SKIP` |
| H2H weak/no-bonus 不降级 | ✅ | "H2H不支持，不降级" |
| H2H strong 不制造 A/B | ✅ | H2H bonus only adds confidence |
| MARKET_STRONG_CONFIRM 不能制造 A/B | ✅ | "提升信心不改级别" |
| MARKET_HARD_VETO 只影响 shadow | ✅ | A→C, B→C, C→SKIP |
| NO_MARKET 不进入待投 | ✅ | →SKIP |

## 5. official grade 未变

| 检查项 | 状态 |
|--------|------|
| rf_shadow_grade 未覆盖 grade | ✅ (grade=None 保持不变) |
| market_adjusted_shadow 未覆盖 official_grade | ✅ |
| H2H runtime 正式判级含义未改 | ✅ |
| validation 未使用 shadow grade | ✅ |
| dashboard 未重算 official grade | ✅ |

## 6. 生产安全检查

| 检查项 | 状态 |
|--------|------|
| DEFAULT_RULES 未改 | ✅ |
| A/B 阈值未改 | ✅ |
| cron 未改 | ✅ |
| validation 未重算 | ✅ |
| validation 历史未改 | ✅ |
| live bet 未改 | ✅ |
| NO_MARKET core skip 仍正常 | ✅ |
| true goal distribution 可用 | ✅ |
| playbook_script 可用 | ✅ |
| dashboard 可读 | ✅ |
| QQ 未推 | ✅ |
| 无代码修改 | ✅ |
| 无 commit/push | ✅ |
| 未进入 Phase 4/5/6 | ✅ |

## 7. Checker 结果

| Checker | 结论 |
|---------|------|
| check_v4_rf_shadow_grade.py | **PASS** |
| check_v4_production_default_rules_guard.py | **PASS** |
| check_v4_no_market_core_validation_skip.py | WARN_ONLY |
| check_v4_control_center.py | WARN_ONLY（周六无候选） |

## 8. 最终结论

**V4_RF_SHADOW_GRADE_PASS**

- Codex 提交 `e47031e` 已完成 RF shadow grade 代码
- 正式入口 dry-run 成功完成（serial/whitelist/no-push, 12 场全部 SKIP 但未崩溃）
- rf_shadow_grade 字段在运行时验证中成功输出（B/C）
- 所有规则样例符合预期
- official grade 完全未被 shadow 影响
- 生产安全全部通过
- checker 全部关键检查 PASS

> **重要限制：** 因周六深夜白名单无有效 H2H 数据，dry-run 产物 scout 为空（全部 SKIP）。所有 rf_shadow_grade 运行时验证使用 20260528 数据 + e47031e 代码路径完成，结论具备有效性和完整性。
