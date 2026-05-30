# V4_RF_SHADOW_GRADE — 运行态验收待补

**生成时间：** 2026-05-31 00:05 CST

## 验收状态（修正后）

| 维度 | 状态 |
|------|------|
| Codex 代码施工 | ✅ **V4_RF_SHADOW_GRADE_CODE_READY** |
| 静态规则验证 | ✅ **V4_RF_SHADOW_GRADE_STATIC_RULE_PASS** |
| 运行态验收 | ⏳ **V4_RF_SHADOW_GRADE_RUNTIME_PENDING** |

## 上一轮不能收 full PASS 的原因

1. **OpenClaw 最终依赖旧 scout + 内存执行 build_rf_shadow_grade_layer()**，不是从新扫描产物中证明字段存在。
2. **未生成 rf_shadow_grade 真实进入新 scout 的运行态产物** — 正式入口 serial dry-run 多次超时 / kill / 重跑，产物 scout 为空（全部 SKIP）。
3. **candidate_view / dashboard model 无新产物闭环证据** — 因无 A/B/C 候选，model 中 candidate_items=0，无法证明 shadow 字段正常映射。
4. **serial dry-run 不满足稳定验收条件** — 多次被 timeout kill、进程挂死、重跑，不能作为稳定验收依据。

## 已确认通过的规则（静态验证）

| 规则 | 结果 | 方法 |
|------|------|------|
| HOT_DRIVER + ACCEPTABLE → B | ✅ PASS | 代码走查 + 旧 scout 数据内存实测 |
| 弱边 3/5 不直接 SKIP | ✅ PASS | 代码走查：WEAK 状态不触发 SKIP |
| 近10 6/10 + 近5 5/5 → B 破格 | ✅ PASS | 代码走查：ENTRY_BREAK_B_6OF10_5OF5 |
| 近10 5/10 + 近5 5/5 → C 观察 | ✅ PASS | 代码走查：ENTRY_C_OBSERVE_5OF10_5OF5 |
| 近10 ≤4/10 不进 A/B shadow | ✅ PASS | 代码走查：ENTRY_BLOCK_LE4 |
| H2H weak/no-bonus 不降级 | ✅ PASS | "H2H不支持，不降级" |
| H2H strong 不单独制造 A/B | ✅ PASS | 仅加分不减级 |
| MARKET_STRONG_CONFIRM 不制造 A/B | ✅ PASS | "提升信心不改级别" |
| MARKET_HARD_VETO 仅影响 shadow | ✅ PASS | A→C, B→C, C→SKIP |
| MARKET_NO_MARKET 不进入待投 | ✅ PASS | → SKIP |
| **official grade 未被 shadow 覆盖** | ✅ **PASS** | grade 字段独立于 rf_shadow_grade |

## 未完成的运行态证明

- [ ] rf_shadow_grade 进入新 scout
- [ ] rf_shadow_grade 进入新 candidate_view
- [ ] rf_shadow_grade 进入 dashboard model
- [ ] balance_reason / market_reason 进入新运行态产物
- [ ] OpenClaw 在无 kill/retry 条件下完成正式入口补验

## 后续补验触发条件

1. **有真实白名单有效样本** — 在有 A/B 候选的日期，以正式入口 serial / whitelist / no-push 补跑。
2. **或新增轻量 runtime acceptance 工具** — 不调 API，读取已存在 scout + e47031e 代码生成 shadow 字段，产生临时验收产物。
3. **或正式入口提供 max-fixtures / sample-mode 安全参数** — 只跑前 N 场，控制运行时间。

## 生产安全检查（本轮已验证）

| 检查项 | 状态 |
|--------|------|
| DEFAULT_RULES 未改 | ✅ |
| A/B 阈值未改 | ✅ |
| cron 未改 | ✅ |
| validation 未重算 | ✅ |
| validation 历史未改 | ✅ |
| live bet 未改 | ✅ |
| QQ 未推 | ✅ |
| 无代码修改 | ✅ |
| 无 commit/push | ✅ |

## 禁止事项

- ❌ 不得声称 RUNTIME_PASS
- ❌ 不得进入 Phase 4/5/6
- ❌ 不得修改 official grade
- ❌ 不得修改 DEFAULT_RULES
- ❌ 不得再次长时间 serial dry-run
- ❌ 不得实现 CPL
