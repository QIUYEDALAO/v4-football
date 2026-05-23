# V4 Script Validation UI Compact Rework Issue List 20260524

1. 剧本验证当前与结果验证视觉混杂。
2. 昨日 N/A 与累计 A/B/A+B 挤在同一行。
3. 黄色高亮过强。
4. 剧本验证率未说明是走势吻合率。
5. 剧本验证不应影响 A/B 结果命中率。
6. 剧本验证应默认紧凑展示。
7. 详细 A/B 拆分应放入折叠区。
8. SCRIPT_UNKNOWN 不进分母必须说明。
9. dashboard API disabled 状态可能 stale。
10. checker 必须防止剧本验证 UI 回到混乱状态。

PASS: 问题清单完整；剧本验证将作为辅助复盘模块，不与结果命中率同视觉层级。
