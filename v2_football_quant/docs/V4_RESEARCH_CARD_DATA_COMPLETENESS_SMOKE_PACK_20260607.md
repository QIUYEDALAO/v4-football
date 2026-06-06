# V4 Research Card Data Completeness Smoke Pack

Date: 2026-06-07

## Objective

This pack validates whether the new V4 five-dimension Lite schema and market
strategy research-card layer can read fuller api-football fields on a small
whitelisted sample. It is a data-completeness smoke only.

It does not run the V4 daily scan, does not change official grades, does not
write pending candidates, does not send QQ, and does not change cron or launchd.

## Source Scope

The smoke runner samples 3 to 5 fixtures from current mainstream whitelist
leagues when available:

- J1 League
- CSL
- Serie A Brazil
- Belgian Pro League
- UCL

The runner reads the api-football key through the local safe secret file:

- `~/.openclaw/secrets/v4_daily_scan.env`

The key is not printed and is not written to committed files.

## Queried Fields

For each sample fixture, the runner checks:

- fixtures
- odds
- standings
- team statistics
- lineups
- injuries
- H2H

Market coverage is summarized as:

- 1X2
- FT Over/Under
- AH or Handicap
- Double Chance
- bookmaker count
- line present
- odds present

Raw API JSON is written only under gitignored runtime:

- `data/runtime/v4_research_card_smoke/`

Runtime output must not be staged or committed.

## Research-Only Output

The runner converts each sample into:

- five-dimension Lite observation fields
- market strategy research-card fields
- OBSERVE / WAIT / PASS distribution
- missing context summary

The output remains research-only. It must not be treated as an official V4
candidate view, validation ledger, pending write, or live alert source.

## Safety Locks

The checker enforces:

- no betting or recommendation wording in runtime smoke payloads
- no secret literals
- no raw runtime files tracked by git
- no official grade changes
- no pending writes
- no QQ sends
- no cron or launchd changes
- B realtime remains paused
- RF shadow promotion remains blocked

Missing price, line, or market fields cannot produce a market edge conclusion.
HT Over remains auxiliary only and cannot create official A/B behavior.

## Commands

```bash
python3 tools/run_v4_research_card_data_completeness_smoke.py
python3 tools/check_v4_research_card_data_completeness_smoke.py
python3 tools/check_v4_market_strategy_research_cards.py
python3 tools/check_v4_five_dimension_lite.py
python3 tools/check_v4_main_league_admission_guard.py
python3 tools/check_v4_price_field_persistence_pipeline.py
python3 tools/check_v4_production_default_rules_guard.py
python3 tools/check_working_tree_dirty_hygiene.py
```
