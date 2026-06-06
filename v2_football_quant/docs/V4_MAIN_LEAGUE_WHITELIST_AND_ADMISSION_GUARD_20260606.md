# V4 Main League Whitelist And Admission Guard

Status: CODE_READY  
Date: 2026-06-06

This is not a strategy launch. It does not change official grade logic, A/B/C/SKIP thresholds, QQ routing, pending candidates, cron, launchd, validation, or live bet records.

## League Tiers

`INCLUDE_CURRENT` is the only always-current research-pool include bucket:

- J1 League
- CSL
- Serie A Brazil
- Belgian Pro League
- UCL

`INCLUDE_SEASON_AWARE` is allowed only as a mainstream/season-aware research-pool bucket:

- EPL
- LaLiga
- Bundesliga
- Serie A Italy
- Ligue 1
- Liga Portugal
- Eredivisie
- Super Lig
- Liga MX
- MLS

`OBSERVE_ONLY` is not a strategy pool and does not trigger realtime reminders:

- Argentina Liga Profesional
- K League 1
- UEL
- Friendlies

Friendlies remain OBSERVE_ONLY and must not use the formal league model.

`EXCLUDE_DEFAULT` covers regional leagues, lower divisions, youth teams, reserve teams, low-coverage cups, and unknown leagues. These do not enter the V4 strategy research pool.

## Admission Rules

A fixture must have sufficient information before it can be considered research-pool eligible:

- At least 3 of these 4 market families: 1X2, FT O/U, AH or Handicap, Double Chance.
- `bookmaker_count >= 5`; `8+` is preferred.
- FT O/U or AH/Handicap must include a line.
- Standings or team stats must exist.
- Missing injuries must be tagged `INJURY_SOURCE_MISSING`.
- Missing lineup must be tagged `LINEUP_MISSING` or `LINEUP_WAIT_EVENT`.
- HT Over is auxiliary only and must not manufacture A/B by itself.

The current basis is the OpenClaw api-football coverage review: mainstream first-tier leagues and UCL have the best chance of carrying odds, line, standings/team stats, and lineup/injury context. Weak leagues, regional leagues, youth competitions, friendlies, and low-coverage cups are not suitable for the official strategy pool.

## Policy Locks

- B realtime reminder remains paused.
- C/SKIP/shadow-only do not trigger realtime reminders.
- RF shadow promotion remains BLOCKED.
- `OBSERVE_ONLY` rows remain observation-only.
- This pack does not change official A/B/C/SKIP thresholds.
- This pack does not write `pending_bet_candidates`.
- This pack does not push QQ.
- This pack does not modify cron or launchd.

## Files

- `config/v4_main_league_admission_policy.json`
- `engine/v4_league_admission.py`
- `engine/v4_runner.py`
- `tools/check_v4_main_league_admission_guard.py`
