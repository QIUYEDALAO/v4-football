# V4 Dashboard Final Polish

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_FINAL_POLISH_PASS
**Commit**: (see below)

## Fixes

### 1. Chinese Team Name Display
Added `TEAM_ALIAS_ZH` alias map in `matchName()` function:
- Rosenborg → 罗森博格
- Bodo/Glimt → 博德闪耀
- TransINVEST Vilnius → 特兰斯因维斯特
- Hegelmann Litauen → 赫格尔曼

Fallback: if no alias, uses raw name.

### 2. Litauen Field Leakage Fix
"Hegelmann Litauen" (API returns country suffix) now mapped to "赫格尔曼" via alias. No country leakage in candidate cards.

### 3. Validation N/A Cleanup
- KPI defaults: `N/A` → `暂无`
- Validation detail defaults: `N/A` → `暂无`
- `renderTop` validation `safe()` calls: fallback changed from `'N/A'` to `'暂无'`
- General `safe()` function unchanged (preserves N/A for other contexts)

### Files Changed
- `data/runtime/dashboard/v4_control_center.html` — matchName alias map, validation N/A cleanup
- `tools/check_v4_dashboard_final_polish.py` — new checker
- `docs/V4_DASHBOARD_FINAL_POLISH_20260529.md` — this doc

### Candidate Card Display (Final State)
1. 罗森博格 vs 博德闪耀 (A)
2. 特兰斯因维斯特 vs 赫格尔曼 (B)
3. 进球时间分布 0-15 x% · 16-30 x% · 31-45 x%
4. 未投注 · 盘口/水位/金额/分钟

### Protection
| Check | Status |
|-------|--------|
| DEFAULT_RULES unchanged | ✓ |
| A/B thresholds unchanged | ✓ |
| Validation not recomputed | ✓ |
| Live bet unchanged | ✓ |
| Cron unchanged | ✓ |
| QQ not pushed | ✓ |
| No secrets | ✓ |
