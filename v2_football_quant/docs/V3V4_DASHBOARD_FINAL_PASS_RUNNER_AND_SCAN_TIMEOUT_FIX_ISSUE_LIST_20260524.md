# V3V4 Dashboard Final Pass Runner and Scan Timeout Fix Issue List - 20260524

Status: PASS

1. 14:00 final refresh 已进入计划。
2. tools/run_v3v4_dashboard_daily_update.py 缺少 --final-pass。
3. 无 --final-pass 时无法保证 14:00 source_hash 未变 NOOP。
4. 14:00 不得重跑 scan。
5. 14:00 不得重跑 validation。
6. 14:00 不得改 candidate。
7. 12:00 V4 scan 曾 600s timeout。
8. 12:00 scan timeout 需要正式配置口径。
9. cron 本轮不得启用。
10. checker 必须拦截 final-pass 缺失。

## Boundary

- No cron enable.
- No full V4 scan.
- No capture / QQ push / cloud publish.
- No git add / commit / push.
- No V2/V33/C/近7天 restoration.
