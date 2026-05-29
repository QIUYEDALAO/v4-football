# V4 Dashboard Restore From Last Good Version — 2026-05-29

## 问题

2026-05-29 下午 15:25 起 (`5d2fe99`)，dashboard 被多轮修改后严重偏离正常版本。当前版本虽能显示候选，但 CSS 压缩、视觉混乱、结构偏离 BOSS 接受版本。

## 恢复基准

**commit `9ddb36a`** (2026-05-29 13:42) — "v4: enable all eligible scan and expose whitelist57 stats"

这是今天 UI 改动开始前的最后一个正常 dashboard 版本。包含：
- BOSS 接受的 compact UI
- 完整 CSS 布局
- 候选卡片正常渲染
- 所有后台能力（all_eligible, WHITELIST_57/OUTSIDE_57, score fields, no-regrade）

## 修复

### HTML
- 从 `9ddb36a` 导出 dashboard HTML（906 行）完全替换当前版本
- 追加 7 项数据兼容修补：
  1. `srcGroupDisplay()` → 57白名单/名单外
  2. `uniDisplay()` → 全量合规
  3. "候选剧本" → "正式候选"
  4. "N/A" → "开赛时间待定"
  5. 428/13/0.86 → null（未投注候选为空）
  6. source_group 标签行
  7. `addBet` stake → null

### Checker
- `check_v4_control_center.py` 恢复为 `9ddb36a` 版本 + 适配
- `check_v4_dashboard_restored_from_yesterday.py` 新增

## 验证

- 全部 checker PASS
- A=1 B=1 SKIP=240
- todo=2
- DEFAULT_RULES 未改
- validation 未重算
- live bet 未改
- QQ 未推送

## 变更文件

| 文件 | 操作 |
|------|------|
| `data/runtime/dashboard/v4_control_center.html` | 替换为 9ddb36a + 数据修补 |
| `tools/check_v4_control_center.py` | 恢复为 9ddb36a + 适配 |
| `tools/check_v4_dashboard_restored_from_yesterday.py` | 新增 |
| `docs/V4_DASHBOARD_RESTORE_FROM_YESTERDAY_20260529.md` | 新增 |
