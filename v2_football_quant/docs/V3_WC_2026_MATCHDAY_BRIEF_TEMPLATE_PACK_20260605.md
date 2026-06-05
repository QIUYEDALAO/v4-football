# V3_WC_2026_MATCHDAY_BRIEF_TEMPLATE_PACK

本阶段新增 V3 世界杯赛前情报卡模板与本地生成器。输出只作为 observation-only 手机阅读卡，不调用 live API，不生成首发，不生成预测，不输出投注建议，不影响 V4 official。

## 输出

- `templates/v3_worldcup_matchday_brief_card.md`
- `tools/build_v3_worldcup_matchday_brief_template.py`
- `tools/check_v3_worldcup_matchday_brief_template.py`
- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_matchday_brief_cards.json`
- `data/manual_sources/v3_worldcup/war_room/v3_wc2026_matchday_brief_summary.json`
- `data/manual_sources/v3_worldcup/war_room/V3_WC2026_MATCHDAY_BRIEF_CARDS.md`

## 口径

- 完整赛程：104 张赛前情报卡。
- 小组赛：72 张，保留双方 Final26 摘要、场馆、venue stress、lineup status、odds status、data gaps。
- 淘汰赛：32 张，只显示 structural placeholder，不生成真实球队。
- 官方首发未到时固定显示 `WAIT_OFFICIAL_LINEUP`。
- odds 只显示 `first_seen_odds`、`last_pre_kickoff_odds`、`odds_observation_delta`。
- 原生开盘/收盘缺失，不生成盘口变化结论，不生成资金流结论。

## 安全

所有输出保留：

- `observation_only=true`
- `no_starting_xi_generated=true`
- `no_prediction=true`
- `no_injury_judgment=true`
- `betting_recommendation=false`
- `affects_v4=false`
