# V4 需要 APIFOOTBALL_KEY 的任务清单

> 你可以先完成所有离线任务；下面这些命令需要 `APIFOOTBALL_KEY` 才能跑。

## 0) 环境变量

```bash
export APIFOOTBALL_KEY='你的key'
```

可加到 `~/.zshrc` 持久化。

## 1) 赛前扫描（会调用 fixtures/odds/h2h/predictions 等 API）

```bash
python3 engine/v4_runner.py --run_tag PROD --lookahead-hours 24 --scan-mode fast --recent-prewarm off
```

## 2) HT 走地监控（会调用 fixtures/odds/live/statistics/events）

```bash
python3 engine/live_ht_over_monitor.py --date 20260512 --watch --interval 30
```

## 3) HT 自动结算（会调用 fixtures）

```bash
python3 engine/v4_ht_result_verifier.py --date 20260512 --watch --interval 300
```

## 4) SH 评估（会调用 fixtures/odds/live/statistics/events）

```bash
python3 engine/second_half_evaluator.py --date 20260512 --watch --interval 300
```

## 5) SH 自动结算（会调用 fixtures）

```bash
python3 engine/v4_sh_result_verifier.py --date 20260512 --watch --interval 600
```

## 6) 总控（在线模式）

```bash
python3 engine/v4_master_run.py --date 20260512 --phase full
```

## 7) 总控（离线模式，不需要 KEY）

```bash
python3 engine/v4_master_run.py --date 20260512 --phase reports --offline
```
