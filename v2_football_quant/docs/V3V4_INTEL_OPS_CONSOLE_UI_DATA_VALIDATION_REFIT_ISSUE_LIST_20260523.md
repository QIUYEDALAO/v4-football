# V3/V4 Intel Ops Console UI Data Validation Refit Issue List — 20260523

status: PASS
issues_count: 10
phase: V3V4-INTEL-OPS-CONSOLE-UI-DATA-VALIDATION-REFIT-20260523

## 问题清单

1. A/B/C 卡片背景颜色不统一，当前视觉容易把等级变成整卡大色块，而不是信息层级。
2. 中文队名缺失或未优先显示，正式情报台主行必须优先中文名，英文名只能进入技术血缘/副信息。
3. 当前页面 generated=2026-05-23 但 scan_date=20260522，不能继续标成“今日候选”。
4. “今日决策”与“V4 情报状态”功能重复，候选数量应并入 V4 情报状态。
5. 缺少 V3/V4 比赛验证模块，不能只展示候选结构。
6. 缺少昨日 / 7日 / 累计命中展示，且必须来自正式 attribution / validation / review 产物。
7. C 观察层需要明确不进正式 A+B 命中率，C 仍然只观察，不是推荐。
8. V3 战备窗口需要补齐；没有 V3 实盘数据时必须显示预留窗口。
9. checker 对日期错配、英文队名主行、V2 残留的硬拦截不够，存在 false pass 风险。
10. daily refresh 必须基于当前 active source，不得读旧文件冒充今日，不得运行 capture / push / cloud。

## BLOCKER 判定

- 仍允许页面把旧数据标成今日：BLOCKER。
- 页面主区域出现 V2 / BET_LOCKED / V33 active：BLOCKER。
- 验证数据自由重算或伪造命中率：BLOCKER。
