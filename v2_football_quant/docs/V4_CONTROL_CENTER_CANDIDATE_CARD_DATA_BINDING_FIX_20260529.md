# V4 作战台候选卡片数据绑定修复

## 修复内容

1. **Model builder 从 scout 合并评分字段**
   `_extract_candidates` 现在接受 `scout_data` 参数，按 fixture_id 查找 scout 中的 `score_pack`、`market_scores`、`factors`、`time_bins`、`h2h_official_count`、`late_fh_pressure` 等字段，合并到 model 候选卡片。

2. **HTML 显示修复**
   - `srcGroupDisplay`：`WHITELIST_57` → `57白名单`，`OUTSIDE_57` → `名单外`
   - `uniDisplay`：`all_eligible` → `全量合规扫描`
   - 开赛时间优先 `kickoff_local` → `kickoff_time` → `match_time` → `kickoff` → `time`
   - time_bins 缺失时显示 score_pack 评分摘要
   - 解释字段全部缺失时才显示"解释数据缺失，不影响 official grade"
   - 未投注候选表单金额/分钟为空

## 禁止项确认

| 项目 | 状态 |
|------|------|
| DEFAULT_RULES 修改 | ❌ 未改 |
| A/B 阈值修改 | ❌ 未改 |
| Candidate 评级修改 | ❌ 未改 |
| Cron 修改 | ❌ 未改 |
| Validation 重算 | ❌ 未触发 |
| Live bet 修改 | ❌ 未改 |
| QQ 推送 | ❌ 未推送 |
