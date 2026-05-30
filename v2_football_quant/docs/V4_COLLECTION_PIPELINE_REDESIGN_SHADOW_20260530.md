# V4_COLLECTION_PIPELINE_REDESIGN_SHADOW_20260530

## Scope
- Phase: `V4_COLLECTION_PIPELINE_REDESIGN_SHADOW`
- Target: shadow collection pipeline only
- Kept unchanged: official grade rules, DEFAULT_RULES, A/B thresholds, cron policy, validation history, live bet raw records, QQ push behavior

## Implemented

### 1) Collection order redesign in `engine/v4_runner.py`
New shadow collection order is now:
1. RF-first (`build_recent_form_shadow_from_recent`)
2. Opening Market-before-H2H (`odds?fixture=...` + `_best_pre_live_line`)
3. RF prefilter (`_shadow_prefilter_decision`)
4. Lazy H2H (only when `h2h_required=true`)
5. Lazy Events (only when `events_required=true`, passed into `evaluate_h2h_edge`)
6. Lazy CPL placeholder (`cpl_required` marker only, no full CPL collection call)

### 2) Lazy Events in `engine/data_sources/h2h_engine.py`
`evaluate_h2h_edge` now supports optional flags:
- `include_h2h_events`
- `include_recent_events`

Defaults preserve legacy behavior for other callers; `v4_runner` uses flags to avoid full-volume events calls.

### 3) New shadow collection fields
Added and propagated:
- `collection_stage`
- `rf_collected`
- `market_collected`
- `prefilter_done`
- `h2h_required`
- `h2h_skipped_reason`
- `h2h_collected`
- `events_required`
- `events_skipped_reason`
- `events_collected`
- `cpl_required`
- `cpl_skipped_reason`
- `cpl_collected`
- `expensive_calls_saved`
- `collection_reason`

### 4) Field propagation
- `engine/v4_scan_and_brief.py`: shadow field mapping updated
- `tools/build_v4_control_center_model.py`: dashboard model merge fields updated

### 5) New checker
Created:
- `tools/check_v4_collection_pipeline_redesign_shadow.py`

Checker validates source-order, gating rules, field propagation, and safety boundaries (DEFAULT_RULES/cron/validation/live_bet/QQ push).

## Execution records

### Formal entry dry-run
Attempted command:
```bash
python3 engine/v4_scan_and_brief.py --scan-date 20260530 --window midday --no-push --scan-engine serial --fixture-universe whitelist
```
Result:
- blocked by missing env vars in `config/secrets.py`
- required vars not present in current shell:
  - `APIFOOTBALL_KEY`
  - `OPENCLAW_APIFOOTBALL_KEY`

### Checker / rebuild
- `python3 tools/build_v4_control_center_model.py` -> PASS
- `python3 tools/check_v4_collection_pipeline_redesign_shadow.py` -> WARN_ONLY (runtime scout file stale; source-level checks pass)

## Notes
- This patch intentionally does not alter official grading rules or DEFAULT_RULES logic.
- Runtime full verification requires API env injected and one successful formal no-push scan run to refresh scout rows with new collection fields.
