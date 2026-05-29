# V4 Dynamic League Classifier False Positive Fix — 2026-05-29

## Problem

`_is_non_senior_league()` in `engine/data_sources/h2h_engine.py` used bare
`"ii"` as a reserve keyword substring match. This caused false positive
classification of senior leagues whose names contain the substring `ii`.

### Affected leagues in current data

| League | Country | Actual Type | False Classification |
|---|---|---|---|
| Meistriliiga | Estonia | Senior top division | reserve |
| Esiliiga | Estonia | Senior second division | reserve |
| Esiliiga B | Estonia | Senior second division B | reserve |
| Ykkösliiga | Finland | Senior second division | reserve |
| Veikkausliiga | Finland | Senior top division | reserve |
| III Liga Group 3/4 | Poland | Senior fifth division | reserve |

## Fix

Replaced bare `"ii"` with word-boundary patterns:

- Removed: `"ii"` (bare substring)
- Added: `" ii "` (standalone word with spaces)
- Added: `"ii team"` (explicit second-team pattern)
- Added: `"b team"`, `"b-team"` (explicit B-team patterns)
- Kept: `"reserve"`, `"reserves"`, `" b "`, `"second team"`, `"2nd team"`

## Verification

- 40 senior league names correctly classified as senior (0 false positives)
- 46 non-senior league names correctly excluded (0 missed)
- DEFAULT_RULES unchanged
- A/B thresholds unchanged
- H2H engine thresholds (REFERENCE_MIN_SAMPLES=4, STRONG_SAMPLE_SIZE=8, STRONG_RATE_MIN=0.75) unchanged

## Commit

`v4: tighten dynamic league classifier`
