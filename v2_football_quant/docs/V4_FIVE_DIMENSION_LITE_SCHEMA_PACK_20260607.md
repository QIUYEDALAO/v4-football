# V4 Five Dimension Lite Schema Pack

Date: 2026-06-07

## Scope

This pack adds an observation-only V4 event evaluation skeleton. It does not
launch a new strategy, restore realtime reminders, change official grades,
write pending candidates, send QQ messages, or modify cron/launchd.

## Five Dimensions

1. `strength_gap`: league tier, standings, team stats, and H2H context. H2H is
   auxiliary only and cannot create A/B by itself.
2. `tactical_efficiency`: goals for, goals against, shots, home/away context,
   and full-time O/U context when present.
3. `squad_context`: lineup, formation, and injury source status. Official
   lineup remains `LINEUP_WAIT_EVENT` until it is available.
4. `market_confirmation`: 1X2, FT O/U, AH/Handicap, Double Chance, bookmaker
   count, line, odds, and snapshot time.
5. `external_risk`: rest-days placeholder, travel placeholder, venue, weather
   placeholder, and referee placeholder.

## Missing Context Policy

The first Lite version must explicitly preserve missing context instead of
guessing:

- `PRICE_MISSING`
- `LINE_MISSING`
- `MARKET_MISSING`
- `STANDINGS_MISSING`
- `TEAM_STATS_MISSING`
- `LINEUP_MISSING`
- `LINEUP_WAIT_EVENT`
- `INJURY_SOURCE_MISSING`
- `EXTERNAL_CONTEXT_PENDING`
- `DATA_INSUFFICIENT`

Missing price or line prevents `market_confirmation` from passing. Missing both
standings and team stats prevents `strength_gap` from passing. HT Over is
auxiliary only and cannot independently create A/B or a realtime reminder.

## Output

The builder writes manual-source samples under
`data/manual_sources/v4/five_dimension_lite/`:

- `v4_five_dimension_lite_samples_20260607.json`
- `v4_five_dimension_lite_summary_20260607.json`

Allowed conclusions are only `OBSERVE`, `WAIT`, and `PASS`. These labels mean
research state, not an official recommendation or betting instruction.

## Policy Lock

- Official grade unchanged.
- A/B/C/SKIP thresholds unchanged.
- Pending candidates untouched.
- QQ untouched.
- Cron and launchd untouched.
- B realtime reminder remains paused.
- RF shadow promotion remains blocked.
- No live API is called.
