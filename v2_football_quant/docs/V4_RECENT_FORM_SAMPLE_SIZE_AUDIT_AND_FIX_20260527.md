# V4 Recent Form Sample Size Audit and Fix

## Overview

Phase: V4-RECENT-FORM-SAMPLE-SIZE-AUDIT-AND-FIX-20260527
Date: 2026-05-27
Auditor: OpenClaw

## Findings

### 1. What is the recent form API raw fetch size?

**3 matches.**

`engine/data_sources/h2h_engine.py` line 311:
```python
def _query_recent_goal_profile(api_client, team_id: int, last_n: int = 3, include_events: bool = True) -> dict:
```

Called at line 644-654:
```python
recent_last_n = 3
home_recent = _query_recent_goal_profile(api_client, home_id, last_n=recent_last_n, ...)
away_recent = _query_recent_goal_profile(api_client, away_id, last_n=recent_last_n, ...)
```

API endpoint: `fixtures?team={team_id}&last=3&status=FT`

### 2. What is the recent form scoring sample size?

**3 matches.**

All 3 matches returned by the API are used directly in scoring. No filtering or truncation occurs between fetch and score.

### 3. Was OpenClaw's claim of "拉近50场近期比赛画像" correct?

**No. The claim was incorrect.**

OpenClaw (myself) made an incorrect statement during troubleshooting about pulling "50 recent matches per team." The actual code pulls exactly 3 matches per team. This was an error in OpenClaw's analysis and is now corrected.

### 4. Is the scoring window within BOSS's 10-match requirement?

**Yes. raw_fetch=3, scoring=3. Both are well within BOSS's 10-match maximum.**

### 5. Is a fix needed?

**No fix needed.** The code already complies with BOSS's requirement. No code changes were made for the recent form sample size.

### 6. Why can raw_fetch be larger than scoring_sample_size?

This is an architectural note for future reference. In the pattern where raw_fetch > scoring_sample_size, the extra matches serve as a filtering pool so that invalid/non-settled matches can be discarded while still obtaining 10 valid matches for scoring. As of this audit, this pattern is not needed because the current raw_fetch=3 is sufficient for the scoring pipeline.

### 7. Outside_57 coverage

Outside_57 matches go through the exact same `evaluate_h2h_edge()` pipeline with `recent_last_n=3`. No fixtures are skipped, no topN replacement is used, no required scoring is bypassed. Full coverage is preserved.

### 8. Did this audit modify anything?

- Official scan logic: **No**
- Strategy thresholds: **No**
- Candidate ratings: **No**
- Validation data: **No**
- Live bet records: **No**
- Cron: **No**
- QQ recommendations: **No**
- Cloud publish: **No**

## New files added

- `tools/check_v4_recent_form_sample_size.py` — Checker that verifies recent form sample size compliance
- `data/runtime/status/v4_recent_form_sample_size_freeze_20260527.json`
- `data/runtime/status/v4_recent_form_fetch_vs_score_audit_20260527.json`
- `data/runtime/status/v4_recent_form_sample_size_classification_20260527.json`
- `data/runtime/status/v4_outside57_speed_allowed_methods_20260527.json`
- `data/runtime/status/v4_recent_form_sample_size_verify_20260527.json`
- `data/runtime/status/v4_recent_form_sample_size_audit_and_fix_20260527.json`

## Final Status

**V4_RECENT_FORM_SAMPLE_SIZE_AUDIT_FIX_PASS**
