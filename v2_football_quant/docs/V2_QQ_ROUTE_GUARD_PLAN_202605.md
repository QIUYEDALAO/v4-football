# V2 QQ Route Guard Plan — 2026-05-19
**STATUS: PLAN ONLY — QQ NOT ENABLED**

## Default: allowed_to_send=false
- QQ route guarded by safe_outbound_sender
- Only BET_LOCKED fixtures enter QQ candidate set
- C/SKIP/WATCH_EARLY/CANDIDATE never pushed

## Preconditions for QQ
- guard_status=PASS
- route_marker exists
- sent_marker exists
- duplicate suppression active
- message_hash verified
- BOSS approval required per-send
