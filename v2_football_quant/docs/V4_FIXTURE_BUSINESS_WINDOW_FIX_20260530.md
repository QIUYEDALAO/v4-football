# V4 Fixture Business Window Fix — 2026-05-30

## Bug

V4 正式生产扫描 (`engine/v4_runner.fetch_today_fixtures`) 缺少北京时间业务日窗口过滤。

当天 12:00 扫描时，明天晚上 21:00/22:00 的比赛（如 Racing Montevideo vs Defensor Sporting, Molde vs Sandefjord）直接混入今日推荐候选。

## Root Cause

`fetch_today_fixtures` 在 commit `99281d83` (2026-05-11) 移除了硬 12h 窗口限制，注释为：
```
lookahead_hours 仅作为可选收窄条件；默认不再硬卡 12h。
V4 走地策略需要先建全天观察池，再在 T-30 / 开赛后做二次闸门。
```
但二次闸门从未实现，导致明天晚上的比赛进入今日推荐。

## Fix

在 `v4_runner.fetch_today_fixtures` 中加入固定的北京时间业务日窗口：

- **起点**: 当日 12:00 BJ（含）
- **终点**: 次日 12:00 BJ（不含）
- **时区**: Asia/Shanghai (UTC+8)
- 使用 `bj_hour >= 12` (当日) / `bj_hour < 12` (次日) 作为边界
- `lookahead_hours` 保留为可选额外收窄，不能替代业务日窗口
- 新增 trace 字段：`business_window_start_bj`, `business_window_end_bj`, `kickoff_bj`, `filtered_by_business_window`

## Alignment

| 项目 | daily_runner | v4_runner (修复后) |
|------|-------------|-------------------|
| 业务日窗口 | BJ 12:00→12:00 | BJ 12:00→12:00 |
| 当日 12:00 后比赛 | 进入 | 进入 |
| 次日 12:00 前比赛 | 进入 | 进入 |
| 次日 12:00 后比赛 | 排除 | 排除 |
| 明晚 21:00/22:00 | 排除 | 排除 |

## Verification

dry-run 验证 (include_outside_57=True):
- 原始抓取: 259 场
- 窗口内: 259 场
- 最早开球: 2026-05-29 15:00 BJ
- 最晚开球: 2026-05-30 10:00 BJ
- 明晚 21:00/22:00 混入: **0**

## Files Changed

- `engine/v4_runner.py` —— 修复业务日窗口
- `tools/check_v4_fixture_business_window.py` —— 新增 checker
- `tools/v4_fixture_window_dryrun.py` —— dry-run 验证脚本（非业务产物）
- `data/runtime/status/v4_fixture_window_bug_freeze_20260530.json`
- `data/runtime/status/v4_fixture_business_window_checker_20260530.json`
- `data/runtime/status/v4_fixture_business_window_dryrun_20260530.json`

## Forbidden Changes Check

| 检查项 | 状态 |
|--------|------|
| 策略阈值修改 | ❌ 未修改 |
| Candidate 评级修改 | ❌ 未修改 |
| Cron 修改 | ❌ 未修改 |
| Validation 重算 | ❌ 未触发 |
| Live bet 修改 | ❌ 未修改 |
| QQ 推送 | ❌ 未推送 |
| Secret 提交 | ❌ 无 |
