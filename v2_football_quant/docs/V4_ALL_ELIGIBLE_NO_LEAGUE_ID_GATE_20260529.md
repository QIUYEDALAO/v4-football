# V4 All Eligible — No League ID Gate

**Date**: 2026-05-29
**Status**: V4_ALL_ELIGIBLE_NO_LEAGUE_ID_GATE_PASS
**HEAD**: a999721 → (new commit)

## Summary

Removed the fixed league_id pyramid map gate from V4 all_eligible H2H classification. Previously, any league_id not present in `config/v4_league_pyramid_map.json` was immediately classified as `forensic_h2h` + `pyramid_unknown`, which excluded it from H2H eligibility regardless of whether the league was a legitimate senior competition.

## Decision

From this commit, V4 all_eligible no longer uses league_id membership in the pyramid map as a hard admission gate for H2H eligibility.

### New Rules

1. **Fixture must be from all_eligible scan scope** — unchanged.
2. **Fixture must pass business window** — unchanged.
3. **Competition must be a senior league** — determined dynamically by `_is_non_senior_league()`.
4. **Excluded competition types**: Cup, Friendly, Youth (U-series), Women's, Reserve, International tournaments.
5. **Pyramid map role**: Statistics and attribution metadata only — no longer a candidate admission gate.
6. **Dynamic senior leagues**: Unmapped but verified senior leagues get `pyramid_group="UNMAPPED_SENIOR"`, `tier=99`, `eligibility_source="dynamic"`.
7. **Review required**: Leagues with insufficient metadata are excluded with `review_required_unknown_league` — never silently dropped.
8. **Final grade**: Still determined by official V4 scoring — dynamic eligibility does not force any grade.

## Files Changed

| File | Change |
|------|--------|
| `engine/data_sources/h2h_engine.py` | Added `_is_non_senior_league()` helper; modified `_classify_h2h_sample()` for dynamic eligibility; added synthetic `current_pyr` for unmapped current leagues |
| `tools/check_v4_all_eligible_no_league_id_gate.py` | NEW — verifies dynamic eligibility, split stats, safety gates |
| `tools/audit_v4_dynamic_league_eligibility.py` | NEW — audits all unique leagues with dynamic classification |

## Protection Gates (Verified)

- [x] DEFAULT_RULES unchanged
- [x] A/B thresholds unchanged
- [x] validation not recomputed
- [x] live bet raw records unmodified
- [x] cron unmodified
- [x] QQ not pushed
- [x] pyramid map preserved as stats metadata (61 entries, 52 whitelist intact)
- [x] WHITELIST_57 / OUTSIDE_57 split statistics preserved
- [x] source_group field preserved in model
- [x] all_eligible mode preserved (NOT reverted to whitelist)
- [x] H2H post-2020 last-10 policy preserved
- [x] No secrets committed

## Remaining

- Full scan validation requires cron environment (API key not available in dev workspace)
- `V4_PLAYBOOK_SCRIPT_AND_TIME_DISTRIBUTION_PENDING` — playbook labels and normalized time distribution display
- `V4_OUTSIDE57_SAMPLE_ACCUMULATION_RESTORE_PENDING` — monitor OUTSIDE_57 A/B as dynamic eligibility enables more fixtures
