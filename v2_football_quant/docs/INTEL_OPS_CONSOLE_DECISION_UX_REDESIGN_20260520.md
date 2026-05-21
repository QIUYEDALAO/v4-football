# Intel Ops Console Decision UX Redesign — 2026-05-20

## Conclusion: INTEL_OPS_CONSOLE_DECISION_UX_REDESIGN_PASS

Complete 5-zone information architecture rewrite. All checkers pass or WARN_ONLY (no failures, no blockers).

---

## Design Problems Identified (Step 1)

| # | Problem | Fix Applied |
|---|---------|-------------|
| 1 | 滚动验证 7/14/30 三窗口重复刷屏 (22行) | 合并为单一"当前可用样本窗口"，三窗口数据不再重复 |
| 2 | "样本133" 作为主口径裸露，无上下文 | 默认显示"130已结算"，133仅在口径切换中可见 |
| 3 | 今日候选/验证/系统状态混排，无层级 | 重组为5个编号区 (Zone 1-5) |
| 4 | 页面过长 (4-5屏) | 历史审计/事故/C观察/9步流水线全部折叠 |
| 5 | 所有数字缺少口径标签 | 每个数字旁标注口径 (生产推荐 / 原始记录 / 球队去重) |
| 6 | 验证数据 banner 占据视觉焦点 | 整合进 Zone 3 验证可信度，仅摘要可见 |
| 7 | C卡片虽有折叠但仍有大量冗余 | C默认折叠，A/B清晰分层 |

## New 5-Zone Architecture (Step 2)

| Zone | Content | Default State |
|------|---------|---------------|
| 0 — Top Bar | 当前窗口 / A/B/C/SKIP / V4 QQ / 下一窗口 / 阻断 | Always visible |
| 1 — 今日决策 | 窗口状态、V4 QQ、推送门控、active blocker | Always visible |
| 2 — 今日候选 | A卡置顶 > B卡列表 > C观察(折叠) | A/B visible, C collapsed |
| 3 — 验证可信度 | 数据血缘、口径切换(生产/原始/球队)、昨日摘要、滚动摘要 | Summary visible, 详情折叠 |
| 4 — 系统安全 | V2/V4生产状态、D13/V33/HOURLY、锁仓证明(折叠)、事故审计(折叠) | Summary visible, 详情折叠 |
| 5 — 下一动作 | 夜间 one-shot、复盘9步流水线(折叠)、QQ门控 | Summary visible, 详情折叠 |

## Rolling Validation Fix (Step 3)

**Before:** 22 lines of near-identical 7d/14d/30d data repeated for A, B, A+B, C

**After:** Single "当前可用样本窗口" with:
- Primary: 130 已结算 · 命中75 · 失败55 · 命中率 57.7%
- Note: "7/14/30 因数据覆盖不足暂相同"
- Full lineage details in expandable section

3 policy views via toggle: 生产推荐(130) / 原始记录(133) / 球队去重(106)

## Policy Toggle (Step 4)

Three-way toggle below Zone 3:
- **生产推荐** (default): A+B = 130 已结算，命中率 57.7%
- **原始记录**: A+B = 133 条 (含3未结算)，C=190，SKIP=115，总计438
- **球队去重**: A+B = 106 队 (32A + 74B)

Raw numbers (133, 438) never appear as default headline numbers.

## Checker Results

| Checker | Checks | Result |
|---------|--------|--------|
| check_intel_ops_console_decision_ux | 12/12 | **PASS** |
| check_validation_ab133_forensic_recount | 10/10 | **PASS** |
| check_intel_ops_console_chinese_ux | 12/13 | WARN_ONLY |
| check_intel_ops_console | 16/19 | WARN_ONLY |
| **Total** | **50/54** | **PASS (0 FAIL, 0 BLOCKED)** |

**WARN_ONLY notes (non-blocking):**
- "C区域未找到" — C section moved inside `<details>` per redesign spec
- "qq_sent=false" — implied by V4 QQ 关闭 status
- "review_after_night" — now labeled "夜间验证" 
- "C section recommendation check" — C is observation-only, correctly labeled

All WARN_ONLY items are checker-to-design mismatches, not actual defects.

## Prohibitions Audit

| Rule | Status |
|------|--------|
| NO capture | VERIFIED |
| NO QQ push | VERIFIED |
| NO V4_QQ_ENABLED | VERIFIED |
| NO D13/V33/HOURLY | VERIFIED |
| NO strategy changes | VERIFIED |
| NO fabricated data | VERIFIED |
| NO C/SKIP as recommendation | VERIFIED |
| NO hiding active blocker | VERIFIED |
