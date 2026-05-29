# V4 Parallel Adapter Score Fields Fix — 2026-05-29

## 根因

`evaluate_h2h_edge` (h2h_engine) 返回 `market_scores`、`factors`、`score_pack`，但 scanner 的 `_process_one_fixture` (v4_outside57_scanner) 只提取了 `grade`、`ht_score`、`h2h_valid` 等 summary 字段，未转发评分细节。

adapter (v4_scan_and_brief) 的 `scout_entry` 从 scan result 读取 `r.get("market_scores")` 等，但 scanner 从未填充这些字段，导致 scout 中全是 `{}`。

## 修复

### 1. h2h_engine.py — 添加 score_pack 到返回值
- valid=True 返回：新增 `"score_pack": score_pack`
- valid=False 返回：新增 `"market_scores": score_pack["scores"]` + `"score_pack": score_pack`

### 2. v4_outside57_scanner.py — 转发评分字段
`_process_one_fixture` 的 `result_base.update()` 新增 11 个字段：
- `market_scores`, `factors`, `score_pack`
- `h2h_score`, `recent_form_summary`, `time_bins`
- `late_fh_pressure`, `h2h_policy`, `h2h_low_sample`
- `recent_form_sample_size`, `events_complete`

新增 BOSS 守卫：
- `market_scores_missing=true` 当字段为空
- `factors_missing=true` 当字段为空
- `score_pack_missing=true` 当字段为空

### 3. v4_scan_and_brief.py — adapter 透传
scout_entry 新增 10 个字段透传 + missing-field 标记。

### 4. tools/check_v4_parallel_adapter_score_fields.py
283 行 fail-closed checker，覆盖 18 项检查。

## 验证

- Dry-run：candidate / SKIP / missing 三种场景全部通过
- market_scores/factors/score_pack 正确从 scanner 流转到 scout
- official grade 未被重算
- DEFAULT_RULES 未修改
- 子 checker 全部 PASS
- QQ 未推送 / validation 未重算 / live bet 未修改

## 变更文件

| 文件 | 操作 |
|------|------|
| `engine/data_sources/h2h_engine.py` | 修改：返回中添加 score_pack |
| `engine/v4_outside57_scanner.py` | 修改：转发评分字段 + missing 守卫 |
| `engine/v4_scan_and_brief.py` | 修改：scout_entry 透传新字段 |
| `tools/check_v4_parallel_adapter_score_fields.py` | 新增 |
| `docs/V4_PARALLEL_ADAPTER_SCORE_FIELDS_FIX_20260529.md` | 新增 |
