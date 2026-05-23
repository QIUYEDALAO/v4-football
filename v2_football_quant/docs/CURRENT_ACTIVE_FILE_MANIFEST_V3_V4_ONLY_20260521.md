# Current Active File Manifest V3/V4 Only 20260521

Status: PASS (new active-source target manifest; no V2 active source)

## V3
- Active: `engine/wc_model.py`, `engine/v3_config/v3_thresholds.json`, `engine/v3_config/intl_big4_master.json`, `docs/PROJECT_REPORT_V3.md`
- Definition: World Cup Perception Gap readiness system. V3 is not V33.
- Forbidden: V33 active source; V2 fallback as active source.

## V4
- Active: V4 candidate model, A/B/C/SKIP, review REPORT_ONLY, daily refresh source, dashboard renderer.
- Allowed grades: A, B, C, SKIP.

## Cloud
- readonly mirror only.
- reverse_sync=false.

## Cron
- Allowed future active tasks: V4 live snapshot, V4 review, V4 report-only.
- V2 cron: forbidden.

## Dashboard
- Intel ops console entrypoint only.
- Page must not display V2 modules after execution phase.
