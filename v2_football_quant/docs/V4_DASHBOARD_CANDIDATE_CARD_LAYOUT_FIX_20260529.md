# V4 Dashboard Candidate Card Layout Fix

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_CANDIDATE_CARD_LAYOUT_FIX_PASS
**Commit**: (see below)

## Problem

Candidate cards in the action area had inconsistent heights and misaligned form areas due to:
- `.candidate-list` grid missing `align-items: stretch`
- `.candidate` cards not using flex column layout
- `.quick-form` forms floating at different vertical positions
- `.match` title allowing unlimited text expansion

## Fix

### CSS Changes

1. **`.candidate-list`** — added `align-items: stretch` to make grid children fill row height
2. **`.candidate`** — added `display: flex; flex-direction: column; height: 100%` for equal-height cards with bottom-aligned content
3. **`.match`** — added `-webkit-line-clamp: 2` to prevent long team names from stretching cards
4. **`.quick-form`** — changed `margin-top: 10px` → `margin-top: auto` so forms stick to card bottom
5. **`.field textarea`** — added `max-height: 60px; resize: none` for consistent note area height

### How It Works

```
.candidate-list (grid, align-items: stretch)
  ┌─────────────────────┐  ┌─────────────────────┐
  │ .candidate (flex col)│  │ .candidate (flex col)│
  │   cand-top          │  │   cand-top          │
  │   badges            │  │   badges            │
  │                     │  │                     │
  │   ← margin-top:auto │  │   ← margin-top:auto │
  │   quick-form        │  │   quick-form        │
  └─────────────────────┘  └─────────────────────┘
```

### Protection
| Check | Status |
|-------|--------|
| DEFAULT_RULES unchanged | ✓ |
| Validation not recomputed | ✓ |
| Live bet unchanged | ✓ |
| Cron unchanged | ✓ |
| QQ not pushed | ✓ |
| No secrets | ✓ |
