# V4 Attribution Guard

Phase: V4-E
Date: 2026-05-19
Status: FINAL

## 1. Attribution Input Requirements

- Must be based on V4 structured output (A/B/C/SKIP)
- Must preserve original_grade from scout/recommendation pipeline
- Must preserve source_trace for data lineage
- Must preserve guard_status from pipeline guards
- Must have match_id (fixture_id)
- Must have HT result or mark as UNKNOWN

## 2. Attribution Output Requirements

- Only allowed status: HIT / MISS / VOID / UNKNOWN / SKIP_NOT_SCORED
- SKIP must always produce SKIP_NOT_SCORED
- C must always be observation-only (not counted in primary stats)
- UNKNOWN result must NOT be written as HIT or MISS
- Must NOT write verified markers
- Must NOT modify strategy rules

## 3. Failure Categories

| Category | Description |
|----------|-------------|
| no_ht_goal | No first-half goal observed |
| late_goal_after_ht | Goal scored after half-time only |
| data_quality_issue | Input data insufficient or unreliable |
| source_quality_issue | Source data quality below threshold |
| fixture_mismatch | Fixture identification mismatch |
| odds_context_mismatch | Odds movement contradicted grade |
| lineup_context_mismatch | Lineup changes affected outcome |
| weather_or_external_context | Weather or external factors |
| unknown_result | Cannot determine match result |
| guard_blocker | Guard validation prevented attribution |
| skipped_case | Match was in SKIP pool |

## 4. Prohibited Actions

| Action | Reason |
|--------|--------|
| Single-day result triggers rule change | Insufficient sample |
| AI free grade recalculation | Strategy bypass |
| SKIP counted as recommendation hit | Contamination |
| C counted as primary hit | Misrepresentation |
| Attribution writes PRODUCTION_VERIFIED | Scope breach |
| Attribution triggers QQ push | Delivery breach |
| Attribution calls API with keys | Security breach |
| API calls without --allow-api | Guard violation |
| --dry-run calls API | Guard violation |
| --validate-only calls run() | Guard violation |

## 5. No-API Guard (V4-E.1)

- `--allow-api` flag required for any API call (default: false)
- `--validate-only` MUST NOT enter `run()` — no API, no writes, no side effects
- `--dry-run` MUST default `allow_api=false` — no API, generates UNKNOWN attribution
- When API disabled: attribution_status MUST be UNKNOWN, NOT HIT/MISS
- This phase: `--allow-api` is forbidden for production runs
- V4-F: review allow_api execution before allowing
- All API calls are guarded by `if allow_api:` block
- `net_utils.api_get()` only called within `allow_api=True` code path
| Attribution writes state files | State breach |
| Attribution modifies strategy algorithm | Strategy breach |
