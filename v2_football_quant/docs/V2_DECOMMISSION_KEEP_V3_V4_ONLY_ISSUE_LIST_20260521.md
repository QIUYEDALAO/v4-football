# V2 Decommission Keep V3/V4 Only Issue List 20260521

Status: PASS (preflight issue list only)

1. V2 active code still exists and must be removed from current active source.
2. V2 cron/status payloads may still exist and must be disabled/deleted from active cron in execution phase.
3. V2 dashboard modules still appear in runtime dashboards and must be removed from active UI.
4. V2 validation and BET_LOCKED wording is no longer needed as active operational state.
5. V2 checker files still exist and can influence OpenClaw if active scans include them.
6. V2 status markers still exist under runtime/status and may be read by broad active scans.
7. Cloud publish bundle/publish scripts may still include dashboard/status files with V2 content.
8. current_ops_manifest must be replaced by a V3/V4-only active manifest.
9. Daily refresh/intel console pipeline must remove V2 modules from active output.
10. Docs can retain V2 only as archive/historical evidence, not current source.

Boundary: V2 is not retained as active source; this phase does not delete or move files.
