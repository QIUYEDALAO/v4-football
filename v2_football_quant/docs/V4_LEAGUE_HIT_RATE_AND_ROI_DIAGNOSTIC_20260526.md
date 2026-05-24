# V4_LEAGUE_HIT_RATE_AND_ROI_DIAGNOSTIC_20260526

## 结论
- 本阶段为统计诊断，未改 production 策略。
- 样本复现：A=41，B=89，A+B=130。
- 已生成联赛诊断 JSON 与本地 HTML 页面。
- 盘口 ROI 使用 paper odds（默认 0.80）模拟，属于诊断用途。

## 问题回答
1. 总样本是否仍为 A=41/B=89/AB=130？是。
2. 哪些联赛样本足够看？暂无 >=20 样本联赛
3. 哪些联赛只是小样本观察？丹超, 乌克超, 乌拉甲, 俄超, 保甲, 克亚甲, 冰岛超, 匈甲, 印尼超, 埃及超, 塞尔超, 墨西联
4. 哪些联赛 O0.75 表现好？丹超(0.825), 乌克超(0.825), 印尼超(0.825), 奥甲(0.825), 爱超(0.825)
5. 哪些联赛 O1 表现好？丹超(0.825), 乌克超(0.825), 印尼超(0.825), 奥甲(0.825), 爱超(0.825)
6. 哪些联赛 O1.25/O1.5 不适合？保甲(O1.5=-0.975), 克亚甲(O1.5=-0.975), 埃及超(O1.5=-0.975), 塞尔超(O1.5=-0.975), 墨西联(O1.5=-0.975)
无
无
无
9. 是否改了正式策略？否。
10. 是否可以进入下一阶段联赛分层 shadow test？可以。

## 输出文件
- data/runtime/status/v4_league_hit_rate_inventory_20260526.json
- data/runtime/status/v4_league_hit_rate_stats_20260526.json
- data/runtime/dashboard/v4_league_hit_rate.html
- tools/build_v4_league_hit_rate_report.py
- tools/check_v4_league_hit_rate_report.py

## 禁止项确认
- full_scan_ran=false
- validation_recomputed=false
- strategy_changed=false
- candidate_changed=false
- result_validation_changed=false
- script_validation_changed=false
- dashboard_official_numbers_changed=false
- outside_57_mixed_into_official=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- secrets_printed=false
