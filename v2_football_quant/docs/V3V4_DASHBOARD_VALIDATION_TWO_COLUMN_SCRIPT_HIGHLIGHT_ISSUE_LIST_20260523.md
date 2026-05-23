# V3/V4 Dashboard Validation Two Column Script Highlight Issue List 20260523

Phase: V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523

## Issues

1. 验证区上下堆叠导致 iPhone 页面过长。
2. 昨日验证和累计验证应在同一框架左右并排。
3. 验证主屏只保留 A/B/A+B。
4. C验证不得显示。
5. 近7天验证不得显示。
6. unknown 不应占主屏，只能进入折叠审计区。
7. 剧本值不够醒目。
8. 剧本值需要高亮，并与普通字段颜色区分。
9. 字段缺失仍不得显示 `-`。
10. checker 必须拦截 C验证 / 近7天 / 剧本未高亮回流。

## PASS Condition

问题清单完整；本轮设计不保留 C验证或近7天主屏展示。

## BLOCKER Condition

任何计划继续保留 C验证或近7天主屏展示。
