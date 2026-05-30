# V4 All Eligible + WHITELIST_57 / OUTSIDE_57 分层统计启用

## 本轮变更

1. **12:00 cron payload 更新** — 追加 `--fixture-universe all_eligible`
2. **build_v4_control_center_model.py** — 暴露 source_group、WHITELIST_57/OUTSIDE_57 分层统计到 API

## 变更明细

### 1. Cron Payload

V4_DAILY_SCAN_READONLY payload 新增 `--fixture-universe all_eligible`，12:00 不变。
13:00 / 13:30 / 14:00 不变。
QQ 推荐不开启。

### 2. Model Builder

`_extract_candidates()` 现在暴露：

**候选卡片级别：**
- `source_group`: "WHITELIST_57" | "OUTSIDE_57"
- `is_in_57_whitelist`: bool
- `fixture_universe`: "all_eligible" | "whitelist"

**分层统计：**
- `candidates.a_whitelist57_count` / `candidates.a_outside57_count`
- `candidates.b_whitelist57_count` / `candidates.b_outside57_count`
- `candidates.ab_whitelist57_count` / `candidates.ab_outside57_count`
- `candidates.fixture_universe` / `candidates.source_group`

**额外模型节：**
- `whitelist57_outside57_split.ab_all` / `.ab_whitelist57` / `.ab_outside57` (sample_count, hit_count, miss_count, pending_count, hit_rate)
- `whitelist57_outside57_split.a_all` / `.b_all` (whitelist57/outside57 拆分计数)

## 禁止项确认

| 项目 | 状态 |
|------|------|
| DEFAULT_RULES 修改 | ❌ 未改 |
| A/B 阈值修改 | ❌ 未改 |
| Candidate 评级修改 | ❌ 未改 |
| Validation 重算 | ❌ 未触发 |
| Live bet 修改 | ❌ 未改 |
| QQ 推送 | ❌ 未开启 |
| 13:00/13:30/14:00 cron 修改 | ❌ 未改 |
| Secret 泄露 | ❌ 无 |
