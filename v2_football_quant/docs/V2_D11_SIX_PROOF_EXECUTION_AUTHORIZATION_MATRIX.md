# V2 D11 Six-Proof Execution Authorization Matrix
Phase: D.11 | All UNPROVEN | execution_allowed_now=false

| # | proof_id | status | exec_auth | exec_now | command_exists | runner | preconditions | stop_gate | rollback | watchdog | no_ai_kill | evidence_req | mark_proven |
|---|----------|--------|-----------|----------|----------------|--------|---------------|----------|----------|----------|------------|-------------|-------------|
| 1 | real_state_present_case | UNPROVEN | REVIEW_ONLY | false | true | false | sandbox+real_fixtures | true | true | true | true | true | false |
| 2 | active_window_mutation_path | UNPROVEN | REVIEW_ONLY | false | true | false | single_window+observe | true | true | true | true | true | false |
| 3 | production_cron_path | UNPROVEN | REVIEW_ONLY | false | true | false | dry_run+no_push | true | true | true | true | true | false |
| 4 | production_qq_path | UNPROVEN | REVIEW_ONLY | false | true | false | OPENCLAW_NO_PUSH=1 | true | true | true | true | true | false |
| 5 | production_verified_path | UNPROVEN | REVIEW_ONLY | false | true | false | false_state+no_write | true | true | true | true | true | false |
| 6 | formal_state_write_path | UNPROVEN | REVIEW_ONLY | false | true | false | sandbox+no_prod | true | true | true | true | true | false |

PIPELINE_READY=false | PRODUCTION_VERIFIED=false | Phase E=false
