# V4 Control Center Accepted UI Restore — 2026-05-29

## 问题

多轮修补后 V4 作战台 UI 偏离 BOSS 接受的 gold template（`14f0be1`）。CSS 被压缩成一行，视觉层次混乱，候选卡片失去紧凑实盘风格。

## 恢复基准

**commit `14f0be1`** — "dashboard: compact V4 control center operations UI"
此版本是 BOSS gold template：240 行 CSS、完整抽屉面板系统、底部导航、6-KPI 布局。

## 修复

### 1. HTML 恢复（以 gold template 为基底）
- 恢复完整 CSS（`:root` 变量、`.card`、`.candidate`、`.kpi`、`.primary-layout`、`@media` 等）
- 恢复 6 KPI 卡片布局（今日候选、昨日验证、验证累计、今日盈亏、流水/返水、今日待办）
- 恢复底部工具栏 + 底部导航
- 恢复完整抽屉面板系统

### 2. 数据改善移植（从当前版本）
- `srcGroupDisplay()`: WHITELIST_57 → "57白名单" / OUTSIDE_57 → "名单外"
- `uniDisplay()`: all_eligible → "全量合规"
- 投注默认值：null（不预填 428/13/0.86）
- 文案："正式候选" 替代 "候选剧本"
- "开赛时间待定" 替代 N/A
- `inlineBet` stake fallback: null 替代 428

### 3. Model 兼容层
- `normalizeModel()`: 自动适配当前 model 字段名到 gold template 期望

### 4. Checker 更新
- `check_v4_control_center.py`: 适配 gold template DOM 结构
- `check_v4_control_center_candidate_render_integrity.py`: 适配 `buildCandidateCard`

## 验证

- 全部 checker PASS（含 WARN_ONLY）
- A=1 B=1 SKIP=240
- todo=2
- DEFAULT_RULES 未改
- validation 未重算
- live bet 未改
- QQ 未推送

## 变更文件

| 文件 | 操作 |
|------|------|
| `data/runtime/dashboard/v4_control_center.html` | 修改：恢复为 gold template + 数据改善 |
| `tools/check_v4_control_center.py` | 修改：适配 gold template |
| `tools/check_v4_control_center_candidate_render_integrity.py` | 修改：适配 buildCandidateCard |
| `docs/V4_CONTROL_CENTER_ACCEPTED_UI_RESTORE_20260529.md` | 新增 |
