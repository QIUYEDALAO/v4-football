# GATEWAY CRON LEGACY QUARANTINE INVENTORY 2026-05-21

## A. KEEP_ACTIVE (11)

| # | ID | Name | Schedule | Kind | Delivery | Enabled |
|:-:|:---|:---|:---:|:---:|:---:|:---:|
| 1 | 8e7abfa6 | V4赛中快照 | */3 18-23,0-11 * * * | agentTurn | none | ✅ |
| 2 | 853e0db4 | V2窗口检查器 | 5,35 * * * * | agentTurn | none | ✅ |
| 3 | 73ef5647 | V2建池-每日 | 15 13 * * * | agentTurn | none | ✅ |
| 4 | e1ad23c5 | V2 DAILY_POOL Health Check | 18 13 * * * | systemEvent | none | ✅ |
| 5 | 2c0a07f2 | V2每日结算 | 10 12 * * * | agentTurn | none | ✅ |
| 6 | f7bee1b6 | V4每日复盘 | 35 12 * * * | agentTurn | none | ✅ |
| 7 | 9abd753b | SYS每日结算汇总 | 0 13 * * * | agentTurn | none | ✅ |
| 8 | af94e533 | 每日状态更新 | 25 17 * * * | systemEvent | none | ✅ |
| 9 | 3caf9d28 | V2每日状态回执 | 45 23 * * * | systemEvent | none | ✅ |
| 10 | fe290fa0 | V4周报 | 20 11 * * 1 | agentTurn | none | ✅ |
| 11 | 9524c151 | V4月报 | 20 13 1 * * | agentTurn | none | ✅ |

## B. KEEP_STATUS_ONLY (1)

| # | ID | Name | Schedule | Kind | Delivery | Enabled |
|:-:|:---|:---|:---:|:---:|:---:|:---:|
| 1 | 41a21ce1 | SYS-架构审计守卫 | 40 8,17,23 * * * | agentTurn | none ✅ | ✅ |

## C. QUARANTINE_DISABLE (13)

| # | ID | Name | Schedule | Reason | Action |
|:-:|:---|:---|:---:|:---|:---:|
| 1 | e1863187 | V4扫描-早场 | 20 7 * * * | legacy multi-window scan | disable |
| 2 | 708f26f9 | V4扫描-午间 | 5 14 * * * | legacy multi-window scan | disable |
| 3 | 0443f80e | V4扫描-傍晚 | 20 16 * * * | legacy multi-window scan | disable |
| 4 | b022bce3 | V4扫描-晚间 | 20 22 * * * | legacy multi-window scan | disable |
| 5 | 4450d249 | V4扫描-凌晨 | 20 1 * * * | legacy multi-window scan | disable |
| 6 | 95676a5c | V4_MIDDAY_ONE_SHOT_20260520 | 5 14 * * * | expired one-shot, deleteAfterRun=true | delete |
| 7 | 82b6d42b | V4_EVENING_ONE_SHOT_20260520 | 20 16 * * * | expired one-shot, deleteAfterRun=true | delete |
| 8 | b9c4fa16 | V4_NIGHT_ONE_SHOT_20260520 | 20 22 * * * | expired one-shot, deleteAfterRun=true | delete |
| 9 | acaa39be | V4午间最后验收 | 45 14 * * * | legacy one-shot, deleteAfterRun=true | delete |
| 10 | 87ef5f92 | V2早场兜底 | 35 7 * * * | legacy fallback | disable |
| 11 | a98353aa | V2晚场兜底 | 35 18 * * * | legacy fallback | disable |
| 12 | 50e63276 | V2夜间兜底 | 35 23 * * * | legacy fallback | disable |
| 13 | ce082e9d | V2每日结算-补跑 | 37 15 * * * | legacy catchup | disable |

## D. SYSTEM_CRONTAB_REVIEW

| Name | Schedule | Status |
|:---|:---:|:---:|
| pre_match_reminder.py | */2 * * * * | REVIEW — check for QQ/state/V33/D13/HOURLY |

---

## Quarantine Metadata

```
quarantine_reason=legacy_multi_window_or_old_fallback
quarantine_date=20260521
boss_directive=true
disable_priority=1  (prefer disable over delete for non-expired)
delete_for_expired_oneshot=confirmed_done
