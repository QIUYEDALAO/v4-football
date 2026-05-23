# V3/V4 Dashboard Compact Validation Remove C Observation Issue List 20260523

Phase: V3V4-DASHBOARD-COMPACT-VALIDATION-REMOVE-C-OBS-20260523

## Issues

1. 验证区纵向过长，iPhone 首屏阅读负担过高。
2. 昨日验证与累计验证仍以多列/多块方式占用右侧和纵向空间。
3. 近7天验证不再需要展示，应从 active dashboard 移除。
4. C级观察不再保留为 active 展示、验证、分析对象。
5. 候选结构需要从 A/B/C 改为 A/B + SKIP 状态字段。
6. 候选列表只展示 A级候选、B级候选，不展示 C级观察分组。
7. C 不再参与 UI / 验证 / 分析；只能在非页面 raw audit/status 中保留 deprecated evidence。
8. HT 字段显示疑似错误，必须优先使用正式 ht_score，并避免把 HT score 渲染成百分比。
9. 强度缺失显示为 `强度 -` 是错误，缺失字段必须从主信息行隐藏。
10. 每日 brief 和 validation 自动刷新链路需要固化，防止旧数据、C active、7日验证再次回流。

## PASS Condition

问题清单完整；本轮设计不保留 C级观察为 active 展示。

## BLOCKER Condition

任何计划继续保留 C级观察为 active dashboard 展示、active validation 或 active analysis。
