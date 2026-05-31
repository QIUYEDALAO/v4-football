# V4_RESCUE_THRESHOLD_MULTI_ARTIFACT_REPLAY_20260601

## 范围
本轮是 **Phase 3I — V4_RESCUE_THRESHOLD_73_5_CANDIDATE_MULTI_ARTIFACT_REPLAY**。  
目标是把 `73.5` 作为 **candidate threshold** 做 shadow-only 多 artifact 回放对比，不是正式切换。

## 核心原则
1. 默认 rescue threshold 仍是 `77`。  
2. `73.5` 仅用于 candidate replay 场景。  
3. 不修改 official grade / production_grade_mode。  
4. 不写 pending，不推 QQ。  
5. 不重算 validation，不修改 live bet。  
6. 不修改 cron。  
7. 不调用 API，不重扫。  

## Multi-artifact 回放能力
在 `tools/run_v4_rf_shadow_promotion_dryrun_replay.py` 增加：
- `--multi-artifact`
- `--artifact-glob`
- `--min-fixtures`（默认 `30`）
- `--baseline-threshold`（默认 `77`）
- `--candidate-threshold`（默认 `73.5`）

回放只读取本地已有 `data/daily_reports/scout_v4_*.json`。

## 样本策略
- `fixture_count >= 30`：`SAMPLE_SUFFICIENT`，可进入 aggregate 对比。  
- `fixture_count < 30`：`SAMPLE_TOO_SMALL_WARN_ONLY`，只记录，不进入 aggregate 结论。  

## official artifact 缺失处理
- 如果某日缺少 official candidate artifact，标记 `OFFICIAL_ARTIFACT_MISSING`。  
- 不得把 official 伪造为 `0/0/0/0`。  
- 该样本可进入 shadow 安全观察，但不进入 official-vs-shadow结论聚合。  

## 安全门（candidate 73.5）
每个 sufficient artifact 必须满足：
- `candidate_A_expansion = 0`
- `candidate_SKIP_to_B = 0`
- `candidate_market_alone = 0`
- `candidate_safety_violations = 0`

否则状态必须进入阻断，不得形成 promotion 口径。

## 结论口径
本轮输出的是 **candidate threshold review** 证据，不是上线授权。  
是否进入“调整默认阈值”阶段，必须 BOSS 后续单独授权并经 OpenClaw 只读验收。
