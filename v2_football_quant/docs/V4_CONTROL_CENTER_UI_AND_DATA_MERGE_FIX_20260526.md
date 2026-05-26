# V4_CONTROL_CENTER_UI_AND_DATA_MERGE_FIX_20260526

## 结论
V4_CONTROL_CENTER_UI_DATA_MERGE_FIX_PASS

## 根因
- 当前页面此前是“已验收 UI 壳”与“生产数据绑定 JS”未完成合并，导致静态值/空值风险。

## 本轮修复
- 保持 UI 外观不变，仅补齐 JS 数据绑定与 model 字段。
- 恢复 `loadModel()`，并兼容 `{ok:true, model:{...}}` / 直接 model。
- 绑定顶部 KPI、候选区、SKIP 摘要、右侧待办、实盘快照、系统状态。
- 强化 checker，拦截“仅静态稿”假通过。

## 问题回答
1. 原因是否为静态设计稿没有数据绑定？
- 是。
2. 是否保持 BOSS 接受 UI 不变？
- 是。
3. 是否恢复 loadModel？
- 是。
4. 是否恢复 /api/v4_control_center_model 渲染？
- 是。
5. 顶部 KPI 是否真实？
- 是。
6. 候选卡是否真实？
- 是。
7. 默认盘口/水位/金额/分钟来源是什么？
- 来自 `build_v4_control_center_model.py` 输出的 candidate 默认字段（含实盘摘要覆盖与兜底默认）。
8. 右侧待办是否真实？
- 是（todo_summary）。
9. 实盘快照是否真实？
- 是（live_bet_summary）。
10. 是否清除 undefined？
- 可见内容已清除。
11. checker 是否能拦截静态壳假通过？
- 是。
12. 是否改 CSS？
- 否。
13. 是否改策略？
- 否。
14. 是否改 candidate？
- 否。
15. 是否重算 validation？
- 否。
16. 是否改 live bet 原始记录？
- 否。
17. 是否推 QQ？
- 否。
18. 是否 cloud / cron？
- 否。
