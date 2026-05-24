# V3V4_INTEL_CENTER_TEAM_CN_DISPLAY_FULL_FIX_ISSUE_LIST_20260525

1. 主情报台仍大量英文球队名。
2. outside_57 页面也可能英文球队名。
3. candidate_view / observation_pool 可能缺 home_team_cn / away_team_cn。
4. renderer 可能使用英文 fallback。
5. checker 之前没有强制拦截主显示英文名。
6. 本轮只修展示层 / 映射层。
7. 不改策略、不改评级、不改验证结果。
8. 英文名允许保留为审计小字。
9. 中文缺失必须写 missing list。
10. 修完必须本地和云端都验证。

Step 1: PASS
BLOCKER 定义：仍允许主显示静默 fallback 英文。
