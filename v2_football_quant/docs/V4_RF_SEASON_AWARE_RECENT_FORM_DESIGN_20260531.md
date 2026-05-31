# V4 RF Season-Aware Recent Form Design Freeze (2026-05-31)

## 1. 目标与边界
本设计用于冻结 V4 RF 的 season-aware recent form 方案，确保 RF 在不同赛季阶段具备稳定可解释的降级保护。

本轮仅冻结设计，不改生产代码：
- 不修改 `engine/`
- 不重新扫描
- 不调用 API
- 不修改 official grade / cron / validation / live bet / QQ

## 2. 现状审计（只读）
当前已存在的相关能力：
- `recent10_window_days_home/away`
- `recent_freshness_status`（FRESH/NORMAL/STALE/EXPIRED）
- `recent_form_primary_level`（STRONG/MEDIUM/WEAK/LOW_SAMPLE/STALE_SAMPLE/EXPIRED_SAMPLE）
- `season_phase` 结构已在 runner 里写入，但尚未成为 RF 主窗口状态机

当前不足：
- 未形成“60天主窗口 + 赛季状态机”统一口径
- 未区分 ACTIVE_SEASON / SHORT_BREAK / EARLY_SEASON / POST_OFFSEASON_RETURN 的系统降级策略
- 未显式定义主流联赛优先与弱覆盖赛事保护

## 3. Season Phase 状态机（冻结）
本设计冻结以下状态：
1. `ACTIVE_SEASON`
2. `SHORT_BREAK`
3. `EARLY_SEASON`
4. `POST_OFFSEASON_RETURN`
5. `OFFSEASON`
6. `UNKNOWN`

### 3.1 状态判定口径（设计）
- `ACTIVE_SEASON`：近赛程连续、有效比赛密度正常
- `SHORT_BREAK`：存在短间歇但连续性未完全中断
- `EARLY_SEASON`：赛季初前 1-5 场
- `POST_OFFSEASON_RETURN`：休赛后恢复阶段（跨赛季重启）
- `OFFSEASON`：无有效联赛节奏，不适合强推近期样本
- `UNKNOWN`：数据不足或联赛元信息不足

## 4. Recent Form 窗口策略（冻结）

### 4.1 ACTIVE_SEASON（主窗口）
- 使用最近 `60天` 作为主窗口
- `recent10/recent5` 仅从主窗口中抽样
- 超出主窗口不参与主评分

### 4.2 SHORT_BREAK（放宽窗口）
- 可放宽到 `90天`
- 但必须施加降级保护：
  - A 最高降为 B
  - B 最高降为 C观察
  - C 可保留观察或 SKIP（按置信度）

### 4.3 EARLY_SEASON（前1-5场）
- 前 1-5 场禁止直接给 A
- 上限建议：
  - 强 RF + 强市场确认 -> B观察
  - 其余进入 C观察/SKIP
- 必须增加 early-season 风险标注

### 4.4 POST_OFFSEASON_RETURN
- 旧赛季数据仅作 baseline，不直接参与主评分打分
- 当期有效样本不足时：
  - 不允许升 A
  - 允许 B/C 观察
  - 明确 `POST_OFFSEASON_BASELINE_ONLY`

### 4.5 OFFSEASON / UNKNOWN
- 默认风险偏高：
  - 不给 A
  - 仅 C观察或 SKIP

## 5. 联赛优先级策略（冻结）

### 5.1 主流一级联赛 / 五大联赛
- 优先级最高（英超/西甲/意甲/德甲/法甲 + 主流一级联赛）
- 在样本充分且窗口有效时，允许更稳健保留 B

### 5.2 弱覆盖联赛 / 友谊赛 / U系列
- 必须降级保护：
  - 禁止直接升 A
  - 强 RF 也仅保留 B/C观察
  - 缺盘口或样本异常时更倾向 C/SKIP

## 6. 新增字段（设计冻结）
建议新增（后续实施阶段再落代码）：
- `season_phase_state`
- `season_phase_reason`
- `recent_form_window_mode`（`D60_PRIMARY` / `D90_SHORT_BREAK` / `BASELINE_ONLY`）
- `recent_form_window_days_applied`
- `recent_form_window_sample_count`
- `early_season_guard_active`
- `post_offseason_baseline_only`
- `league_tier_priority`
- `season_aware_rf_adjustment`
- `season_aware_rf_reason`

## 7. 与现有规则的兼容约束
- RF 仍为主因子
- H2H 仅 bonus-only（不降级、不硬杀）
- Opening Market 仅确认/降级/风险提示/极端熔断
- 不允许全场盘口冒充半场盘口
- 不改变 official grade 与 DEFAULT_RULES

## 8. 实施分期（设计冻结）
- Phase S1：字段落盘与只读透传（不改判级）
- Phase S2：窗口策略接入 shadow grade
- Phase S3：联赛优先与弱覆盖降级接入
- Phase S4：dryrun/replay 对比与 guard 扩展
- Phase S5：BOSS 单独授权后再讨论生产切换

## 9. 非目标（本轮）
- 不做 runtime 改造
- 不做扫描验证
- 不做 API 回放
- 不出正式推荐

