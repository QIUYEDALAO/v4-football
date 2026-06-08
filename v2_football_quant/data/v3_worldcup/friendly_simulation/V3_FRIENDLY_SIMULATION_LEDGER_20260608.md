# V3 Friendly Simulation Ledger - 2026-06-08

Mode: `SIMULATION_ONLY`

## Summary

- sample_count: `1`
- hit_rate: `N/A`
- settled simulation direction: `1`
- no-direction references: `4`
- safety: observation-only, no pending write, no QQ send, no V4 impact

## Settled Simulation Entry

| Match | fixture_id | Direction | Confidence | Score | Settlement |
|---|---:|---|---|---|---|
| Denmark vs Ukraine | 1543830 | Denmark -0.75 | MEDIUM-LOW | 2-1 | HALF_WIN |

## Reference Matches

| Match | Score | Settlement |
|---|---|---|
| Croatia vs Slovenia | 2-1 | NO_DIRECTION_NOT_SETTLED |
| Morocco vs Norway | 1-1 | NO_DIRECTION_NOT_SETTLED |
| Greece vs Italy | 0-1 | NO_DIRECTION_NOT_SETTLED |
| Colombia vs Jordan | 2-0 | NO_DIRECTION_NOT_SETTLED |

## Guardrails

This ledger is a simulation accounting record only.

- It does not create pending candidates.
- It does not send QQ.
- It does not affect V4.
- `sample_count=1`, so hit rate stays `N/A`.
