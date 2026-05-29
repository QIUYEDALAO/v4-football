# V4 作战台 UI 恢复

## 恢复基准

恢复至 commit `ab4e608`（"merge accepted V4 UI with live data binding") 的视觉布局、CSS、候选卡片结构和整体风格。

## 保留的后台能力

- all_eligible 正式扫描
- WHITELIST_57 / OUTSIDE_57 分层
- no-regrade dashboard 刷新
- score_pack / factors / market_scores 数据字段
- source_group 中文标签（57白名单 / 名单外）
- fixture_universe 中文标签（全量合规）
- 未投注候选金额/分钟/水位为空

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
| 重跑 scan | ❌ 未触发 |
