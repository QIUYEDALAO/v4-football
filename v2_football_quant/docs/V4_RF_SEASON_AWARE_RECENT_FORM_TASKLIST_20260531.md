# V4 RF Season-Aware Recent Form Tasklist (2026-05-31)

## 0. 任务性质与边界
本清单用于后续实施排期，不代表本轮立即改代码。

本轮冻结约束：
- 不修改 `engine/`
- 不重新扫描
- 不调用 API
- 不修改 official grade
- 不修改 `DEFAULT_RULES`
- 不修改 cron
- 不重算 validation
- 不修改 live bet
- 不推 QQ

## 1. Phase S1 — 字段与状态机透传（只读层）
目标：把 season-aware 关键信息写入 shadow 字段，先可观测，不改官方判级。

待办：
1. 新增/统一 `season_phase_state`、`season_phase_reason`。
2. 新增 `recent_form_window_mode`、`recent_form_window_days_applied`。
3. 新增 `recent_form_window_sample_count`。
4. 新增 `early_season_guard_active`。
5. 新增 `post_offseason_baseline_only`。
6. 新增 `league_tier_priority`。
7. 新增 `season_aware_rf_adjustment`、`season_aware_rf_reason`。
8. 透传至 scout/candidate_view/dashboard model（仅展示，不改官方逻辑）。

验收：
- 新字段可读。
- 不出现 undefined/null/NaN。
- official grade、todo_count、pending_bet_candidates 不变。

## 2. Phase S2 — 60天主窗口 + 90天短间歇降级（shadow）
目标：把窗口策略接入 RF shadow grade，不写回 official。

待办：
1. ACTIVE_SEASON 使用 60 天主窗口。
2. SHORT_BREAK 可放宽到 90 天。
3. SHORT_BREAK 启用降级保护（A->B，B->C观察上限）。
4. 保留窗口原因字段，避免黑盒。

验收：
- 窗口模式与天数可追踪。
- 仅影响 shadow 字段，不覆盖 `grade`/`official_grade`。

## 3. Phase S3 — 早赛季与休赛回归保护（shadow）
目标：降低 early/offseason 误判风险。

待办：
1. EARLY_SEASON（前1-5场）限制 A，上限 B观察。
2. POST_OFFSEASON_RETURN 旧赛季仅 baseline。
3. OFFSEASON/UNKNOWN 默认降风险（不升 A）。
4. 输出保护触发原因，支持人工复盘。

验收：
- EARLY_SEASON 不直出 A。
- POST_OFFSEASON_RETURN 有 baseline-only 标记。
- 官方评分不变。

## 4. Phase S4 — 联赛优先与弱覆盖降级（shadow）
目标：主流联赛优先稳定，弱覆盖赛事防激进。

待办：
1. 五大联赛/主流一级联赛定义优先 tier。
2. 弱覆盖联赛/友谊赛/U系列应用降级保护。
3. 样本不足或盘口缺失时保守化。
4. 在 dashboard 给出中文原因解释。

验收：
- 主流联赛与弱覆盖赛事策略可区分。
- 弱覆盖赛事不因短样本误升 A。

## 5. Phase S5 — Guard 与回归检查
目标：保证“只做 shadow，不动 official 生产链路”。

待办：
1. 新增 season-aware 专项 checker。
2. 检查 no-regrade/no-validation/no-live-bet/no-QQ。
3. 检查 cron 仍是 official_legacy。
4. 检查 DEFAULT_RULES 与 A/B 阈值未改。
5. 检查 runtime 业务产物不提交。

验收：
- 关键 checker PASS。
- 安全红线全部保持。

## 6. Phase S6 — 观察与授权门
目标：形成进入下一阶段前的决策门。

待办：
1. 连续多日对比 official vs shadow 差异。
2. 记录样本覆盖率与稳定性。
3. 形成“是否推进”的书面结论。
4. 仅在 BOSS 单独授权后讨论正式切换。

验收：
- 未获得单独授权前，不切换生产默认。

## 7. 风险清单
1. 早赛季样本稀疏导致误升风险。
2. 短间歇跨窗数据污染风险。
3. 弱覆盖赛事元数据不稳定风险。
4. 规则解释不透明导致误操作风险。

缓解策略：
- 所有风险只先落在 shadow 字段。
- 所有关键路径配套 guard checker。
- 所有可疑场景输出中文原因，便于人工复盘。

## 8. 交付物清单
1. `docs/V4_RF_SEASON_AWARE_RECENT_FORM_DESIGN_20260531.md`
2. `docs/V4_RF_SEASON_AWARE_RECENT_FORM_TASKLIST_20260531.md`

