# MEMORY.md — 长期记忆

## 🫡 BOSS操作宪法 (2026-05-15 生效)

我是BOSS的足球量化系统操作员、风控审计员、复盘分析员，不是自由发挥的足球推荐员。

### 核心禁令
- 不凭直觉改策略 | 不因单日结果改规则 | 不把观察池说成正式推荐
- 不把纸盘信号说成实盘下注 | 不把SH/FT信息污染HT主策略
- 日报只解释 | 周报只观察 | 月报才允许提出规则调整建议
- 所有建议必须基于样本数、命中率、归因标签、root cause、数据质量和连续性表现

### 三系统定位
- **V2** (v2.3.1): 半场平局赔率带 2.00-2.90 | T-90m/T-45m唯一BET_LOCKED | ODDS_OUT只追踪
- **V3** (战备): 世界杯Perception Gap | enabled=false→战备观察 | MD1→MD2→MD3→KO路由
- **V4** (纸盘验证): HT进球情报 A/B/C/SKIP | 天气/裁判/阵容等仅归因不进评分

### V4归因核心标签
MODEL_VALID_STRONG(高质量命中) | MODEL_TOO_STRICT(跳过误杀) | MODEL_OVERCONFIDENT(推荐过松)
UNLUCKY_MISS(过程好没进球) | LUCKY_HIT(运气球命中) | NOISY_WIN/LOSS(噪音干扰)
DATA_QUALITY_ISSUE(先补数据) | CONTEXT_CHANGED(人工复核)

### 规则变更纪律
- <100场样本：不许建议核心权重调整
- 连续7天同方向异常：才允许观察性建议
- 月报样本足够：才允许规则调整建议
- SKIP偏严→先SKIP→C观察，不直接升A/B

### 每日输出
1. V2 BET_LOCKED数 2. V4 A/B/C/SKIP 3. 昨日复盘判断(模型有效/偏严/偏松/噪音/正常波动)
4. 是否人工介入 5. 禁止改规则

---

## 💎 核心价值观

> **赔率涨跌不改变已成交的 PnL，只影响 CLV 的符号，而 CLV 的符号才是 Alpha 存在的证据。**

### 三层 CLV 审计标准 (P0 部署)
- **raw_clv**: (买入价/收盘原始价)-1 — 战胜市场表象了吗？
- **fair_line_clv**: 去水公平概率漂移 — 扣除vig后的真实移动
- **ev_vs_close**: 最严苛标准（等同旧True CLV）
- 先看 raw_clv，再去抠 EV 细节。拜仁实测 raw=-0.31%（几乎持平），之前的 -7.57% 恐慌一半是抽水幻觉。

## 🔭 V4 走地系统（2026-05-13 凌晨上线）

### 定位
- 纯球探情报系统 → 赛中走地回调策略 `V4_HT_LIVE_PULLBACK`
- 不与 V2 交易耦合，独立数据采集+独立仪表盘
- 65 模块 / ~17K 行 Python，全流水线闭环

### 核心策略
- **不入场规则**: 不在赛前预测进球，在赛中等待盘口犯错
- **三层采集**: A_candidate (入池候选) / B_shadow (选择偏差) / C_slice (衰减校准)
- **EV 决策链**: hazard_model → line_decay → asian_ev → execution_cost → risk_guard
- **进场窗口**: 0-10分钟 0-0 → 等盘口降到大1.0/0.75 → PAPER_BUY_NOW
- **三方向隔离**: HT_LIVE_OVER / SECOND_HALF_OVER / FULLTIME_OVER 互不污染

### 关键设计决策
- strict_v3_pullback: 赛前只要求大1.25线，0.75/1.0/1.25 线型是赛中触发条件
- SH_NOISY guard: 下半场只看 EV 不看命中率（防高命中低赔率陷阱）
- B_shadow 分层: near_miss + random_baseline
- 仪表盘默认 ops 窗口 (12:00→次日12:00) + 时间排序
- 天气模块已就位 (OpenWeatherMap 50城坐标)
- Cron: 17 个作业，采集每 2 分钟，走地监控每 10 分钟

### 当前状态 (5/13)
- Universe: 10 天历史 (B_shadow 池来源)
- 5/13 凌晨: 7,582 API 调用 (10%), 0 次 429
- 标准化: 495 行, 全量线型 0.5-1.75
- 半场入场: 0 条 (走地监控运行中，等待 HT_LIVE_OVER 候选进入窗口)
- 专家建议: 不要推翻 HT 策略，先补 B_shadow + 诊断

### 项目定位
- 数据源：API-Football Pro (Key: e5e315b1f9ba1ba51dc2124b35f07a01)
- 56个联赛白名单 | 14引擎模块 | 3026行 Python
- 核心KPI：ROI > 3% | CLV > 0 | 命中率 > 58%
- GitHub: git@github.com:whoerixxz/v2-football-quant.git

### 当前阶段：纸盘验证（5/6 - 5/12）
- 8:00 Cron `V2每日扫描` 自动扫描 → QQ Bot 推送
- 次日 paper_trading.py 自动结算（含三层CLV: raw/fair_line/ev_vs_close）
- 每天同时保存全量候选池快照 universe_candidates_YYMMDD.json
- 纸盘验收：7天 ≥25场 | CLV>0 | ROI≥3% | MDD≤12%
- 5/5 首场结算：Al Khaleej vs Al Hilal HT 1-1 ✅ | PnL +86.1u | CLV -8.43%
- 5/6 推荐2场：拜仁vs巴黎(HT Draw Edge+11.2%) + 阿联酋超(Edge+5%)
  - 结算: 1/2 命中, 平均 CLV -7.23% (raw_clv拜仁 -0.31% 几乎持平收盘)

### 架构红线（信号与执行分离）
- 纸盘期：8:00 快照 → 假设瞬间成交 → 次日 CLV 结算
- 实盘期：daily_runner 降级为观察池 → odds_monitor 赛前30min轮询 → T-15min临场决策
- **绝不把 8:00 快照直接接下单 API**

### 最新Bankroll配置（2026-05-07 19:52 锁定）
- 本金：**20,000** | Kelly **1/4** (红线) | 单注上限 **1,000**
- 硬熔断：**-30%** (亏6,000强制停机) | 软熔断：**-15%** (亏3,000减半1/8 Kelly)
- Kelly < 100 → **SKIP_LOW_KELLY**（宁可不下绝不超配）
- `calculate_stake()` 返回 dict `{action, stake, reason, raw_kelly, effective_kelly, kelly_factor_used}`
- `_kelly_factor_for_drawdown()`: 阶梯熔断函数 (0→25% > 15%→12.5% > 30%→0)

### P0 五件套已部署（2026-05-07 PM）
1. ✅ **Kelly毒药拆除**: 废除clamp抬高，Kelly<100→SKIP
2. ✅ **三层CLV**: clv_triple(raw/fair_line/ev_vs_close)，剥离抽水幻觉
3. ✅ **全量候选池**: universe_candidates快照，归因分析基础
4. ✅ **信号审计日志**: break_even_prob+action字段，负EV自动阻断
5. ✅ **密钥清理**: 环境变量注入，移除fallback明文

### Phase 1 上帝视角部署（2026-05-07 22:30）
1. ✅ **Kelly元数据**: raw_kelly/effective_kelly/kelly_factor_used 注入每笔决策
2. ✅ **全景死因追踪**: full_scan_YYYYMMDD.json 记录所有扫描场次(含SKIP死因)
3. ✅ **漏斗日报**: 总场次→无盘口→无Edge→负EV→熔断→低Kelly→BET 转化率
4. 🔄 **多维归因仪表盘**: paper_trading.py --summary 待重构 (Task 3)

### P0 剩余
- ❌ 评分引擎权重校准（H2H 20%→60%）
- ❌ 14联赛数据补拉

## 🔧 工程纪律
- 临近开赛/周末 → 代码静止
- 样本外积累优先 → 几十场后才 --summary
- 所有规则以代码为准，MEMORY 仅作记录

## 🚀 V3/V4 多策略系统（2026-05-06 晚建成）

### 架构
- **Strategy Router** (`strategy_router.py`): 三路分发 V2(次级) / V3(W杯) / V4(五大)
- 开闭原则: 新模型独立接入，不改 daily_runner

### Phase 0-3 完成（17/30任务）
- ✅ Phase 0: 基础设施（配置/映射/Git）
- ✅ Phase 1: 策略路由框架
- ✅ Phase 2A: API-Football深挖（Proxy xG + 战力折损引擎 + 核心球员权重库12队）
- 🔒 Phase 2B: FotMob — Killed by Cloudflare Turnstile
- ✅ Phase 3: V3世界杯引擎（Elo + Perception Gap + 亚盘套利 + 淘汰赛平局）
- 🔒 Phase 4: V4 五大联赛 — Paused until Aug

### 关键文件
- `engine/strategy_router.py` — 路由分发器
- `engine/wc_model.py` — W杯 Elo模型（测试通过: 英vs日 BUY Japan AH+1.25）
- `engine/data_sources/elo_scraper.py` — Elo积分爬虫
- `engine/data_sources/proxy_xg_engine.py` — 伪xG引擎
- `engine/data_sources/apifootball_deep.py` — 伤停+首发+战力折损
- `config/core_players_weight.json` — 12队核心球员权重

### 三轮Code Review共修复9个Bug
- R1: Stake丢失/NoneType/旧纸盘
- R2: Kelly摧毁/平局误杀/收盘真空
- R3: 双发请求缓存/死代码/密钥硬编码→环境变量

## 🏗️ 系统配置
- 模型：deepseek-v4-flash（默认）/ v4-pro（重型）
- 通道：QQ Bot (ON) | 微信 (已弃)
- 记忆：memory-core + memory-wiki（后台编译）
- 银行：20,000本金 | Kelly 1/4 | 单注上限1,000
- Cron：每天 08:00/12:00/16:00 BJT 三频扫描 → QQ Bot推送
- 结算：次日三层CLV自动结算 + 全量候选池快照
- 项目书：v2.2 (docs/PROJECT_BOOK.md)
- GitHub: whoerixxz/v2-football-quant (16 commits today)

### 四层防线闭环
1. **bankroll.py** — Kelly仓位·阶梯熔断·SKIP_LOW_KELLY
2. **strategy_router.py** — N≥20铁律·黄金跳变提权·毒药崩塌斩杀
3. **live_bridge.py** — 准入审查·试水0.5%·Kill-Switch拔网线
4. **paper_trading.py** — 8面板仪表盘·CLV三层·每周审判日

### V3 世界杯引擎 (2026-05-08 建成)
- 88场四届大赛数据 (WC2018/2022, EC2020/2024)
- Perception Gap = log(身价比) - log(Elo比)
- 极度泡沫区(Gap>1.0): 下盘不败33.3%, 平赔4-6x, EV正
- Router: V3_PERCEPTION_GAP_SNIPER 赛季隔离 (非大赛季 SKIP_OFF_SEASON)
- 开枪红线: v3_thresholds.json (小组赛R1-R2, Gap>0.15, 买入受让方)

### 五大联赛双轨制
- fair_odds_matrix_top5_v2.json: 7,230场时间衰减校准
- 五大联赛档5 P(D)=45.2% vs 通用42.6%
- matrix_config.json 双轨切换 (五大→专项矩阵, 其余→通用)

### SSL证书修复
- engine/net_utils.py: urllib优先, 403自动回退subprocess+curl
- 全引擎统一 UA: V2-Football-Quant/1.0
- GUARD审计: grep '[GUARD] API_' *.log

### 三频时序雷达
- --run_tag AM0800/NOON1200/PM1600
- 复合主键 (fixture_id + scan_tag) 合并
- full_scan 三条快照互不吞食
- Time-Series Signal Lock 首次触发锁定
