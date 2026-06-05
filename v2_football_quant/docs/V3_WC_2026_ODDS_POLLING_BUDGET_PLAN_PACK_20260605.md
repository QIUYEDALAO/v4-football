# V3 WC 2026 Odds Polling Budget Plan Pack

## Scope

This pack defines a conservative polling budget for the V3 World Cup odds observation layer.
It does not call live API, enable cron/launchd, create runtime output, or produce market conclusions.

## API Budget Guard

- Provider: api-football
- Daily quota reference: 7500 requests/day
- System max daily requests: 1500 requests/day
- Default target usage: 600 requests/day
- Hard stop: 6000 requests/day

The budget intentionally does not use the full daily quota. Any planned run must stop before the
hard stop and should stay inside the default target unless BOSS explicitly approves a higher usage.

## Fixture Scope

- Canonical tournament scope: 104 cards
- Group-stage view: 72 matches
- Knockout reserve: 32 structural slots

The 32 knockout slots are budget reserves only until real teams are available. They must not create
team, lineup, odds, or match conclusions.

## Polling Cadence

The match-relative polling windows are:

- T-24h
- T-6h
- T-2h
- T-90m
- T-60m
- T-30m

If all 104 cards were polled in all six windows, the theoretical request count would be 624. Since
the default target is 600/day, the default policy is to batch or thin lower-priority early windows
instead of silently exceeding the target.

Non-matchdays stay low frequency with a 72-request/day group-stage check template.

## Allowed Observation Fields

Only these odds observation fields are allowed:

- `first_seen_odds`
- `last_pre_kickoff_odds`
- `odds_observation_delta`

`first_seen_odds` is only the earliest locally captured snapshot. It is not true opening odds.
`last_pre_kickoff_odds` is only the latest locally captured pre-kickoff snapshot. It is not true
closing odds. `odds_observation_delta` is a difference between locally captured snapshots only.

## Forbidden Conclusions

The layer must not generate:

- true opening or true closing claims
- steam, drift, sharp-move, or fund-flow claims
- betting recommendations
- V4 grade effects

The dashboard and War Room only display budget and data-gap status.
