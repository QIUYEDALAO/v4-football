# V4 走地半场大球策略规则与任务清单

> 当前主线：V4_HT_LIVE_PULLBACK  
> 状态：规则冻结第 1 版，先纸盘验证，不接实盘  
> 核心纪律：赛前只建观察池，真正进场必须等待走地触发

## 一、策略定位

V4 的主策略不是赛前直接买上半场大球，而是：

```text
赛前筛选高概率上半场进球比赛
→ T-30 分钟确认首发阵容
→ 开赛 0-10 分钟无球则等待盘口自然回调
→ 盘口降到大 1.0 / 大 0.75 且水位合理时纸盘进场
→ 如果等待期间已经进球，跳过该场
```

策略名称：

```text
V4_HT_LIVE_PULLBACK
```

## 二、市场方向

系统目前分三类方向：

| 方向 | 含义 | 是否进入上半场滚球雷达 |
|:---|:---|:---:|
| HT_LIVE_OVER | 上半场走地大球主策略 | 是 |
| SECOND_HALF_OVER | 下半场大球参考 | 否 |
| FULLTIME_OVER | 全场大球参考 | 否 |

下半场和全场方向只做观察，不允许混入上半场走地主策略。

## 三、上半场走地入池门槛

V4 不再把 H2H 8/10 当成唯一硬门槛。新的判断顺序是：

```text
近期球队上半场能力 > 近期进球时间分布 > H2H参考 > 赛前盘口高开
```

一场比赛必须满足以下综合条件，才允许进入 `HT_LIVE_OVER`：

| 条件 | 门槛 |
|:---|:---|
| 双方近 5 场综合 HT 动能 | >= 70%，或攻防交叉威胁 >= 65% |
| 近期 10-45 分钟压力 | >= 50%，且不能是纯 0-10 闪击型 |
| H2H 参考 | 不作为唯一硬门槛，但若样本 >= 4 且 HT率 < 50% 则视为风险 |
| H2H 强信号 | 样本 >= 8 且 HT率 >= 75% 时加分 |
| HT 走地分 | >= 50，低分只做观察，不进入 HT 主策略 |
| 三方向一致性 | 评分最强方向必须是 HT_LIVE_OVER |
| 赛前半场大球盘口 | >= 大 1.25 |
| API 数据覆盖 | FULL / GOOD 才允许进入自动滚球监控 |

H2H 8/10 以后只代表强历史基因，不再直接决定入池。原因是交锋可能跨年份、换帅、换阵容，偶然性和过期噪音都比较大。

## 四、下半场/全场参考门槛

这两类只用于提醒我们“不要硬追上半场”，暂不作为主策略下注。

### SECOND_HALF_OVER

```text
H2H 下半场有球率 >= 70%
H2H 下半场场均进球 >= 0.8
双方近 5 场综合下半场动能 >= 70%
```

### FULLTIME_OVER

```text
H2H 全场 2+ 球率 >= 75%
H2H 全场场均进球 >= 2.0
双方近 5 场全场 2+ 综合动能 >= 70%
```

## 五、T-30 首发阵容闸门

开赛前 30 分钟，系统拉取首发名单，并用最近 10 场历史首发生成常规主力 XI。

阵容动作：

| 动作 | 含义 |
|:---|:---|
| BOOST | 攻击端可用，且存在防线缺口 |
| KEEP_WATCH | 阵容正常，继续观察 |
| WATCH_CAUTION | 阵容一般，降低优先级 |
| DROP_ATTACK_WEAK | 攻击端主力不足，移出观察 |
| DROP_HEAVY_ROTATION | 大轮换，移出观察 |
| LINEUP_PENDING | 首发未公布，保持等待 |
| LINEUP_UNKNOWN | 历史首发样本不足，阵容因子降权 |

主策略纪律：

```text
DROP_ATTACK_WEAK / DROP_HEAVY_ROTATION 不进入走地监控。
BOOST 只提高优先级，不允许绕过走地触发条件。
```

## 六、走地进场规则

开赛后：

```text
0-10 分钟有进球 → SKIP_EARLY_GOAL
0-10 分钟无进球 → 继续观察盘口
```

建议进场窗口：

```text
8-15 分钟
```

进场条件：

```text
当前比分 0-0
盘口降到大 1.0 或大 0.75
Over 水位在合理区间
无红牌
无重大伤退 / 长时间 VAR
比赛节奏不沉闷
```

初版水位范围：

```text
大 1.0：1.65 - 2.05
大 0.75：1.60 - 1.90
```

## 七、跳过规则

以下情况直接跳过：

```text
等待降盘过程中已经进球
盘口没有降到目标线
Over 水位异常过高
开场 10 分钟场面沉闷
出现红牌
出现重大伤退
首发大轮换
攻击核心缺失严重
```

## 八、当前已有功能

- [x] V4 扫描今天+明天白名单未开赛比赛
- [x] 支持 H2H 上半场/下半场/全场进球画像
- [x] 拆分 HT / SH / FT 三套独立评分
- [x] 加入 10-45 分钟进球分布指标
- [x] 增强近期球队 HT 进球/失球动能
- [x] 上半场入池改为近期优先，H2H 只做参考和风险控制
- [x] 下半场/全场参考方向与上半场滚球雷达分离
- [x] 支持半场亚洲盘口 0.75 / 1.0 / 1.25 / 1.5
- [x] 仪表盘只显示大球赔率
- [x] 中文球队名展示
- [x] T-30 首发阵容闸门
- [x] V4 交互式网页仪表盘

## 九、后续任务清单

### 第一阶段：主策略闭环

- [x] 任务 1：统一 V4 策略规则文档
- [x] 任务 2：拆分 HT / SH / FT 三套独立评分
- [x] 任务 3：加入 10-45 分钟进球分布指标
- [x] 任务 4：增强近期球队 HT 进球/失球动能
- [x] 任务 5：实现 `live_ht_over_monitor.py`
- [x] 任务 5.5：建立 API-Football 数据覆盖检查器
- [x] 任务 6：建立 `/odds/live` 快照库
- [x] 任务 7：实现亚洲盘结算
- [x] 任务 8：扩展 `paper_trading.py` 支持 V4 走地结算

### 第二阶段：命中率优化

- [x] 任务 9：加入联赛 HT/SH/FT 基准
- [x] 任务 10：加入赛季阶段：初期/中期/末期/最后三轮
- [x] 任务 11：加入排名和战意过滤
- [x] 任务 12：加入未来三场赛程压力
- [x] 任务 13：优化首发阵容权重：攻击核心/防守核心拆分
- [x] 任务 14：加入赛中前 10 分钟节奏判断

### 第三阶段：复盘与评估

- [x] 任务 15：仪表盘加入走地状态
- [x] 任务 16：每日 V4 复盘报告
- [x] 任务 17：样本满 50 场后做第一次策略评估
- [x] 任务 18：维护中文队名缺失收集
- [x] 任务 19：半场结束后自动回填 V4 走地命中结果
- [x] 任务 20：半场后下半场大球评估器
- [x] 任务 21：新增 V4 规则型智能解释器
- [x] 任务 22：输出比赛类型标签 EARLY_FLASH / HT_PULLBACK / SH_SURGE / FT_OPEN_GAME 等
- [x] 任务 23：输出 primary_direction / trade_action / confidence
- [x] 任务 24：输出 why / wait_for / avoid_if 三段解释
- [x] 任务 25：dashboard 默认显示智能解释器结论
- [x] 任务 26：复盘时统计每种比赛类型的命中率和 ROI
- [x] 任务 27：P0-全量比赛池日志（`data/universe/fixtures_universe_YYYYMMDD.jsonl`）
- [x] 任务 28：P0-决策日志（`data/decision_logs/v4_decision_log_YYYYMMDD.jsonl`）

## 十、执行顺序

优先顺序：

```text
任务 1 → 任务 26 已完成
```

当前清单已完成，下一步进入真实纸盘运行、样本累积和按标签复盘调参。

## 十一、三方向评分说明

系统现在为每场比赛同时输出三套独立分数：

| 分数 | 用途 | 是否可直接进上半场滚球雷达 |
|:---|:---|:---:|
| HT走地分 | 衡量上半场走地回调潜力 | 仍需通过近期能力、时间分布、盘口、数据覆盖 |
| SH参考分 | 衡量下半场大球倾向 | 否 |
| FT参考分 | 衡量全场大球倾向 | 否 |

重要纪律：

```text
评分不是硬门槛。
HT走地必须先过近期能力、10-45时间分布、盘口高开和 API 数据覆盖。
SH/FT 分数再高，也不能自动进入上半场滚球雷达。
```

## 十二、10-45 分钟回调适配指标

V4_HT_LIVE_PULLBACK 的进场点通常发生在开赛 8-15 分钟，因此系统现在单独统计：

| 指标 | 含义 |
|:---|:---|
| 0-10 | 开场闪击倾向 |
| 11-30 | 等待后前半段压力 |
| 11-45 | 走地回调后剩余上半场出球能力 |
| 16-45 | 排除前 15 分钟后的持续压力 |
| late_fh_pressure | 11-45 与 16-45 的综合压力 |
| early_only_flag | 开场强、10分钟后弱的风险标记 |
| pullback_fit | STRONG / OK / WEAK |

策略纪律：

```text
early_only_flag=True 的比赛，即使 H2H 很强，也要降级观察。
pullback_fit=WEAK 的比赛，不适合 0-10 无球后追大。
```

## 十三、近期 HT 攻防动能

系统现在不只看“近 5 场是否半场有球”，还会拆成：

| 指标 | 含义 |
|:---|:---|
| home_recent_ht_scored | 主队近 5 场上半场进球率 |
| home_recent_ht_conceded | 主队近 5 场上半场失球率 |
| away_recent_ht_scored | 客队近 5 场上半场进球率 |
| away_recent_ht_conceded | 客队近 5 场上半场失球率 |
| home_attack_vs_away_defense | 主队上半场进攻 vs 客队上半场防线 |
| away_attack_vs_home_defense | 客队上半场进攻 vs 主队上半场防线 |
| ht_attack_vs_defense | 双方最强攻防组合 |
| both_sides_ht_threat | 双方综合攻防威胁 |

这类指标用于判断：

```text
一方稳定上半场进球 + 另一方稳定上半场失球
```

这比单纯的“双方近 5 场 HT 有球率”更贴近真实进球来源。

## 十四、滚球监控脚本

任务 5 已完成，脚本：

```text
engine/live_ht_over_monitor.py
```

输入：

```text
data/daily_reports/live_watchlist_YYYYMMDD.json
```

输出：

```text
data/live_monitor/v4_live_status_YYYYMMDD.json
data/paper_trading/v4_live_entries_YYYYMMDD.json
data/live_odds_snapshots/YYYYMMDD/
```

监控动作：

| 动作 | 含义 |
|:---|:---|
| WAIT_KICKOFF | 比赛未开始 |
| WATCHING_0_10 | 0-8 分钟 0-0，继续观察 |
| BUY_NOW | 8-15 分钟 0-0，盘口降到大 1.0 / 大 0.75 且水位合理 |
| WAIT_LINE_NOT_READY | 进场窗口内盘口或水位未到位 |
| SKIP_EARLY_GOAL | 等待期已经进球，跳过 |
| SKIP_WINDOW_CLOSED | 超过 15 分钟仍没有触发买点 |
| SKIP_LINEUP_DROP | 首发闸门要求移出观察 |
| SKIP_NOT_HT_FOCUS | 非上半场走地主方向 |

运行：

```text
python3 engine/live_ht_over_monitor.py --date 20260511 --once
python3 engine/live_ht_over_monitor.py --date 20260511 --watch --interval 30
```

## 十五、API-Football 数据覆盖闸门

任务 5.5 已完成，检查器：

```text
engine/data_sources/api_coverage.py
```

每天扫描时，每场比赛会输出：

| 字段 | 含义 |
|:---|:---|
| coverage_level | FULL / GOOD / BASIC / WEAK |
| data_gate_action | ALLOW_V4_LIVE / WATCH_ONLY / SKIP_DATA_WEAK |
| has_h2h | 是否有可用 H2H 样本 |
| has_recent_profile | 是否拿到近期球队画像 |
| has_pre_odds | 是否有赛前盘口 |
| live_odds_status | 走地盘口赛中再确认 |
| supported | league-season 层面的 events / lineups / statistics / injuries / odds 覆盖 |
| missing | 当前缺失的数据项 |

执行纪律：

```text
FULL / GOOD → 允许进入 V4 自动滚球监控
BASIC       → 只观察，不自动纸盘
WEAK        → 跳过
```

`/odds/live` 不保存历史，所以任务 6 仍然必须做快照库；否则赛后无法复盘盘口从大1.25降到大1.0/0.75的过程。

## 十六、/odds/live 快照库

任务 6 已完成，脚本：

```text
engine/live_odds_snapshot.py
```

保存结构：

```text
data/live_odds_snapshots/YYYYMMDD/index.json
data/live_odds_snapshots/YYYYMMDD/{fixture_id}/HHMMSS.json
data/live_odds_snapshots/YYYYMMDD/{fixture_id}/latest.json
```

每条快照包含：

| 字段 | 含义 |
|:---|:---|
| fixture_id | 比赛 ID |
| captured_at | 快照时间 |
| state | 比赛状态、分钟、比分 |
| line_values | 当前可见半场大球盘口线 |
| lines | Over 方向盘口、水位、公司、市场名 |
| watch_item | 赛前观察池信息 |
| raw | API-Football 原始 `/odds/live` 响应 |

快照纪律：

```text
同状态 + 同盘口重复轮询，不制造重复文件，只更新 latest 和 index。
index.json 记录每场比赛 first_seen / last_seen / snapshot_count / duplicate_count。
summarize_fixture_timeline() 可复盘首次出现大1.0/大0.75的时间和水位。
```

运行：

```text
python3 engine/live_odds_snapshot.py --date 20260511 --once
python3 engine/live_odds_snapshot.py --date 20260511 --watch --interval 30
python3 engine/live_odds_snapshot.py --date 20260511 --fixture-id 123456 --once
```

## 十七、亚洲盘结算

任务 7 已完成，模块：

```text
engine/asian_over_settlement.py
```

支持结果：

| 结果 | 含义 |
|:---|:---|
| WIN | 全赢 |
| HALF_WIN | 半赢 |
| PUSH | 走水 |
| HALF_LOSS | 半输 |
| LOSS | 全输 |

典型规则：

```text
Over 0.75，1球 → 半赢
Over 1.0，1球 → 走水
Over 1.25，1球 → 半输
Over 1.5，2球 → 全赢
```

调用：

```text
from engine.asian_over_settlement import settle_over_from_score

settle_over_from_score("1-0", line=0.75, odds=1.80, stake=1)
```

## 十八、V4 走地纸盘结算

任务 8 已完成，入口：

```text
engine/paper_trading.py
```

输入：

```text
data/paper_trading/v4_live_entries_YYYYMMDD.json
```

输出：

```text
data/paper_trading/v4_live_verified_YYYYMMDD.json
```

结算逻辑：

```text
读取 BUY_NOW 记录
拉取 fixture 完赛结果
取半场比分作为 HT 总进球
用亚洲盘结算模块计算 WIN / HALF_WIN / PUSH / HALF_LOSS / LOSS
汇总 W/P/L、总投入、总 PnL、ROI
```

半场自动回填：

```text
engine/v4_ht_result_verifier.py
```

```text
读取 v4_live_entries_YYYYMMDD.json
比赛状态到 HT / 2H / FT 且 score.halftime 有比分
立即按 entry_line + entry_over_odds 结算亚洲上半场大球
写回 v4_live_verified_YYYYMMDD.json
未到半场或比分缺失则留在 pending_items，下轮继续检查
```

运行：

```text
python3 engine/v4_ht_result_verifier.py --date 20260511 --once
python3 engine/v4_ht_result_verifier.py --date 20260511 --watch --interval 300
python3 engine/paper_trading.py --verify-v4-live 20260511
python3 engine/paper_trading.py --verify-v4-live-yesterday
python3 engine/paper_trading.py --verify-v4-live 20260511 --v4-stake 1
```

## 十九、联赛 HT/SH/FT 基准

任务 9 已完成，模块：

```text
engine/data_sources/league_baseline.py
```

每个联赛会基于本赛季已完赛比赛计算：

| 字段 | 含义 |
|:---|:---|
| sample_size | 已完赛样本数 |
| ht_goal_rate | 联赛上半场有球率 |
| sh_goal_rate | 联赛下半场有球率 |
| ft_over_1_5_rate | 联赛全场 2+ 球率 |
| avg_ht_goals | 联赛场均上半场进球 |
| avg_sh_goals | 联赛场均下半场进球 |
| avg_ft_goals | 联赛场均全场进球 |
| ht_env | FRIENDLY / NEUTRAL / COLD / UNKNOWN |
| sh_env | FRIENDLY / NEUTRAL / COLD / UNKNOWN |
| confidence | HIGH / MEDIUM / LOW |

初版阈值：

```text
HT有球率 >= 60% → FRIENDLY
HT有球率 < 50%  → COLD
样本 < 20       → UNKNOWN，不做强调整
```

执行纪律：

```text
FRIENDLY → 轻微加分
NEUTRAL  → 不调整
COLD     → HT_LIVE_OVER 自动降级为观察，不进入自动滚球监控
UNKNOWN  → 暂不调整
```

目的不是让联赛基准单独决定推荐，而是避免所有联赛共用同一条 HT 标准。

## 二十、赛季阶段

任务 10 已完成，模块：

```text
engine/data_sources/season_phase.py
```

系统会基于 API-Football 的联赛赛季 fixtures 推导：

| 字段 | 含义 |
|:---|:---|
| phase | EARLY / MID / LATE / FINAL_ROUND / UNKNOWN |
| progress_pct | 赛季已完成比例 |
| completed | 当前比赛前已完赛场次 |
| total | 联赛赛季总场次 |
| remaining | 剩余场次 |
| remaining_rounds_est | 估算剩余轮次 |

初版阶段规则：

```text
剩余轮次 <= 3 → FINAL_ROUND
进度 < 20%    → EARLY
进度 < 75%    → MID
否则          → LATE
```

执行纪律：

```text
EARLY       → 近期样本未稳定，轻微降权
MID         → 正常
LATE        → 需要结合排名和战意
FINAL_ROUND → 未接入战意前，不进入自动滚球监控
```

也就是说，任务 10 本身不判断战意，只负责告诉我们“现在是不是到了战意必须参与决策的阶段”。

## 二十一、排名和战意过滤

任务 11 已完成，模块：

```text
engine/data_sources/motivation.py
```

系统会基于 API-Football `standings` 判断：

| 标签 | 含义 |
|:---|:---|
| TITLE_RACE | 争冠压力 |
| CONTINENT_RACE | 欧战/洲际资格压力 |
| PROMOTION_RACE | 升级压力 |
| PLAYOFF_RACE | 附加赛压力 |
| RELEGATION_RISK | 保级压力 |
| MID_TABLE_SAFE | 中游安全区 |
| UNKNOWN_STANDING | 排名数据缺失 |

执行纪律：

```text
LATE / FINAL_ROUND 阶段：
  双方中游安全区 → WATCH_ONLY
  双方都有明确目标 → BOOST
  至少一方有明确目标 → ALLOW_V4_LIVE
  排名数据缺失 → WATCH_ONLY

EARLY / MID 阶段：
  战意只做加权，不强制过滤
```

这一步解决的是赛季末风险：有些比赛数据好看，但双方无欲无求，真实攻防强度可能下降。

## 二十二、未来三场赛程压力

任务 12 已完成，模块：

```text
engine/data_sources/schedule_pressure.py
```

系统会基于 API-Football：

```text
fixtures?team={team_id}&next=3
```

计算：

| 字段 | 含义 |
|:---|:---|
| games_next_7d | 未来 7 天比赛数量 |
| games_next_10d | 未来 10 天比赛数量 |
| min_gap_days | 当前比赛到未来比赛的最短间隔 |
| level | LOW / MEDIUM / HIGH |
| action | KEEP / KEEP_CAUTION / WATCH_CAUTION |

执行纪律：

```text
HIGH   → WATCH_CAUTION，不进入自动滚球监控
MEDIUM → KEEP_CAUTION，只提示轮换风险
LOW    → KEEP
```

这一步主要防止密集赛程导致主力轮换、压节奏或提前收力。

## 二十三、首发攻击/防守核心拆分

任务 13 已完成，模块：

```text
engine/data_sources/lineup_strength.py
```

首发闸门现在拆成三组：

| 指标 | 含义 |
|:---|:---|
| attack_core_present / attack_core_count | 前锋核心到位情况 |
| midfield_core_present / midfield_core_count | 中场连接核心到位情况 |
| defense_core_present / defense_core_count | 门将/后卫核心到位情况 |
| attack_signal | ATTACK_FULL / ATTACK_OK / ATTACK_WEAK |
| defense_signal | DEFENSE_STABLE / DEFENSE_GAP / DEFENSE_HEAVY_GAP |

执行纪律：

```text
攻击核心明显缺失 → DROP_ATTACK_WEAK
大轮换 → DROP_HEAVY_ROTATION
攻击端完整 + 防线缺口 → BOOST_OVER
攻击端基本可用 → KEEP_WATCH
```

这一步让“全主力阵容”不再只是笼统判断，而是区分：攻击端是否能进球、防守端是否可能给对手机会。

## 二十四、赛中前 10 分钟节奏判断

任务 14 已完成，模块：

```text
engine/data_sources/live_tempo.py
```

接入位置：

```text
engine/live_ht_over_monitor.py
```

进场窗口 8-15 分钟时，系统会检查：

| 指标 | 来源 |
|:---|:---|
| total_shots | fixtures/statistics |
| shots_on_goal | fixtures/statistics |
| corners | fixtures/statistics |
| dangerous_attacks | fixtures/statistics |
| red_cards | fixtures/events |

执行纪律：

```text
红牌 → SKIP_TEMPO_GATE
节奏沉闷 → SKIP_TEMPO_GATE
统计缺失 → 不硬拦截，继续按盘口/比分判断
节奏达标 → 允许进入盘口买点判断
```

这一步是最后的赛中保险：避免 0-0 降盘后，比赛实际节奏很低却机械入场。

## 二十五、仪表盘走地状态

任务 15 已完成，仪表盘现在会读取：

```text
data/live_monitor/v4_live_status_YYYYMMDD.json
data/paper_trading/v4_live_entries_YYYYMMDD.json
```

并展示：

| 字段 | 含义 |
|:---|:---|
| liveAction | WAIT_KICKOFF / WATCHING_0_10 / BUY_NOW / SKIP 等 |
| liveReason | 走地监控原因 |
| liveMinute | 当前分钟 |
| liveScore | 当前比分 |
| entryLine | 入场盘口 |
| entryOdds | 入场水位 |

这一步让网页不只是赛前情报卡，也能看到走地监控和纸盘入场状态。

## 二十六、每日 V4 复盘报告

任务 16 已完成，脚本：

```text
engine/v4_review_report.py
```

输入：

```text
scout_v4_YYYYMMDD.json
live_watchlist_YYYYMMDD.json
v4_live_status_YYYYMMDD.json
v4_live_entries_YYYYMMDD.json
v4_live_verified_YYYYMMDD.json
live_odds_snapshots/YYYYMMDD/
```

输出：

```text
data/daily_reports/v4_review_YYYYMMDD.json
data/daily_reports/v4_review_YYYYMMDD.md
```

运行：

```text
python3 engine/v4_review_report.py --date 20260511
```

## 二十七、V4 样本评估

任务 17 已完成，脚本：

```text
engine/v4_strategy_eval.py
```

读取：

```text
data/paper_trading/v4_live_verified_*.json
```

输出：

```text
data/daily_reports/v4_strategy_eval.json
```

评估内容：

```text
样本数是否 >= 50
W/P/L
命中率
总投入
总 PnL
ROI
按入场盘口线分桶
```

运行：

```text
python3 engine/v4_strategy_eval.py --save
```

## 二十八、半场后下半场大球评估

任务 20 已完成，脚本：

```text
engine/second_half_evaluator.py
```

触发时间：

```text
半场结束后 1-5 分钟开始轮询
```

输入：

```text
data/daily_reports/scout_v4_YYYYMMDD.json
fixtures?id=
fixtures/statistics?fixture=
fixtures/events?fixture=
odds/live?fixture=
```

核心判断：

```text
只处理 SECOND_HALF_OVER 候选
读取半场比分
统计上半场射门 / 射正 / 角球 / 危险进攻
检查红牌和伤退
抓取 Second Half / 下半场实时大小球盘口
优先寻找 SH Over 1.0 或 0.75 的合理水位
```

动作输出：

| 动作 | 含义 |
|:---|:---|
| SH_BUY_NOW | 半场场面、比分结构、盘口均支持下半场大球 |
| SH_WATCH | 条件接近，需要人工复核 |
| SH_WATCH_PRICE | 下半场盘口未到合理水位 |
| SH_WAIT_HALFTIME | 还没到半场 |
| SH_SKIP_TEMPO | 上半场沉闷或有红牌 |
| SH_SKIP_CONTEXT | 半场比分结构不支持 |
| SH_SKIP_DATA_WEAK | API 数据覆盖过弱 |

输出：

```text
data/live_monitor/v4_second_half_status_YYYYMMDD.json
data/paper_trading/v4_second_half_entries_YYYYMMDD.json
```

运行：

```text
python3 engine/second_half_evaluator.py --date 20260512 --once
python3 engine/second_half_evaluator.py --date 20260512 --watch --interval 300
```

## 二十九、V4 智能比赛解释器

任务 21-25 已完成，模块：

```text
engine/v4_match_intelligence.py
```

定位：

```text
把底层因子转成交易员可读的比赛标签、主方向、建议动作和解释。
第一阶段使用规则型解释器，不做黑盒模型。
```

输出字段：

| 字段 | 含义 |
|:---|:---|
| match_type | 比赛类型标签 |
| primary_direction | 主方向：HT / SH / FT / EARLY_HT / SKIP |
| trade_action | 当前建议动作 |
| confidence | 解释器信心分 |
| profile | 比赛画像 |
| summary | 一句话结论 |
| why | 为什么这么判断 |
| wait_for | 等待什么条件 |
| avoid_if | 什么情况避开 |

当前标签：

```text
EARLY_FLASH        上半场早段闪击型
HT_PULLBACK        上半场回调型
SH_SURGE           下半场爆发型
FT_OPEN_GAME       全场开放局
PRICE_TOO_EXPENSIVE 方向对但盘口太贵
DATA_TOO_WEAK      API覆盖不足
DULL_TRAP          数据看着不差但场面/时间结构不支持
NO_CLEAR_EDGE      方向不集中
```

关键解释纪律：

```text
回调适配 WEAK 不等于上半场不会进。
它只代表 0-10 分钟无球后，继续等降盘买入的质量差。
```

## 三十、中文队名缺失收集

任务 18 已完成，脚本：

```text
engine/team_cn_missing_collector.py
```

扫描：

```text
data/daily_reports/scout_v4_*.json
data/daily_reports/live_watchlist_*.json
```

写入：

```text
engine/team_cn_map.json
```

运行：

```text
python3 engine/team_cn_missing_collector.py
python3 engine/team_cn_missing_collector.py --date 20260511 --save
```

用途：把未能翻译成中文的队名集中收集到 `unknown`，后续人工补充到 `TEAM_CN_MAP`。
