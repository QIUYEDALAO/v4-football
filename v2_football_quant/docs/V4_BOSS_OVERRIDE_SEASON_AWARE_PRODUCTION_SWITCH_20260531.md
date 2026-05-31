# V4 BOSS Override Production Switch (2026-05-31)

## 1. 变更性质
本次为 **BOSS_OVERRIDE_PRODUCTION_SWITCH_NOW**。

- 不是 readiness pack
- 不是继续观察
- 不是 shadow-only
- 不是 RF-SA-5/6/7 常规等待路径

本次目标：允许将 RF-SA-4 的 season-aware shadow grade 接入官方出口（带回滚）。

## 2. 核心模式与回滚
新增/启用正式评级模式开关：

- production mode: `season_aware_rf`
- rollback mode: `official_legacy`
- 环境变量：`V4_PRODUCTION_GRADE_MODE`

默认：`season_aware_rf`（本次 BOSS override）
回滚：显式切回 `official_legacy`

## 3. 正式评级来源
在 `season_aware_rf` 下：

- `official_grade_source = market_adjusted_shadow_grade`
- `official_grade = market_adjusted_shadow_grade`（经过守卫修正）

守卫修正包含：

1. `MARKET_EXTREME_VETO`：唯一直接 `SKIP`
2. `MARKET_NO_DATA/MARKET_NO_MARKET`：不能升 A（A 将降级）
3. `TIER_4_NON_FORMAL`：不允许 A/B 正式推荐
4. `POST_OFFSEASON_RETURN + baseline_only`：不允许 A/B
5. `UNKNOWN/UNKNOWN_TIER`：不允许强升格到 A
6. H2H 维持 add-only，`H2H_LOW_SAMPLE` 只标注不降级

## 4. pending / QQ 路由边界
pending 写入条件（最终进入 A/B 列表）：

- grade in A/B
- `official_permission=true`
- 非 `MARKET_EXTREME_VETO`
- 非 `TIER_4_NON_FORMAL` 强阻断
- 非 baseline-only 误升格

QQ 路由（本轮仅 guard，不真实推送）：

- 仅允许 official A/B
- block shadow-only
- block dryrun
- `allowed_to_send` 仍受 `--no-push` + `V4_QQ_ENABLED` 硬门控制

## 5. 本轮明确未做
1. 未删除 `official_legacy`
2. 未删除 RF-SA shadow/dryrun 链路
3. 未修改 watchdog kill/retry 机制
4. 未重算 validation
5. 未修改 live bet 原始记录
6. 未真实推 QQ
7. 未执行 API 全量扫描
8. 未把 C 观察写成主推荐

## 6. 上线后观察点
上线扫描后必须重点看：

1. `candidate_view` 的 A/B 是否按新守卫生效
2. `official_grade_source` 是否正确落地
3. `pending_bet_candidates` 是否仅 A/B
4. `qq_route_guard` 是否仍阻断 shadow-only/dryrun
5. watchdog 心跳是否正常
6. runtime status 是否无异常 blocker

## 7. 回滚步骤
如发现风险，立即执行回滚：

1. 运行扫描时显式设置：`--production-grade-mode official_legacy`
2. 或设置环境变量：`V4_PRODUCTION_GRADE_MODE=official_legacy`
3. 保持 `collection_mode` 与 cron 其他参数不变
4. 复跑 production switch checker

