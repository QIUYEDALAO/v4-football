# V4 Scout Metadata Integrity Fix — 2026-05-29

## 问题

V4 parallel adapter（`engine/v4_scan_and_brief.py`）在写入 `scout_v4_YYYYMMDD.json` 时，`scout_entry` 缺少以下字段：

- `league_id`
- `league_name`
- `country`
- `source_group`
- `is_in_57_whitelist`
- `fixture_universe`
- `kickoff_bj`

而这些字段在 `candidate_view` 的 `entry` 中已正确写入。根因是 `scout_entry` 构建时未透传这些元数据。

## 修复

在 `v4_scan_and_brief.py` 的 `scout_entry` dict 中新增 7 个字段，均来自 scan result / fixture metadata，不重评分、不覆盖 candidate_view。

- `league_id`: `r.get("league_id")`
- `league_name`: `r.get("league_name", "?")`
- `country`: `r.get("country", "?")`
- `source_group`: `source_group`（由 `_get_source_labels` 计算）
- `is_in_57_whitelist`: `is_in_57`
- `fixture_universe`: `fixture_universe`（adapter 参数）
- `kickoff_bj`: `r.get("kickoff_time", "?")`

## BOSS 守卫

若 `league_id` 为 None，写入 `metadata_missing=true` + `metadata_missing_reason`，不伪造数据。

## 新增 Checker

`tools/check_v4_scout_metadata_integrity.py`：
1. 检查 scout entry 包含 `league_id`
2. 检查 scout entry 包含 `source_group`
3. `source_group` 仅允许 `WHITELIST_57` / `OUTSIDE_57`
4. scout `source_group` 与 candidate_view 一致
5. scout `grade` 与 candidate_view 一致
6. 调用 `check_v4_dashboard_refresh_no_regrade.py`
7. 调用 `check_v4_production_default_rules_guard.py`
8. QQ 未推送检查
9. validation 未重算检查
10. live bet 未修改检查
11. cron 未修改检查

## 验证结果

- Dry-run：3 个 mock fixture（正常/A级/null league_id）全部通过
- A/B 分级不变
- DEFAULT_RULES 未修改
- 无 regrade
- 无 QQ 推送
- 无 validation 重算
- 无 live bet 修改

## 文件变更

| 文件 | 操作 |
|------|------|
| `engine/v4_scan_and_brief.py` | 修改：scout_entry 新增 7 字段 + metadata_missing 守卫 |
| `tools/check_v4_scout_metadata_integrity.py` | 新增：335 行 checker |
| `docs/V4_SCOUT_METADATA_INTEGRITY_FIX_20260529.md` | 新增：本文档 |
