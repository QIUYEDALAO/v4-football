# V2 Validation Caliber Audit — 最终报告

**日期**: 2026-05-21
**阶段**: V2-VALIDATION-CALIBER-AUDIT-20260521

---

## BOSS 问题

Dashboard 显示"V2验证：185已结算，45.9%"。BOSS 要求核实：**这185条是否全部是 BET_LOCKED 正式推荐？**

BOSS 硬规则："V2正式推荐只认 BET_LOCKED。WATCH_EARLY / CANDIDATE / FINAL_RECORD / daily pool / historical replay / backtest pool 不能混入正式命中率。"

---

## 审计结论

**否。185已结算全部来自 V2 历史池（WATCH_EARLY + CANDIDATE），0 条为 BET_LOCKED 正式推荐。**

| 项目 | 数值 | 说明 |
|------|------|------|
| Dashboard 原显示 | 185已结算 / 45.9% | 标注"仅 BET_LOCKED" — **错误** |
| 实际正式 BET_LOCKED | 1 场（未结算） | Ried vs Wolfsberger AC, #1545407, 20260519 |
| 正式 BET_LOCKED 命中率 | N/A | 样本不足（0 已结算） |
| 历史池（WATCH/CANDIDATE） | 185已结算 / 45.9% | 12 天数据，审计追溯用 |

---

## 关键证据

1. **BET_LOCKED 仅 1 条**：`v2_rolling_validation_split_20260520.json` 明确记载 "V2 BET_LOCKED 仅在 2026-05-19 有 1 条记录"
2. **该 BET_LOCKED 不在 185 中**：fixture_id 1545407 在 `v2_validation_detail_model_20260521.json` 中 grep 结果为 0
3. **每日池分布**：`v2_daily_pool_summary_20260516.json` 显示典型比例 — BET_LOCKED:0, WATCH_EARLY:126, CANDIDATE:3
4. **Dashboard 原标注错误**：多处声称"仅统计 BET_LOCKED，累计185场"，实际数据从未按 caliber 过滤

---

## 修复措施

### Dashboard 变更

| 位置 | 原文本 | 修复后 |
|------|--------|--------|
| V2 摘要卡 | "V2 滚动验证：累计185场..." | "V2 历史池审计：累计185场... ⚠ 非正式BET_LOCKED" |
| V2 摘要卡 | （无） | 新增 "V2 正式 BET_LOCKED：1场 · 0已结算 · 样本不足" |
| 详细折叠区标题 | "V2 滚动验证（仅统计 BET_LOCKED，累计185场）" | "V2 历史池审计（WATCH/CANDIDATE追溯，累计185场 — 非正式BET_LOCKED）" |
| 统计口径 | "仅 BET_LOCKED（排除 WATCH/CANDIDATE）" | "⚠ 历史池 WATCH_EARLY + CANDIDATE（非正式 BET_LOCKED）" |
| 累计已结算 | "185 场 · 命中85 · 失败100" | "185 场 · 命中85 · 失败100（审计追溯用，不进正式命中率）" |
| 历史命中率 | "45.9%" | "45.9%（仅供参考）" |
| 底部说明 | "仅 BET_LOCKED 进入正式命中率" | "⚠ 以上 185 场为历史池... 正式 BET_LOCKED 仅 1 场且未结算，命中率不可用" |

### 新增文件

| 文件 | 说明 |
|------|------|
| `data/runtime/status/v2_validation_185_source_audit_20260521.json` | 来源审计详情 |
| `tools/check_v2_validation_caliber_audit.py` | 35 项检查 |

### 修改文件

| 文件 | 说明 |
|------|------|
| `data/runtime/dashboard/intel_ops_console.html` | V2 标签修正 + 正式/历史池分离 |
| `tools/check_intel_ops_console_validation_detail_restore.py` | caliber 检查更新为新标签 |

---

## Checker 验证结果

| Checker | 结论 | Total | Pass | Fail |
|----------|------|-------|------|------|
| check_v2_validation_caliber_audit | PASS | 35 | 35 | 0 |
| check_intel_ops_console_validation_detail_restore | PASS | 28 | 28 | 0 |

**总: 63 checks | 63 PASS | 0 FAIL | 0 BLOCKER**

---

## 待办建议

1. **V2 validation detail model 需增加 caliber 字段**：每条 match 记录应有 `record_type: "BET_LOCKED" | "WATCH_EARLY" | "CANDIDATE"` 以便未来自动区分
2. **正式 BET_LOCKED 结算追踪需独立**：不能混入历史池。未来 BET_LOCKED 结算数据需单独建表
3. **Dashboard 未来布局**：当正式 BET_LOCKED 积累足够样本后，分两行展示：
   - 正式 BET_LOCKED：N 已结算 · 命中率 X%
   - 历史池审计：M 已结算 · 命中率 Y%（仅供参考）

---

## 结论

**V2_VALIDATION_CALIBER_AUDIT_PASS**

Dashboard 标签已修正。185/45.9% 明确标注为历史池审计数据。正式 BET_LOCKED 命中率因样本不足（0 已结算）暂不可用。
