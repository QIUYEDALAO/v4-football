# V4 Official A/B Real Edge Audit

## Scope

This audit uses the corrected official cumulative A/B record supplied by BOSS.
It is read-only and does not call live API, execute scan, change official grade,
change A/B thresholds, write pending records, push QQ, change cron/launchd, or
release RF shadow promotion.

This audit is not a recommendation-volume increase pack.

## Official Record

Corrected official cumulative result record:

| Bucket | Hit | Settled | Pending | Hit rate |
|---|---:|---:|---:|---:|
| A | 30 | 49 | 0 | 61.22% |
| B | 54 | 95 | 1 | 56.84% |
| A+B | 84 | 144 | 1 | 58.33% |

This replaces the misleading 90%+ validation join/readout that can appear when
old validation or stale ledger fields are used incorrectly.

## Break-Even Odds

Decimal break-even odds are `settled / hit`:

| Bucket | Break-even decimal odds |
|---|---:|
| A | 1.6333 |
| B | 1.7593 |
| A+B | 1.7143 |

Interpretation:

- A only has value if the long-run achievable price is above roughly 1.63.
- B only has value if the long-run achievable price is above roughly 1.76.
- A+B only has value if the long-run achievable price is above roughly 1.71.

## ROI Proxy

Authoritative price-aware ROI is not available yet because the corrected
official record is aggregate-level and the repository does not contain a clean
event-level price ledger for the corrected 30/49, 54/95, 84/144 record.

Sensitivity proxy:

| Bucket | At 1.29 odds | At 1.60 odds | At 1.70 odds | At 1.80 odds | At 2.00 odds |
|---|---:|---:|---:|---:|---:|
| A | -21.02% | -2.04% | +4.08% | +10.20% | +22.45% |
| B | -26.67% | -9.05% | -3.37% | +2.32% | +13.68% |
| A+B | -24.75% | -6.67% | -0.83% | +5.00% | +16.67% |

This means B is fragile: a small drop below 1.76 turns it negative. A+B is also
thin unless last-pre-kickoff prices reliably clear 1.71.

## Drawdown Proxy

Corrected event-level sequence is not available, so true maximum consecutive
failure and bankroll drawdown cannot be stated as final.

Available aggregate miss burden:

| Bucket | Misses | Miss rate |
|---|---:|---:|
| A | 19 | 38.78% |
| B | 41 | 43.16% |
| A+B | 60 | 41.67% |

Local stale ledger sequence gives only a non-authoritative proxy and must not
be used as proof of safety. The required next step is a corrected price-aware
replay ledger with event sequence, price, stake, result, cumulative P/L, and
max drawdown.

## Risk Decision

### A

Continue observation. A is the only bucket with a moderately acceptable hit
rate cushion, but it still needs price confirmation above 1.63 and an
event-level drawdown ledger before any real-time escalation.

### B

Pause real-time reminders. B has 56.84% hit rate and needs around 1.76 decimal
odds to break even. Without stable price evidence, B should not wake the user
or trigger low-context alerts.

### A+B

Daily report only. A+B is 84/144 at 58.33%; it is not strong enough to justify
real-time behavior without price-aware replay.

### RF Shadow Promotion

Keep blocked / observation-only. The RF shadow strict checker correctly flags
SKIP to B expansion risk. Do not weaken that checker to pass.

## Required Next Step

Build `V4_PRICE_AWARE_REPLAY_LEDGER_PACK` before discussing production
promotion:

- fixture id
- official grade
- market state
- odds/price source
- first seen price
- last-pre-kickoff price
- stake assumption
- result
- cumulative P/L
- max consecutive failure
- max drawdown
- rejected no-price and market-conflict cases

Until that exists, V4 official A/B has observation value but not enough proof
for aggressive real-time operation.

## Decision Summary

- A: continue observation, no automatic escalation without price guard.
- B: pause real-time reminders.
- A+B: daily report only.
- Shadow/C/SKIP: observation-only.
- Next: price-aware replay ledger, not rule changes.
