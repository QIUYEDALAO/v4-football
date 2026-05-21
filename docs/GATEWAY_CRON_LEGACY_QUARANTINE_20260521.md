# GATEWAY CRON LEGACY QUARANTINE REPORT 2026-05-21

## Summary

- Phase: GATEWAY-CRON-LEGACY-QUARANTINE-20260521
- Date executed: 2026-05-21
- Result: PASS
- Backup: `data/runtime/status/gateway_cron_backup_20260521.json` + `system_crontab_backup_20260521.txt`

## Before / After

| Metric | Before | After |
|:---|---:|---:|
| Total Gateway cron | 25 | 12 |
| KEEP_ACTIVE | — | 11 |
| KEEP_STATUS_ONLY | — | 1 |
| QUARANTINE_DISABLED | — | 9 |
| DELETED expired one-shot | — | 4 |
| System crontab | 1 (pre_match_reminder) | 0 (disabled) |

## What was kept (12)

| # | Name | Status |
|:-:|:---|:---:|
| 1 | V4赛中快照 | ✅ active |
| 2 | V2窗口检查器 | ✅ active |
| 3 | V2建池-每日 | ✅ active |
| 4 | V2 DAILY_POOL Health Check | ✅ active |
| 5 | V2每日结算 | ✅ active |
| 6 | V4每日复盘 | ✅ active |
| 7 | SYS每日结算汇总 | ✅ active |
| 8 | 每日状态更新 | ✅ active |
| 9 | SYS-架构审计守卫 | ✅ active, delivery.mode=none |
| 10 | V2每日状态回执 | ✅ active |
| 11 | V4周报 | ✅ active |
| 12 | V4月报 | ✅ active |

## What was disabled (9)

| # | Name | Reason |
|:-:|:---|:---|
| 1 | V4扫描-早场 07:20 | legacy multi-window scan |
| 2 | V4扫描-午间 14:05 | legacy multi-window scan |
| 3 | V4扫描-傍晚 16:20 | legacy multi-window scan |
| 4 | V4扫描-晚间 22:20 | legacy multi-window scan |
| 5 | V4扫描-凌晨 01:20 | legacy multi-window scan |
| 6 | V2早场兜底 07:35 | legacy fallback |
| 7 | V2晚场兜底 18:35 | legacy fallback |
| 8 | V2夜间兜底 23:35 | legacy fallback |
| 9 | V2每日结算-补跑 15:37 | legacy catchup |

## What was deleted (4 expired one-shots)

| # | Name | ID | deleteAfterRun |
|:-:|:---|:---|---:|
| 1 | V4_MIDDAY_ONE_SHOT_20260520 | 95676a5c | true |
| 2 | V4_EVENING_ONE_SHOT_20260520 | 82b6d42b | true |
| 3 | V4_NIGHT_ONE_SHOT_20260520 | b9c4fa16 | true |
| 4 | V4午间最后验收 | acaa39be | true |

## System crontab

| Script | Schedule | Status |
|:---|---:|:---|
| pre_match_reminder.py | */2 * * * * | DISABLED (commented out) |

### Audit findings
- ✅ No QQ push
- ✅ No state/verified write
- ✅ No V33/D13/HOURLY
- ✅ No scan trigger
- ✅ Only macOS desktop notification (display notification)
- ❌ Unnecessary 2-min polling, reads V4 brief format that may change
- Action: Commented out, script still available at `tools/pre_match_reminder.py`

## SYS-架构审计守卫

- ✅ Kept (not deleted)
- ✅ enabled=True
- ✅ delivery.mode=none (no push)
- ✅ No systemEvent
- ✅ No QQ push
- ✅ No announce
- ✅ Only writes status

## Final verification

| Check | Result |
|:---|---:|
| V4旧多窗口 active_count | ✅ 0 |
| V4旧 one-shot active_count | ✅ 0 (removed) |
| V2旧兜底 active_count | ✅ 0 |
| SYS guard active_count | ✅ 1, status_only |
| V2正式 cron 保留 | ✅ V2窗口检查器, V2建池, V2每日结算, V2状态回执 |
| V4每日复盘/周报/月报 保留 | ✅ all 3 |
| delivery.mode=announce one-shot | ✅ 0 |
| systemEvent push count | ✅ 0 |
| secret count | ✅ 0 |
| D13/V33/HOURLY active | ✅ 0 |

## Safety confirmations

| Item | Status |
|:---|:---:|
| capture_ran | ❌ false |
| push_enabled | ❌ false |
| D13 | ❌ false |
| V33 | ❌ false |
| HOURLY | ❌ false |
| strategy_changed | ❌ false |
| candidate_numbers_changed | ❌ false |
| validation_numbers_changed | ❌ false |
| cloud_publish | ❌ false |
