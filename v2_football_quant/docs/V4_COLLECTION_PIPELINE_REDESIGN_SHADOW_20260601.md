# V4 Collection Pipeline Redesign Shadow (Phase 3A)

日期：2026-06-01

## 目标
本阶段仅实现 **shadow collection gating**，把采集顺序从旧的 H2H-first 重构为：

1. Fixture Pool
2. Recent Form
3. Opening Market
4. RF PreFilter
5. Lazy H2H
6. Lazy Events / Time Bin
7. Lazy CPL (placeholder)
8. Shadow Finalize

## 边界
本阶段不做以下变更：

- 不改变 official grade
- 不改变 season_aware_rf official 出口
- 不改变 pending 写入逻辑
- 不推 QQ
- 不修改 cron
- 不重算 validation
- 不修改 live bet

## 关键字段
采集链路新增/确认以下字段：

- `collection_stage`
- `rf_collected`
- `market_collected`
- `prefilter_done`
- `h2h_required`
- `h2h_skipped_reason`
- `h2h_collected`
- `events_required`
- `events_skipped_reason`
- `events_collected`
- `cpl_required`
- `cpl_skipped_reason`
- `cpl_collected`
- `expensive_calls_saved`
- `collection_reason`

## 规则摘要

### Lazy H2H
- 仅 `h2h_required=true` 才执行 H2H。
- `NO_MARKET` / `MARKET_HARD_VETO` / 明显弱势等场景可跳过。
- `h2h_required=false` 不删除 scout row。
- H2H 保持 add-only 语义，不制造 A/B。

### Lazy Events
- 仅 A/B/C shadow 或 pending 重点候选启用。
- 明显 SKIP/弱势/无盘口可跳过。
- 跳过 events 不改变 official grade，不删除 scout row。

### Lazy CPL
- 本阶段仅占位，不启用正式熔断。
- 仅 A/B 或重点 C 置 `cpl_required=true`。
- 非候选/无盘口/弱势可跳过，不删除 scout row。

## 缓存与 API 成本
本阶段确认/使用以下缓存入口：

- Team Recent Form cache
- Pair H2H cache
- Opening Market cache
- Events cache
- CPL placeholder cache

通过 `expensive_calls_saved` 和 `collection_reason` 提供可解释的节省信息。

## Dashboard 映射
`build_v4_control_center_model.py` 已支持展示 collection 字段（含 H2H/events/CPL 跳过原因、estimated saved calls）。

## 验证与守卫
新增 checker：

- `tools/check_v4_collection_pipeline_redesign_shadow.py`

并联守卫：

- `tools/check_v4_season_aware_production_switch.py`
- `tools/check_v4_qq_enabled_gate.py`
- `tools/check_v4_season_aware_qq_brief_route.py`
- `tools/check_v4_production_default_rules_guard.py`

## 结论
Phase 3A 只覆盖 shadow collection 重构，不是 production promotion。
进入 Phase 3B（RF shadow grade）前，仍需 OpenClaw 只读验收通过。
