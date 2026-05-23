# V4 Script Validation Schema 20260523

## Fields

- match_id / fixture_id
- match_date
- grade
- home_team_cn / away_team_cn
- script_predicted
- script_family
- kickoff
- ht_score / ft_score
- goal_events
- actual_goal_timing_profile
- script_result
- script_confidence
- script_reason
- source_files
- api_enabled
- data_quality

## script_result enum

- SCRIPT_HIT
- SCRIPT_PARTIAL
- SCRIPT_MISS
- SCRIPT_UNKNOWN

## Rules

- SCRIPT_UNKNOWN is excluded from the denominator.
- SCRIPT_PARTIAL is tracked separately and is not counted as HIT.
- C and SKIP are excluded.
- A+B script validation equals A+B only, never C.
- Script validation is an audit layer and never changes V4 recommendation grades.
- Brief text is not used for script validation judgement.
