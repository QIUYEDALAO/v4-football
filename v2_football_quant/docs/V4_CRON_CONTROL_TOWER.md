# V4 Cron Control Tower (job_runner 统一包装)

以下命令全部通过 `v4_job_runner.py` 执行，自动具备：
- 任务锁（防重复）
- heartbeat
- 运行日志
- exit code 记录

## 1) 推荐 Crontab

> 假设工作目录：`/Users/liudehua/.openclaw/workspace/v2_football_quant`

```cron
# 12:05 午间扫描
5 12 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name v4_scan_noon --tier system -- \
python3 engine/v4_runner.py --scan-mode fast --lookahead-hours 24 --recent-prewarm off

# 16:05 傍晚扫描
5 16 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name v4_scan_evening --tier system -- \
python3 engine/v4_runner.py --scan-mode fast --lookahead-hours 24 --recent-prewarm off

# 17:30 采集调度（生成 A/B/C 任务）
30 17 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name v4_capture_scheduler --tier system -- \
python3 engine/v4_live_capture_scheduler.py --date $(date +\%Y\%m\%d) --profile may_sprint --budget 75000 --rate-limit 350 --lookback-days 7 --lookahead-days 2 --min-b 120 --min-c 80

# 18:00-23:59 A 层采集（每2分钟）
*/2 18-23 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name A_candidate_capture --tier A_candidate --heartbeat-sec 10 -- \
python3 engine/v4_live_odds_collector.py --date $(date +\%Y\%m\%d) --profile may_sprint --tier A_candidate --task-file data/live_monitor/v4_capture_tasks_$(date +\%Y\%m\%d).json --once --budget-aware

# 18:00-23:59 B 层采集（每2分钟）
*/2 18-23 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name B_shadow_capture --tier B_shadow --heartbeat-sec 10 -- \
python3 engine/v4_live_odds_collector.py --date $(date +\%Y\%m\%d) --profile may_sprint --tier B_shadow --task-file data/live_monitor/v4_capture_tasks_$(date +\%Y\%m\%d).json --once --budget-aware

# 18:00-23:59 C 层采集（每5分钟）
*/5 18-23 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name C_slice_capture --tier C_slice --heartbeat-sec 10 -- \
python3 engine/v4_live_odds_collector.py --date $(date +\%Y\%m\%d) --profile may_sprint --tier C_slice --task-file data/live_monitor/v4_capture_tasks_$(date +\%Y\%m\%d).json --once --budget-aware

# 预算审计（每30分钟）
*/30 18-23 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name v4_budget_audit --tier system -- \
python3 engine/v4_api_budget_audit.py --date $(date +\%Y\%m\%d) --hard-limit 75000

# 采集审计（每30分钟）
*/30 18-23 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name v4_capture_audit --tier system -- \
python3 engine/v4_live_capture_audit.py --date $(date +\%Y\%m\%d)

# 告警（每30分钟）
*/30 18-23 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name v4_ops_alert --tier system -- \
python3 engine/v4_ops_alert.py --date $(date +\%Y\%m\%d)

# 监控看板（每30分钟）
*/30 18-23 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name v4_ops_dashboard --tier system -- \
python3 engine/v4_ops_dashboard.py --date $(date +\%Y\%m\%d)

# 月度进度（每天 23:40）
40 23 * * * cd /Users/liudehua/.openclaw/workspace/v2_football_quant && \
python3 engine/v4_job_runner.py --job-name v4_validation_progress --tier system -- \
python3 engine/v4_validation_progress.py --month $(date +\%Y\%m)
```

## 2) 监控命令

```bash
python3 engine/v4_ops_status.py --date $(date +%Y%m%d)
python3 engine/v4_ops_alert.py --date $(date +%Y%m%d)
python3 engine/v4_ops_dashboard.py --date $(date +%Y%m%d)
python3 engine/v4_validation_progress.py --month $(date +%Y%m)
```

## 3) 关键输出目录

- `data/ops/job_runs/`
- `data/ops/heartbeats/`
- `data/ops/locks/`
- `data/ops/alerts/`
- `data/ops/validation_progress/`
- `logs/cron/`
