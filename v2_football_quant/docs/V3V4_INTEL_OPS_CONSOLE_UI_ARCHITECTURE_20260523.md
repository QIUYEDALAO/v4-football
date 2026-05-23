# V3/V4 Intel Ops Console UI Architecture - 2026-05-23

## Goal

Rebuild the active intelligence console as a V3/V4-only mobile card interface after V2 purge. The page title is `情报决策总台 — V3/V4`.

## Top KPI Cards

1. 今日扫描: completed / running / not started.
2. 候选结构: A / B / C / SKIP.
3. 复盘状态: 等待赛果 / 可复盘 / REPORT_ONLY.
4. 阻断: blocker count.

## Main Layout Order

1. 今日决策.
2. V4 情报状态.
3. 今日候选.
4. V3 战备窗口.
5. 系统安全.
6. 下一动作.
7. 系统审计折叠区.

## Candidate Cards

- A/B/C groups are collapsible.
- A defaults open.
- B and C default collapsed.
- Each A/B card has four rows: time/league/grade, home vs away, HT/strength/goals/script, time bins.
- C section states: `C级仅观察，不是推荐`.
- No per-match technical detail button. Technical lineage is group-level collapsed evidence only.

## V3 Readiness Window

If no active V3 status marker exists, the console shows V3 readiness as reserved: waiting for schedule/intelligence source, Perception Gap pending, not participating in V4 recommendations.

## Safety Panel

The safety panel must not display legacy module names. It shows:

- V3 active: readiness/reserved.
- V4 review: REPORT_ONLY.
- legacy modules: disabled.
- QQ推送: 关闭.
- capture/cloud: 关闭.
- cron: 未启用 / status-only.

## Prohibited Active Dashboard Text

- `V2 active`.
- `BET_LOCKED`.
- V2 historical pool / lock / validation / QQ wording.
- Legacy generation active wording.

Status: PASS.
