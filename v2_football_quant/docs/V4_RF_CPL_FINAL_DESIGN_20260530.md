# V4-RF-CPL 最终设计文档

版本：v1
日期：2026-05-30
状态：DESIGN_FREEZE（只读设计，未实现）

---

## 1. 当前系统基线

| 项目 | 状态 |
|------|------|
| 生产扫描口 | 57 联赛 whitelist（`--fixture-universe whitelist` 默认） |
| all_eligible | ❌ 不再是正式默认 |
| 缓存清理 | 已完成 |
| 废弃归档 | 已完成 |
| DEFAULT_RULES | 未改（hash `2d7df88`） |
| A/B 阈值 | 未改 |
| H2H 逻辑 | 未改 |
| NO_MARKET | 已保留，validator core skip 完成 |
| true goal distribution | 已保留 |
| playbook_script | 已保留 |
| Dashboard | 可读 |
| Validation 历史 | 未改 |
| Live bet 记录 | 未改 |

---

## 2. 为什么从 H2H 主导改为 Recent Form 主导

当前 V4 正式评级体系中，H2H（历史交锋）仍然是最重要因子之一：

- A 级要求 `min_h2h_ht_goal_rate >= 0.65`
- B 级要求 `min_h2h_ht_goal_rate >= 0.55`
- SKIP 硬阈值 `min_h2h_ht_goal_rate < 0.50`
- H2H 样本不够时降级

问题：

1. **H2H 本质是历史数据**。跨赛季、跨阵容的交锋记录对当前比赛预测力有限。
2. **Recent Form 才是实时信号**。近10场的上半场参与率直接反映当前球队状态。
3. **H2H 样本在某些联赛极少**。57 白名单中部分联赛 H2H < 10 场，统计意义弱。
4. **H2H 高但有降温信号**。H2H 历史高但近期双方状态下滑时，H2H 主导会给出错误信号。

新设计将 Recent Form 作为主导因子，H2H 降级为辅助参考。

---

## 3. 为什么近10做主口径

- **last10 是公认的最小统计样本量**（n >= 10 才有统计意义）。
- 跨度为 2-3 个赛月的比赛周期，能覆盖球队状态周期变化。
- 赛季中期覆盖约 1/3 赛季，信息量充足。
- **last5 只做动量修正**，不做主评分，避免小样本噪音。

---

## 4. 为什么近5只做动量

- last5 样本太小，单独做主评分会过度拟合近期 1-2 场表现。
- 但近5场相对近10场的变化方向有参考价值：
  - **稳定**：近5无显著变化
  - **升温**：近5明显好于近10
  - **降温**：近5明显差于近10
- 动量修正幅度：±5~10% 的评分调整，不反转近10主信号。

---

## 5. H2H Assist 设计

### 新角色

H2H 从"硬门槛"降级为"辅助因子"：

| 当前 | 新版 |
|------|------|
| H2H 不足直接 SKIP | H2H 不足只提醒 |
| H2H 达标才进 A/B | 主要看 recent form |
| H2H 高强行拉高评分 | H2H 强只加分 |
| H2H 低强行拉低评分 | H2H 弱只降级或提醒 |

### 字段

```
h2h_assist_status: H2H_STRONG / H2H_NEUTRAL / H2H_WEAK / H2H_LOW_SAMPLE / H2H_STALE / H2H_IGNORED
h2h_assist_strength: float (0-100)
h2h_assist_reason: string
h2h_sample_age_status: FRESH / MODERATE / STALE / EXPIRED
h2h_low_sample: bool
h2h_conflict_with_recent_form: bool (H2H 与 RF 信号相反时标记)
h2h_downgrade_applied: bool
```

### 规则

1. H2H 样本 >= 10 且最近交锋在 2 年内 → `H2H_STRONG`，加分
2. H2H 样本 >= 5 但 < 10 → `H2H_LOW_SAMPLE`，仅参考
3. H2H 样本 >= 10 但最近交锋在 2 年前 → `H2H_STALE`，不参与
4. H2H 样本 < 5 → `H2H_IGNORED`
5. H2H 强弱与 RF 方向一致 → 加分叠加
6. H2H 强弱与 RF 方向相反 → 标记 conflict，不硬杀
7. H2H 强但 RF 弱 → **RF 优先**，H2H 不强拉
8. H2H 弱但 RF 强 → **RF 主导**，H2H 不降级

---

## 6. 双边活跃路线

### 目标场景

双方近期上半场进球积极性都较高，形成"双边互爆"预期。

### 字段

```
home_recent10_fh_involved_rate
away_recent10_fh_involved_rate
combined_recent10_fh_involved_rate
home_recent5_fh_involved_rate
away_recent5_fh_involved_rate
combined_recent5_momentum
route_type: BILATERAL_ACTIVE
```

### A 级草案

- combined_recent10_fh_involved_rate >= 70%
- combined_recent5 >= 60%（未明显降温）
- 近10双方各自 FH involved rate >= 60%
- late_fh_pressure >= 0.50（下半段前压支持）
- HT_LIVE_OVER 评分 >= 65
- 无 CPL_CRITICAL

### B 级草案

- combined_recent10_fh_involved_rate >= 60%
- combined_recent5 >= 55%
- HT_LIVE_OVER >= 55
- 无 CPL_HEAVY

### SKIP 条件

- combined_recent10_fh_involved_rate < 55%
- 双方或一方 FH involved rate < 50%
- CPL_CRITICAL

---

## 7. 强队单边压制路线

### 目标场景

主队或客队明显强势（让球深盘），强队上半场进球能力强，弱队上半场失球多。

### 字段

```
dominant_favorite_route: bool
favorite_side: HOME / AWAY
favorite_handicap_line: float (负值表示让球)
favorite_recent10_fh_score_rate
favorite_recent5_fh_score_rate
underdog_recent10_fh_concede_rate
underdog_recent5_fh_concede_rate
dominant_favorite_score
dominant_favorite_level
dominant_favorite_reason
favorite_early_pressure_rate (11-45分钟)
```

### A 级草案

- handicap <= -1.75
- favorite recent10 FH score rate >= 70%
- favorite recent5 FH score rate >= 60%
- underdog recent10 FH concede rate >= 65%
- underdog recent5 FH concede rate >= 60%
- 半场盘口支持
- 无 CPL_CRITICAL / CPL_HEAVY

### B 级草案

- handicap <= -1.5
- favorite recent10 FH score rate >= 60%
- underdog recent10 FH concede rate >= 60%
- 近5未明显降温
- 盘口不冲突

### SKIP 条件

- favorite FH score rate 低
- underdog FH concede rate 低
- 半场盘口不支持
- CPL_CRITICAL

---

## 8. Market / Time Bin / Playbook 角色

### Market

- `prematch_ht_line`：上半场大小球盘口，判断盘口支持度
- `prematch_over_odds`：上半场大球赔率
- handicap（让球盘）：双边活跃 vs 强队单边压制路线判断的关键输入
- 盘口深度（让球 >= 1.5）触发 DF 路线判断
- 盘口不支持时降级

### Time Bin

- `fh_goals_0_15 / 16_30 / 31_45`：真实进球时间分布
- 来源：`events_goal_counts`（事件统计）或 H2H 回退
- `late_fh_pressure`（11-45分钟压力）：判断后期进球概率
- `time_bin_hotspot`：热点时段文本

### Playbook

- `_script_type_from_bins(time_bins)` 生成剧本标签
- 标签：中段发力 / 尾段压迫 / 双段压迫 / 早球型 / 均衡型
- 用作路线判断补充（如早球型配合 DF 路线）

---

## 9. CPL 战力损耗熔断

### 字段

```
combat_power_loss_status: CPL_NONE / CPL_LIGHT / CPL_MEDIUM / CPL_HEAVY / CPL_CRITICAL / CPL_UNKNOWN
combat_power_loss_score: float (0-100)
combat_power_loss_reason: string
combat_power_loss_source: API_INJURY / API_LINEUP / MANUAL_MARKER
combat_power_loss_confidence: HIGH / MEDIUM / LOW
home_cpl_level: str
away_cpl_level: str
pre_cpl_grade: str
post_cpl_grade: str
cpl_downgrade_applied: bool
cpl_kill_switch_triggered: bool
```

### 等级定义

| 等级 | 含义 | 动作 |
|------|------|------|
| CPL_NONE | 无损耗 | 不调整 |
| CPL_LIGHT | 轻伤/轮换 | 提示 |
| CPL_MEDIUM | 核心 1-2 人缺阵 | 降一级 |
| CPL_HEAVY | 核心 2-3 人缺阵 | 降 1-2 级 |
| CPL_CRITICAL | 核心 >= 3 人或核心射手缺阵 | 杀 |
| CPL_UNKNOWN | 无数据 | 不动作 |

### 熔断表

| pre_grade | CPL_MEDIUM | CPL_HEAVY | CPL_CRITICAL |
|-----------|-----------|-----------|-------------|
| A | B | C | SKIP |
| B | C | SKIP | SKIP |
| C | C | SKIP | SKIP |

### 规则

1. 只降级不升级。
2. `confirmed_out / suspended / confirmed_lineup_absent` 才能硬熔断。
3. `doubtful` 只提示或轻降级。
4. `UNKNOWN` 不硬杀。
5. SKIP 不因对手伤停升级。

---

## 10. NO_MARKET 与 COMBAT_POWER_LOSS 人工排除

### NO_MARKET（已实现）

- 数据源：`data/runtime/live_bets/v4_no_market_exclusions_*.jsonl`
- Validator core skip：`_load_no_market_excluded_fixtures()` → line 290-291
- 排除影响：验证、统计
- 不影响：候选原始记录

### COMBAT_POWER_LOSS（待实现）

- 数据源：`data/runtime/live_bets/v4_combat_power_loss_exclusions_*.jsonl`
- 字段同 NO_MARKET 结构 + `missing_players` / `loss_reason`
- append-only，fixture_id + scan_date 幂等去重
- 不物理删除 candidate/scout
- 不进 validation pending
- 不拉赛果
- 不进统计分母
- 与 NO_MARKET 机制兼容

---

## 11. Dashboard 展示设计

### 候选列表主行

```
时间 | 等级 | 联赛 | 对阵 | 路线 | 剧本 | 进球分布 | 战力 | 状态 | 操作
```

### 展开区

- 正式评级
- RF路线：双边活跃 / 强队单边压制
- 近10 FH参与率
- 近5 FH参与率
- 样本跨度
- H2H辅助状态
- 盘口支持
- 真实进球分布（0-15 / 16-30 / 31-45）
- 战力损耗状态
- NO_MARKET 按钮
- 战力熔断按钮
- 保存投注
- 早进球未投

### 要求

1. 不破坏当前列表布局。
2. 不恢复大卡片。
3. 进球分布必须完整显示 0-15 / 16-30 / 31-45。
4. 状态显示 NO_MARKET / COMBAT_POWER_LOSS / BET_PLACED / EARLY_GOAL_NOT_BET。
5. dashboard 只展示 official grade，不重算 official grade。

---

## 12. Validation / Stats 过滤设计

### 过滤规则

| 状态 | 进 validation | 进命中率统计 | 进投注待办 |
|------|-------------|-------------|-----------|
| 正常 A/B 候选 | ✅ | ✅ | ✅ |
| NO_MARKET 排除 | ❌ | ❌ | ❌ |
| COMBAT_POWER_LOSS | ❌ | ❌ | ❌ |
| BET_PLACED | ✅ | ✅ | ❌（已处理） |
| EARLY_GOAL_NOT_BET | ✅ | ✅ | ❌（已处理） |

### 规则

1. validation 只处理 A/B（正式候选）。
2. SKIP 不进 validation。
3. C 不进 validation。
4. NO_MARKET 排除不进 validation。
5. COMBAT_POWER_LOSS 排除不进 validation。
6. 排除不影响原始候选记录。
7. 排除不影响 source-of-truth 验证分母。

---

## 13. 字段清单

### RF 字段（新增）

```
home_recent10_fh_involved_rate
away_recent10_fh_involved_rate
combined_recent10_fh_involved_rate
home_recent10_fh_score_rate
away_recent10_fh_score_rate
home_recent10_fh_concede_rate
away_recent10_fh_concede_rate
recent10_sample_count_home
recent10_sample_count_away
recent10_window_days_home
recent10_window_days_away
recent_freshness_status
home_recent5_fh_involved_rate
away_recent5_fh_involved_rate
combined_recent5_fh_involved_rate
home_recent5_fh_score_rate
away_recent5_fh_score_rate
home_recent5_fh_concede_rate
away_recent5_fh_concede_rate
recent5_momentum_status
recent_form_primary_score
recent_form_primary_level
recent_form_primary_reason
```

### H2H Assist 字段（新增）

```
h2h_assist_status
h2h_assist_strength
h2h_assist_reason
h2h_sample_age_status
h2h_low_sample
h2h_conflict_with_recent_form
h2h_downgrade_applied
```

### DF 字段（新增）

```
dominant_favorite_route
favorite_side
favorite_handicap_line
favorite_recent10_fh_score_rate
favorite_recent5_fh_score_rate
underdog_recent10_fh_concede_rate
underdog_recent5_fh_concede_rate
dominant_favorite_score
dominant_favorite_level
dominant_favorite_reason
```

### CPL 字段（新增）

```
combat_power_loss_status
combat_power_loss_level
combat_power_loss_score
combat_power_loss_reason
combat_power_loss_source
combat_power_loss_confidence
home_cpl_level
away_cpl_level
pre_cpl_grade
post_cpl_grade
cpl_downgrade_applied
cpl_kill_switch_triggered
home_missing_core_players
away_missing_core_players
```

---

## 14. 阶段实施路线

| 阶段 | 内容 | 修改文件 | 是否改正式评级 |
|------|------|---------|-------------|
| Phase 0 | 系统精简 + whitelist 基线 | 已完成 | ❌ |
| Phase 1 | 新增 RF 字段计算，不改评级 | engine/v4_runner.py | ❌ |
| Phase 2 | 新增 RF shadow grade（不生效） | engine/v4_match_intelligence.py | ❌ |
| Phase 3 | 新增 H2H Assist shadow | engine/v4_match_intelligence.py | ❌ |
| Phase 4 | 新增 DF shadow route | engine/v4_match_intelligence.py | ❌ |
| Phase 5 | 新增 CPL shadow guard | engine/v4_match_intelligence.py | ❌ |
| Phase 6 | 新增 COMBAT_POWER_LOSS marker | tools/serve_live_bet_tracker.py | ❌ |
| Phase 7 | Dashboard 展示 RF/DF/H2H/CPL | dashboard template | ❌ |
| Phase 8 | BOSS 审核 shadow 输出 | — | ❌ |
| Phase 9 | **正式切换 V4-RF-CPL** | 多个 | ✅ |
| Phase 10 | 新版 rolling validation | validator | ❌ |

---

## 15. 风险与回滚方案

### 风险

1. **数据源不足**：低级别联赛 recent form 可能有小样本问题（< 10 场有效数据）。
2. **API 伤病接口不稳定**：CPL 依赖的 injury/lineup 数据可能不完整或延迟。
3. **H2H 弱化后遗漏信号**：部分联赛中 H2H 确实是强信号（如德比、长期对峙），完全忽略可能误判。
4. **阈值调优需要时间**：RF 路线的 A/B/SKIP 阈值需要通过 shadow 阶段观察后确定。

### 回滚方案

1. **Phase 1-7（shadow 阶段）**：不修改正式评级，直接删除 shadow 字段即可回滚。
2. **Phase 9（正式切换）**：恢复 `DEFAULT_RULES` 旧值，切换回原评级逻辑。
3. **Phase 10（新版 validation）**：旧 validation 数据不动，只加新统计。

---

*文档结束 — 只读设计，未实现。*
