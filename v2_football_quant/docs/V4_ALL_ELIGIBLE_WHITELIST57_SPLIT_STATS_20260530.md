# V4 All Eligible Scan with Whitelist57 Split Stats

**Date:** 2026-05-30
**Status:** CODE_READY

## Summary

Expand V4 production candidate discovery beyond the 57-league whitelist while preserving league and data quality gates. Every candidate is tagged as WHITELIST_57 or OUTSIDE_57. Split statistics track A/B hit rates separately for whitelist-inside and whitelist-outside leagues.

## Key Changes

### 1. Fixture Universe (`--fixture-universe`)
- New `--fixture-universe whitelist|all_eligible` parameter across all entry points
- `whitelist` mode: original behavior (57 whitelist only) — retained as fallback
- `all_eligible` mode: scan all leagues that pass the league eligibility gate
- League gate excludes: cup, friendly, unknown competition, bad metadata
- Business window preserved: BJ 12:00 → next day 12:00

### 2. Source Labels
Every candidate now carries:
- `source_group`: `WHITELIST_57` or `OUTSIDE_57`
- `is_in_57_whitelist`: boolean
- `fixture_universe`: `all_eligible` or `whitelist`
- `scoring_complete`: boolean
- `recent_form_sample_size`: 10 (fixed)

### 3. Candidate View (schema v2)
```
A_count, B_count, C_count(=0), SKIP_count
DATA_TIMEOUT_count, SCORE_INCOMPLETE_count
A_WHITELIST_57_count, A_OUTSIDE_57_count
B_WHITELIST_57_count, B_OUTSIDE_57_count
```

### 4. Validation Layered Statistics
New layered buckets in `v4_rolling_validation.py`:
- AB_ALL, AB_WHITELIST_57, AB_OUTSIDE_57
- A_ALL, A_WHITELIST_57, A_OUTSIDE_57
- B_ALL, B_WHITELIST_57, B_OUTSIDE_57
- UNKNOWN_LEGACY for old samples without source_group

Each with: sample_count, hit_count, miss_count, hit_rate, pending_count

### 5. Dashboard
- Shows today's A/B counts split by WHITELIST_57 / OUTSIDE_57
- SKIP, DATA_TIMEOUT, SCORE_INCOMPLETE excluded from pending
- C not displayed
- No undefined values

### 6. 12:00 Payload
```
python3 -u engine/v4_scan_and_brief.py \
  --date $(date +%Y%m%d) \
  --scan-engine parallel \
  --fixture-universe all_eligible \
  --write-official-output \
  --outside57-workers 8 \
  --outside57-api-rpm 290 \
  --outside57-api-rpm-hard-cap 300 \
  --outside57-max-inflight 30 \
  --outside57-resume \
  --no-push
```

## Safety Gates (all preserved)
- DEFAULT_RULES unchanged (hash: 55036a0d551c72a3)
- A threshold: ht_score ≥ 70
- B threshold: ht_score ≥ 60
- C disabled (C_count = 0)
- QQ push disabled (V4_QQ_ENABLED = False)
- Validation history NOT recomputed
- Live bet records NOT modified
- SKIP not in live bet pending
- DATA_TIMEOUT not in A/B
- SCORE_INCOMPLETE not in A/B
- 13:00/13:30/14:00 payloads unchanged

## Files Modified
- `engine/v4_runner.py` — fixture_universe + league gate + source labels
- `engine/v4_scan_and_brief.py` — --fixture-universe arg + candidate_view v2
- `engine/v4_scan_worker.py` — --fixture-universe arg pass-through
- `engine/v4_outside57_scanner.py` — source labels in result_base
- `engine/v4_dashboard.py` — split display + candidate_view merge
- `engine/v4_rolling_validation.py` — layered stats + UNKNOWN_LEGACY

## Files Created
- `tools/check_v4_whitelist57_split_stats.py` — 30-point code checker
- `tools/check_v4_all_eligible_candidate_pool.py` — candidate pool integrity checker
- `data/runtime/status/v4_all_eligible_whitelist57_freeze_20260530.json`
- `data/runtime/status/v4_all_eligible_whitelist57_step7_payload_20260530.json`
- `data/runtime/status/v4_all_eligible_whitelist57_dry_run_20260530.json`
- `docs/V4_ALL_ELIGIBLE_WHITELIST57_SPLIT_STATS_20260530.md`

## Checker Results
- `check_v4_whitelist57_split_stats.py`: 30/30 PASS
- `check_v4_all_eligible_candidate_pool.py`: code-level checks PASS (data-level requires real scan)
