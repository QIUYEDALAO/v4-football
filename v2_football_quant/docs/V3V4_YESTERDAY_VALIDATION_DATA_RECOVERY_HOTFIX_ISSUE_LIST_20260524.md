# V3V4_YESTERDAY_VALIDATION_DATA_RECOVERY_HOTFIX_ISSUE_LIST_20260524

1. 昨日验证卡片可见，但 A/B/A+B 仍为 N/A。
2. 上一阶段 checker 只验证 visible，没有验证数据非空。
3. dashboard_date=20260524。
4. yesterday_validation_target_date=20260523。
5. cumulative 有数据，但 yesterday 没数据。
6. 需要审计 20260523 attribution 是否存在。
7. 需要审计 20260523 validation summary 是否生成。
8. 需要审计 resolver 是否读取错文件。
9. 需要审计 match_date timezone 是否把 20260523 样本移走。
10. 本轮不得跑完整 scan / 不改策略 / 不推送 / 不发布。

Step 1 结论：PASS（问题清单完整）。
BLOCKER 定义：仍把“卡片可见”当作昨日验证 PASS。
