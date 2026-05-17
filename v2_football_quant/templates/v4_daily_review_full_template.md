【V4 情报系统】
📌 {{review_date}} V4正式复盘
━━━━━━━━━━━━━━
【正式输出】
A：{{a_count}}｜B：{{b_count}}｜C：{{c_count}}｜SKIP：{{skip_count}}
A+B主推荐：{{ab_count}}场
正式推荐：{{recommendation_summary}}

数据源：{{official_brief_file}}
━━━━━━━━━━━━━━

【逐场验证】

{{match_rows}}

━━━━━━━━━━━━━━

【汇总】
A级：{{a_hit}}/{{a_total}} · {{a_hit_rate}}
B级：{{b_hit}}/{{b_total}} · {{b_hit_rate}}
C级：{{c_hit}}/{{c_total}} · {{c_hit_rate}}
SKIP正确：{{skip_correct}}/{{skip_total}} · {{skip_correct_rate}}
SKIP反杀：{{skip_backfire}}/{{skip_total}} · {{skip_backfire_rate}}

{{daily_summary_note}}
━━━━━━━━━━━━━━

【时间分布】
{{sample_count}}场｜上半场总{{ht_goal_total}}球

0-15m：{{goals_0_15_total}}球（{{goals_0_15_minutes}}）
16-30m：{{goals_16_30_total}}球（{{goals_16_30_minutes}}）
31-45+：{{goals_31_45_total}}球（{{goals_31_45_minutes}}）

首球时段：
0-15m：{{first_goal_0_15}}场
16-30m：{{first_goal_16_30}}场
31-45+：{{first_goal_31_45}}场
无进球：{{no_ht_goal_count}}场
数据缺失：{{data_missing_count}}场
━━━━━━━━━━━━━━

【赛前剧本验证】
剧本命中：{{script_hit}}场
部分命中：{{script_partial}}场
剧本偏差：{{script_miss}}场
无HT球可验证：{{no_ht_goal_to_validate}}场
剧本未存档：{{script_not_available}}场

偏差方向：
符合：{{matched_count}}
偏早：{{earlier_than_expected}}
偏晚：{{later_than_expected}}
过严：{{too_strict_script}}
无数据：{{script_no_data}}

重点：{{script_review_note}}
━━━━━━━━━━━━━━

【赛前信号复盘】
A/B样本：{{ab_sample_count}}场
平均HT评分：{{avg_ht_score}}
平均HT率：{{avg_ht_goal_rate}}
平均场均HT：{{avg_avg_ht_goals}}
盘口支持：{{market_support_count}}场
全场强于HT风险：{{fulltime_stronger_count}}场
风险验证有效：{{risk_validated_count}}场

说明：{{pre_match_signal_note}}
━━━━━━━━━━━━━━

【天气/场地因子】
{{weather_rows_or_summary}}

说明：天气只作归因辅助，不参与重算评级。
━━━━━━━━━━━━━━

【滚动观察】
近7天 A/B：{{rolling_7d_ab}}
近7天 C级：{{rolling_7d_c}}
近7天 SKIP反杀：{{rolling_7d_skip_backfire}}
近7天 剧本命中：{{rolling_7d_script}}

近14天：{{rolling_14d_summary}}
近30天：{{rolling_30d_summary}}
累计：{{cumulative_summary}}

来源：{{rolling_source_files}}
━━━━━━━━━━━━━━

【累计归因】
模型有效：{{model_valid_count}}
模型过严：{{model_too_strict_count}}
模型过度自信：{{model_overconfident_count}}
噪音命中：{{noisy_win_count}}
噪音失败：{{noisy_loss_count}}
数据质量问题：{{data_quality_issue_count}}
天气风险：{{weather_risk_count}}

重点：{{diagnosis_note}}
━━━━━━━━━━━━━━

【结论】
{{rule_decision}}
{{ab_conclusion}}
{{skip_observation}}
{{script_observation}}
{{data_quality_note}}
{{sample_warning}}

⚠️ 赛后归因报告，不代表今日实盘推荐
