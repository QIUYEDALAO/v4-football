# V4 Dashboard Display Field Final Fix — 2026-05-29

## 问题

昨日 dashboard 恢复后仍有 4 个显示字段问题：
1. 缺失 time_bins 时渲染为假 "0-15 0% · 16-30 0% · 31-45 0%"
2. 开赛时间显示完整 ISO 格式 "2026-05-30T01:00:00+08:00"
3. 候选卡片缺失 "57白名单 · 全量合规" 来源标签
4. 右侧待投注显示 "A2" 而非 "A1/B1"

## 修复

### HTML (`data/runtime/dashboard/v4_control_center.html`)

1. **假 0% 时间分布**：`fmtPct` 增加 null 守卫；缺失时显示 "评分摘要暂缺" 或评分数据摘要
2. **开赛时间格式**：新增 `fmtKickoff()` 函数，ISO → "05-30 01:00" 紧凑格式
3. **来源标签**：候选卡片新增 `source-label` 行显示 "57白名单 · 全量合规"
4. **A2 标签**：`todoBetBadge` 从 `A${tb}` 改为 `A${a}B${b}`；KPI 显示 `A1/B1/SKIP240`

### Checker
- `tools/check_v4_dashboard_display_field_final.py` 新增

## 验证

- 全部 checker PASS
- A=1 B=1 SKIP=240
- 候选卡 2 张
- 安全默认值保持（428/13 不复现）
- DEFAULT_RULES 未改
- validation 未重算
- QQ 未推送
