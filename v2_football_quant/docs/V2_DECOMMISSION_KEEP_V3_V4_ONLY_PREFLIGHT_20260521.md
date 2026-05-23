# V2 Decommission Keep V3/V4 Only Preflight 20260521

Status: WARN_ONLY

## Direct Answers

1. V2 active files: 192
2. V2 cron references: 259
3. V2 dashboard modules/files: 11
4. V2 checker files: 76
5. V2 referenced by V3/V4 runtime imports: V3=False, V4=False
6. Can remove V2 active: true, execution phase required
7. Archive-only files: 596
8. Git delete candidates: 178
9. DO_NOT_TOUCH / keep files: 70
10. Can enter execution stage: true, with separate BOSS instruction only

## Boundary

- No files deleted.
- No files moved.
- No capture ran.
- No QQ push.
- No cron enabled.
- No cloud publish.
- V33 is not V3 and remains forbidden as active source.
- V4 strategy and candidate numbers were not changed.

## Key Findings

- Runtime dashboards still show V2/BET_LOCKED/PRODUCTION_VERIFIED language and must be removed from active UI in execution phase.
- V2 checker/tool/engine files remain present and are planned for archive/delete candidate handling.
- V2 status markers remain as historical evidence and must be excluded from active scans.
- New active manifest target is V3/V4-only and contains no V2 active source.

## Validation Matrix

- v2_decommission: WARN_ONLY
- repo_active_file_singleton: WARN_ONLY
- openclaw_active_source_manifest: WARN_ONLY
- cloud_bundle_excludes_archive: WARN_ONLY
- v4_review_report_only_mode: PASS
- intel_ops_console_daily_refresh_pipeline: WARN_ONLY (checker missing; WARN_ONLY)

Overall validation status: WARN_ONLY
