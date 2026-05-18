# V2 Settlement Production Preflight Gate

> Phase D.7 — Fail-closed guard before settlement writes verified.

## Rule

Settlement **must** be blocked unless ALL conditions met:

1. `official_bet_locked > 0`
2. `window_checker new_locks_count > 0`
3. Every target has `lock_owner=window_checker`
4. Every target has `official_bet_locked=true`
5. No missed candidates appear in targets
6. No DAILY_POOL candidate_stage in targets
7. Source markers present and readable

Missing any → **BLOCK**, no verified written.

## 20260517 Proof

- official_bet_locked=0 → BLOCK
- new_locks_count=0 → BLOCK
- missed candidates in verified → BLOCK
- lock_owner missing → BLOCK
- **Result: BLOCKED (4 reasons)**

## Verified now, not tomorrow

D.7 validated via:
1. Same-day 20260517 replay → BLOCKED
2. 4 synthetic cases → all expected
3. Preflight gate wired into settlement entry
4. Verified: no api, no push, no cron, no production_verified
