# V2 D12 Final Command Review
Phase: D.12.2 | FINAL_REVIEW_ONLY_DRAFT | command_must_not_execute=true

| proof_id | command_must_not_execute | review_only | no_push | no_cron | no_state_write | no_verified_write | no_api | no_key_read | no_supervisor | watchdog_only_failure | no_ai_kill_retry | preserve_logs | manifest_required | boss_d13_required |
|---|-------------------------|------------|---------|---------|---------------|-------------------|--------|------------|-------------|----------------------|-----------------|-------------|------------------|------------------|
| real_state_present_case | true | true | true | true | true | true | true | true | true | true | true | true | true | true |
| active_window_mutation_path | true | true | true | true | true | true | true | true | true | true | true | true | true | true |
| formal_state_write_path | true | true | true | true | true | true | true | true | true | true | true | true | true | true |
| production_verified_path | true | true | true | true | true | true | true | true | true | true | true | true | true | true |
| production_qq_path | true | true | true | true | true | true | true | true | true | true | true | true | true | true |
| production_cron_path | true | true | true | true | true | true | true | true | true | true | true | true | true | true |

NOT_EXECUTABLE_WITHOUT_BOSS_D13_AUTHORIZATION. D13 allowed_to_execute=false.
