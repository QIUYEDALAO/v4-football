# Validation Lineage Hard Freeze & Number Audit — 2026-05-20

## Conclusion: VALIDATION_LINEAGE_HARD_FREEZE_PASS

### 1. A+B=133 解释

| 字段 | 值 |
|------|-----|
| A 记录数 | 41（32 唯一比赛） |
| B 记录数 | 92（74 唯一比赛） |
| A+B 合计 | **133** |
| 命中 | 75 |
| 失败 | 55 |
| 未知 | 3 |
| 已结算 | 130 |
| 命中率 | **57.69%** = 75/(75+55) |
| 来源文件 | 8 个 v4_result_attribution JSONL（20260512-20260519） |
| 重复 | 0 |
| 可追溯 | YES — 每条记录有 source_file + fixture_id |

### 2. 7d/14d/30d 完全相同解释

**原因：数据仅覆盖 7 天。**

Attribution 数据仅覆盖 2026-05-12 至 2026-05-19（8个文件，8天）。
- 7天窗口：2026-05-13 至 2026-05-19 → 捕获所有记录
- 14天窗口：2026-05-06 至 2026-05-19 → 捕获所有记录（05-06至05-12期间无数据）
- 30天窗口：2026-04-20 至 2026-05-19 → 捕获所有记录（04-20至05-12期间无数据）

每个窗口独立按日期过滤，但因为所有记录都落在所有三个窗口内，结果相同。**这不是 bug，不是复制，是数据可用性限制。**

### 3. Unknown 命中率 = N/A

| 范围 | Unknown | Resolved | 显示 |
|------|---------|----------|------|
| B 昨日 | 3 | 0 | **N/A** |
| C 昨日 | 13 | 0 | **N/A** |
| V2 BET_LOCKED | 1 | 0 | **N/A** |

命中率公式：`hit / (hit + miss)`。当 `hit + miss = 0` 时，命中率 = N/A。**任何地方都不显示 0%。**

### 4. 硬冻结状态

- 438 条原始记录
- 312 唯一比赛
- 0 条重复
- 8 个来源文件
- 每条记录可追溯到 source_file + fixture_id
- 数据血缘：**VERIFIED**

### 5. Checker 结果：72/72 PASS

| Checker | Checks | Result |
|---------|--------|--------|
| validation_lineage_hard_freeze | 10 | PASS |
| validation_data_lineage | 17 | PASS |
| grade_split_validation_dashboard | 13 | PASS |
| intel_ops_console | 19 | PASS |
| intel_ops_console_chinese_ux | 13 | PASS |
