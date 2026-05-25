# V4 AB 130 Sample Strategy Diagnostic (No Rule Change)

## Phase
V4-AB-130-SAMPLE-STRATEGY-DIAGNOSTIC-NO-RULE-CHANGE-20260525

## 关键结论
- 样本复现：A=41，B=89，A+B=130（仅 A/B settled）。
- 当前仅可做诊断与 shadow 候选，不可直接改 production 规则。
- 建议进入 shadow test（100-200 场）后再申请正式改规则。

## 问题回答
1. 130 场 A/B 样本是否足够直接改策略？
- 不足以“直接”改 production；可用于提出候选并进入 shadow 验证。
2. A 和 B 是否表现有明显差异？
- 有：A=25/41(61.0%)，B=50/89(56.2%)，A 高于 B。
3. 哪些联赛表现差？
- 在样本>=5里，较弱分层主要出现在：西甲(7, ROI_O1=0.167857), 瑞士超(5, ROI_O1=0.225), 冰岛超(8, ROI_O1=0.275), 土超(10, ROI_O1=0.425), 美职业(15, ROI_O1=0.491667)。
4. 哪些 HT 分数区间表现差？
- 最弱区间：65-70（sample=23，ROI_O1=0.155435）。
5. 哪些剧本表现差？
- 最弱剧本：中段发力型（sample=21，ROI_O1=0.072619）。
6. O0.75 / O1 / O1.25 / O1.5 哪个盘口更适合？
- 本样本下 AB 含返水 ROI 排序：[('O0.75', 0.571154), ('O1', 0.348077), ('O1.25', 0.125), ('O1.5', -0.098077)]，最优是 O0.75。
7. 含 2.5% 反水后 ROI 如何？
- AB: O0.75=0.571154, O1=0.348077, O1.25=0.125, O1.5=-0.098077。
8. 当前最可疑的规则问题是什么？
- B级在部分分层（低分段/特定剧本）收益质量偏弱，存在“覆盖过宽导致效率下滑”的迹象。
9. 哪些规则只能观察不能改？
- 所有 sample<20 的分层只能 OBSERVE；20-50 仅 WARN，不得直接改正式策略。
10. 是否建议进入 shadow test？
- 是，建议。
11. 是否改了 production？
- 否。
12. 是否可以进入下一阶段 shadow ruleset 设计？
- 可以，前提是继续保持 production 不变并走 shadow 对照验证。

## 盘口模拟（AB, 含2.5%返水）
- O0.75: gross=71.0, net=74.25, ROI=0.571154
- O1: gross=42.0, net=45.25, ROI=0.348077
- O1.25: gross=13.0, net=16.25, ROI=0.125
- O1.5: gross=-16.0, net=-12.75, ROI=-0.098077

## 禁止项确认
- full_scan_ran=false
- validation_recomputed=false
- strategy_changed=false
- candidate_changed=false
- result_validation_changed=false
- script_validation_changed=false
- dashboard_changed=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- secrets_printed=false

## 最终结论
V4_AB_130_SAMPLE_STRATEGY_DIAGNOSTIC_NO_RULE_CHANGE_WARN_ONLY
