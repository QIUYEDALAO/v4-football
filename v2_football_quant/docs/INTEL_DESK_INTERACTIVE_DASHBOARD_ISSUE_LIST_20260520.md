# Intel Desk Interactive Dashboard — Issue Inventory 20260520

**Phase:** INTEL-DESK-INTERACTIVE-DASHBOARD-V1-20260520
**Generated:** 2026-05-20T16:00:00+08:00
**Issues:** 10

---

| # | Category | Issue | Location |
|:--|:---|:---|:---|
| 1 | Field conflict | CURRENT 内 `next_window=midday 14:05 one-shot` 与顶部/底部 `night 22:20` 不一致 | generator line ~112 |
| 2 | Field conflict | B卡片 `source_window=midday` 但 top-level `source_window=evening` | candidate JSON B_candidates entries |
| 3 | Field conflict | 顶部 `next_window=night 22:20` 与 footer `Next: night 22:20` 一致但 CURRENT 卡片未同步 | generator hardcode |
| 4 | UX density | 信息密度高，无折叠/筛选，手机阅读累 | all pages |
| 5 | Missing timeline | 无窗口时间线（early→midday→evening→night） | no component exists |
| 6 | Missing filter | 无 A/B/C/SKIP 分层切换 | no component exists |
| 7 | Missing status | 无 review / QQ gate / night one-shot 聚合状态面板 | no component exists |
| 8 | Missing provenance | 无 source_hash / data freshness 可视化 | only in metadata |
| 9 | Missing audit | 异常区与历史审计未折叠，污染 CURRENT 视觉 | History section |
| 10 | Missing entry | 无统一仪表总台入口 | index.html |
