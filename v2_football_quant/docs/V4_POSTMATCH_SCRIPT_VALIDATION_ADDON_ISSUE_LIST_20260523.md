# V4 Postmatch Script Validation Addon Issue List 20260523

1. 当前赛后验证只有结果命中率。
2. 当前缺少剧本验证。
3. 剧本字段来自赛前 candidate/formal attribution source。
4. 剧本验证必须基于赛后事件走势。
5. 剧本验证不能混入 A/B 命中率。
6. brief 不能用于剧本验证。
7. API disabled 时剧本验证显示 N/A。
8. C 已废弃，不进入剧本验证。
9. 剧本验证必须使用 match_date。
10. checker 必须防止剧本验证缺失但 PASS。

PASS: 问题清单完整；剧本验证保持独立，不混入 A/B 命中率。
