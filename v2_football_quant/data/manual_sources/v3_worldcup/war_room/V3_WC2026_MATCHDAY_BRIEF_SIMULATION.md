# V3 世界杯赛前情报卡 dry-run

observation-only。以下为本地 mock odds 演示，不调用 live API，不生成首发，不生成预测，不生成资金流结论，不影响 V4。

## Algeria vs Austria

- 比赛：Algeria vs Austria
- 时间：June 11, 2026 1:00 p.m. UTC−06:00
- 场馆：Estadio Azteca
- 阶段：小组赛 A 组
- 双方 Final26 摘要：Algeria 26人；GK/DF/MF/FW=3/9/7/7；均龄 26.86；均高 182.65cm；Austria 26人；GK/DF/MF/FW=3/8/11/4；均龄 28.54；均高 184.69cm
- venue stress：Estadio Azteca；ALTITUDE_STRESS / MIDDAY_KICKOFF_RISK / VENUE_UPSET_WATCH / WATCH_ONLY；原因：altitude=2200m; midday=HIGH (Oxygen)；来源等级：HIGH_SOURCE_CROSS_CHECKED_VIDEO_CLAIM_OBSERVATION_ONLY
- lineup status：WAIT_OFFICIAL_LINEUP
- data gaps：NO_NATIVE_OPENING_CLOSING_ODDS / WAIT_OFFICIAL_LINEUP

## mock odds 时间点

- T-24h：first_seen_odds=2.42/3.18/2.96；last_pre_kickoff_odds=等待后续快照；odds_observation_delta=BASELINE_MOCK_SNAPSHOT
- T-6h：first_seen_odds=2.42/3.18/2.96；last_pre_kickoff_odds=等待后续快照；odds_observation_delta={'home': -0.02, 'draw': 0.01, 'away': 0.03}
- T-90m：first_seen_odds=2.42/3.18/2.96；last_pre_kickoff_odds=等待后续快照；odds_observation_delta={'home': -0.04, 'draw': 0.02, 'away': 0.04}
- T-30m：first_seen_odds=2.42/3.18/2.96；last_pre_kickoff_odds=2.38/3.2/3.0；odds_observation_delta={'home': -0.04, 'draw': 0.02, 'away': 0.04}

说明：只展示 first_seen_odds、last_pre_kickoff_odds、odds_observation_delta；原生开盘/收盘缺失；不生成盘口或资金流结论。

安全提示：WAIT_OFFICIAL_LINEUP；no starting XI；no prediction；no betting；affects_v4=false。
