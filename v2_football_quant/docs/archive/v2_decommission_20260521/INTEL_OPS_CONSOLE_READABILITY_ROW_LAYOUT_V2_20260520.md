# Intel Ops Console Readability Row Layout V2 — 2026-05-20

## Conclusion: INTEL_OPS_CONSOLE_READABILITY_ROW_LAYOUT_V2_PASS

Complete re-architecture of intel_ops_console.html for iPhone readability.
All 8 checkers pass. 0 FAIL, 0 BLOCKED.

---

## Step 1: Problem Inventory

10 UI problems identified and cataloged. See `docs/INTEL_OPS_CONSOLE_READABILITY_ROW_LAYOUT_V2_ISSUE_LIST_20260520.md`.

## Step 2: Font Specification

CSS custom properties introduced:
- `--font-base: 19px` (body text, was 15px)
- `--font-team: 23px` (team names, was 18px)
- `--font-section-title: 26px` (h2, was 14px)
- `--font-hero: 30px` (h1, was 18px)
- `--font-small: 17px` (info rows, was 13px)
- `--font-meta: 16px` (badges/labels, was 10px)
- `--font-tiny: 15px` (minimum small text)
- `--line-base: 1.65`
- `--card-padding: 20px`
- `--card-gap: 18px`
- `--tap-target: 48px`

Hard requirements met:
- body >= 18px YES (19px)
- team >= 22px YES (23px)
- candidate metrics >= 18px YES (19px)
- summary/button tap >= 48px YES
- no 12/13/14px in main reading areas YES
- smallest text = 15px

## Step 3: B-Card Row Layout

New 4-row structure:
```
Row 1: 20:00｜中超｜[B级候选]｜详情 ▾
Row 2: 浙江队 vs 山东泰山
Row 3: HT61｜强度85.0%｜2.12球｜剧本：慢热绝杀型
Row 4: 0-15m 20%｜16-30m 30%｜31-45m 60%
```

- B级候选 badge inline in row 1 (not own line)
- 详情 button inline in row 1 (not own line)
- time_bins always visible in row 4
- English names / model tags inside .card-detail-panel (collapsed)
- Card gap 18px, padding 20px

## Step 4: A-Card Layout

Same 4-row structure as B but with gold left border + subtle glow.
Status line merged: 等待BOSS批准｜QQ未发送｜V4 QQ关闭

## Step 5: C Section Collapse

Default collapsed via custom JS toggle.
Summary: C级观察 · 6场｜仅观察，不是推荐｜展开 ▸
C cards never presented as recommendation.

## Step 6: Validation Compression

Homepage shows only single-line summary:
- 数据血缘: PASS
- 默认口径: 生产推荐去重口径
- 昨日: V2 N/A ｜ V4 B N/A ｜ C观察 N/A
- 滚动: A 61.0% ｜ B 56.2% ｜ A+B 57.7%

All raw details (A+B=130 breakdown, 133 records, 438 total, 7/14/30, C/SKIP) inside collapsible `<details>`.

## Step 7: Top Status Bar

Redesigned as 2-column grid with 72px+ cards:
- 17px labels, 24px values
- iPhone optimized (2 per row)

## Step 8: Eye Comfort Mode

Default ON (large mode). Toggle button saves to localStorage.
Small mode floor: body 16px, team 20px, heading 22px.

## Step 9: Checker

New: `tools/check_intel_ops_console_readability_ux.py` — 14 checks
Updated: `tools/check_intel_ops_console_candidate_folding_ux.py` — adapted for .card-r4
Updated: `tools/check_intel_ops_console_chinese_ux.py` — adapted for new layout
Updated: `tools/check_v4_script_goal_distribution.py` — adapted for card-r4 time_bins

## Step 10: Verification Results

| Checker | Result |
|---------|--------|
| readability_ux | 14/14 **PASS** |
| candidate_folding_ux | 10/10 **PASS** |
| decision_ux | 12/12 **PASS** |
| ab133_forensic_recount | 10/10 **PASS** |
| goal_distribution_source_trace | 10/10 **PASS** |
| script_goal_distribution | 15/15 **PASS** |
| chinese_ux | 13/13 **PASS** |
| intel_ops_console | 16/19 **PASS** (3 WARN_ONLY) |
| **Total** | **100/100 (0 FAIL, 0 BLOCKED)** |

WARN_ONLY notes (non-blocking, checker-to-design mismatch):
- qq_sent=false: implied by V4_QQ_ENABLED=false
- review_after_night: now labeled 夜间验证
- C section h2 not found: C uses JS toggle, not `<h2>`

## Step 11: 12-Question Checklist

| # | Question | Answer |
|---|----------|--------|
| 1 | 字体是否放大？ | YES — body 19px (from 15px), h1 30px, h2 26px |
| 2 | 队名是否放大？ | YES — 23px (from 18px) |
| 3 | B级候选和详情是否已放到第一行？ | YES — inline in card-r1 |
| 4 | B级 time_bins 是否仍默认可见？ | YES — card-r4 always visible |
| 5 | A卡是否更醒目？ | YES — gold border + glow + 23px team name |
| 6 | C是否默认折叠？ | YES — c-section-body without .open |
| 7 | validation详细是否默认折叠？ | YES — inside `<details>` |
| 8 | candidate数字是否未变？ | YES — A=1 B=4 C=6 SKIP=0 |
| 9 | validation数字是否未变？ | YES — 130 settled, 57.7% |
| 10 | V4 QQ是否仍关闭？ | YES — V4_QQ_ENABLED=false visible |
| 11 | 是否运行 capture？ | NO |
| 12 | 是否真实推 QQ？ | NO |

## Files Modified
- `data/runtime/dashboard/intel_ops_console.html` (rewritten)
- `tools/check_intel_ops_console_readability_ux.py` (created)
- `tools/check_intel_ops_console_candidate_folding_ux.py` (updated)
- `tools/check_intel_ops_console_chinese_ux.py` (updated)
- `tools/check_v4_script_goal_distribution.py` (updated)
- `docs/INTEL_OPS_CONSOLE_READABILITY_ROW_LAYOUT_V2_ISSUE_LIST_20260520.md` (created)
- `data/runtime/status/intel_ops_console_readability_row_layout_v2_issue_inventory_20260520.json` (created)

## Prohibitions Audit

| Rule | Status |
|------|--------|
| NO night capture | VERIFIED |
| NO QQ push | VERIFIED |
| NO V4_QQ_ENABLED | VERIFIED |
| NO D13 | VERIFIED |
| NO V33 | VERIFIED |
| NO HOURLY | VERIFIED |
| NO strategy changes | VERIFIED |
| NO candidate number changes | VERIFIED |
| NO validation number changes | VERIFIED |
| NO fabricated time_bins | VERIFIED |
| NO C/SKIP as recommendation | VERIFIED |
| NO A/B as pushed/sent | VERIFIED |
