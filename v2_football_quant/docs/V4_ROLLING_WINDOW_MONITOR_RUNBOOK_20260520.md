# V4 Rolling Window Monitor Runbook — 2026-05-20

| Window | Time | Status |
|--------|------|--------|
| late | 01:20 | ✅ CAPTURED (A=0,B=0,C=0,SKIP=0) |
| early | 07:20 | ⏸️ PENDING |
| midday | 14:05 | ⏸️ PENDING |
| evening | 16:20 | ⏸️ PENDING |
| night | 22:20 | ⏸️ PENDING |

Rules: WAIT if before window, GRACE 0-30min past, BLOCKER >30min without evidence.
