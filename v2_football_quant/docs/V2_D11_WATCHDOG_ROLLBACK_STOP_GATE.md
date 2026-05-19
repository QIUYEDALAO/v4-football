# V2 D11 Watchdog / Rollback / Stop Gate
Phase: D.11 | gate only, no execution

## Stop Conditions (any → stop)
- permission true / marker mismatch / dirty runtime-state
- QQ send attempt / cron modification
- API/key read attempt / lock conflict / timeout
- checker BLOCKER / proof target not UNPROVEN before execution

## Rollback / Recovery
- no AI kill/retry / report watchdog only / preserve logs
- no delete runtime evidence / no mutate state
- no write verified / no push QQ / no enable cron

## Constraints
- this gate does not execute proof
- D12 allowed_to_execute=false
- production_verified=false / phase_e_allowed=false
