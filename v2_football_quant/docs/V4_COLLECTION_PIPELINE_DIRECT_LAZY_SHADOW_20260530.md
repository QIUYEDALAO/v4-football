# V4_COLLECTION_PIPELINE_DIRECT_LAZY_SHADOW_20260530

## 1. 本轮性质
本轮是直接代码实施，不是任务清单调整。
目标是新增显式可控的 `rf_lazy_shadow` 采集模式，用于在不改变正式默认链路的前提下验证 RF-first lazy collection。

## 2. 6d06be0 失败复盘
`6d06be0` 的核心问题是把 lazy gating 直接作用到正式扫描产物链路，导致多日期 `scout=0` 风险。

## 3. 本轮如何避免 scout=0
本轮新增硬保护：
- `h2h_required=false` 只跳过 H2H enrich，不删除 fixture。
- `events_required=false` 只跳过 events enrich，不删除 fixture。
- `cpl_required=false` 只做占位跳过，不删除 fixture。
- `rf_lazy_shadow` 分支每个 fixture 都写 universe/scout row。

## 4. collection-mode 默认
新增 `--collection-mode`，可选：
- `official_legacy`（默认）
- `rf_lazy_shadow`（仅显式启用）

默认仍是 `official_legacy`，不传参时行为等同当前正式生产路径。

## 5. rf_lazy_shadow 启用条件
只有显式传入：
`--collection-mode rf_lazy_shadow`
才启用新采集顺序。

## 6. --max-fixtures 边界
新增 `--max-fixtures N`，用于 no-push 小样本验收。
- 必须正整数。
- 在 fixture pool 阶段截断。
- 不改 cron 默认，不改正式生产默认。

## 7. lazy 规则落地
在 `rf_lazy_shadow` 下执行：
1. Fixture pool
2. Recent Form first
3. Opening Market before H2H
4. RF prefilter
5. Lazy H2H
6. Lazy Events / time-bin
7. Lazy CPL placeholder
8. Shadow finalized
9. Official unchanged

## 8. H2H / Events / CPL 行为
- H2H：由 RF+Market prefilter 决定是否查询，支持 `NO_MARKET` / `MARKET_HARD_VETO` / `RECENT10_BELOW_GATE` 等 skip reason。
- Events：只对 shadow 候选/待判定路线查询，非候选可跳过并记录 reason。
- CPL：仅占位，不启用正式熔断，不触发外部伤停调用。

## 9. 本轮不改 official grade
`rf_lazy_shadow` 仅追加 shadow collection 状态字段，不覆盖 `grade/official_grade`。

## 10. cron 未改
12:00 正式 cron 未切换到 `rf_lazy_shadow`，默认生产仍走 `official_legacy`。

## 11. validation 未改
本轮不触发 validation 重算，不修改 validation 历史。

## 12. QQ 未推
`V4_QQ_ENABLED = False` 仍硬禁用，no-push 验收不推送 QQ。

## 13. 非正式切换声明
本轮不代表正式生产切换。
后续若要将 lazy 模式用于正式 cron，必须由 BOSS 单独授权。
