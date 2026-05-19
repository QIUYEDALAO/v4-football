# V2 D10 Six-Proof Evidence Matrix

Phase: D.10.1 | Date: 2026-05-19 | Status: FINAL (all targets UNPROVEN)

## Full Matrix

| # | proof_id | proof_name | current_status | required_evidence | allowed_action_now | execution_allowed | production_allowed | production_risk | blocker_if_missing | command_draft_required | proof_result_required_before_PIPELINE_READY |
|---|----------|------------|----------------|-------------------|-------------------|-------------------|-------------------|-----------------|-------------------|----------------------|---------------------------------------------|
| 1 | real_state_present_case | Real State Present Case | UNPROVEN | sandbox observe with real fixtures | REVIEW_ONLY_DRAFT | false | false | HIGH | true | true | true |
| 2 | active_window_mutation_path | Active Window Mutation Path | UNPROVEN | controlled single-window worker observe | REVIEW_ONLY_DRAFT | false | false | HIGH | true | true | true |
| 3 | production_cron_path | Production Cron Path | UNPROVEN | cron scheduling dry-run with no-push | REVIEW_ONLY_DRAFT | false | false | HIGH | true | true | true |
| 4 | production_qq_path | Production QQ Path | UNPROVEN | QQ route dry-run with OPENCLAW_NO_PUSH=1 | REVIEW_ONLY_DRAFT | false | false | CRITICAL | true | true | true |
| 5 | production_verified_path | Production Verified Path | UNPROVEN | verification path test with false state | REVIEW_ONLY_DRAFT | false | false | CRITICAL | true | true | true |
| 6 | formal_state_write_path | Formal State Write Path | UNPROVEN | sandbox state observe with no production write | REVIEW_ONLY_DRAFT | false | false | HIGH | true | true | true |

## Constraints

- PIPELINE_READY = false
- PRODUCTION_VERIFIED = false
- Phase E = false
- All targets require individual BOSS authorization before execution
