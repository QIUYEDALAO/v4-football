# V3 World Cup Roster Intelligence Baseline

**Generated:** 2026-05-25  
**Status:** WARN_ONLY  
**Blocker:** NONE  
**Agent:** ClawOps  

---

## 1. Big list fully loaded?

YES — 46/46 teams with structured roster data. Total players: 1375.
Source: apifootball v3 players/squads endpoint.
WARN_ONLY: caps/goals/season_minutes not available from basic endpoint; needs supplement.

## 2. Most stable squads

| Team | Stability | Avg Age | Players |
|------|-----------|---------|---------|
| **USA** | 81 | 23.9 | 31 |
| **Cameroon** | 79 | 23.1 | 24 |
| **Spain** | 78 | 25.4 | 29 |

## 3. Most spine change

| Team | Spine Change | Core Stability |
|------|-------------|----------------|
| **Brazil** | 60 | 58 |
| **Iran** | 60 | 55 |
| **Jamaica** | 60 | 68 |

## 4. Highest age/injury risk

| Team | Age Risk | Players > 32 |
|------|----------|--------------|
| **Iran** | 24 | 6 |
| **Argentina** | 21 | 6 |
| **Brazil** | 21 | 5 |

## 5. Best squad depth

| Team | Depth | Players |
|------|-------|---------|
| **Chile** | 100 | 37 |
| **Costa Rica** | 100 | 37 |
| **Ecuador** | 100 | 35 |

## 6. Possibly overrated by market

None identified

## 7. Possibly underrated by market

**Cameroon**: High stability + depth — public may underrate squad readiness (confidence: MEDIUM)
**Canada**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Chile**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Ecuador**: Stable squad — consistent performance likely (confidence: MEDIUM)
**France**: Stable squad — consistent performance likely (confidence: LOW)
**Ghana**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Iraq**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Italy**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Ivory Coast**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Mexico**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Morocco**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Nigeria**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Portugal**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Serbia**: Stable squad — consistent performance likely (confidence: MEDIUM)
**Spain**: High stability + depth — public may underrate squad readiness (confidence: MEDIUM)
**Tunisia**: High stability + depth — public may underrate squad readiness (confidence: MEDIUM)
**Turkey**: Stable squad — consistent performance likely (confidence: MEDIUM)
**USA**: High stability + depth — public may underrate squad readiness (confidence: MEDIUM)
**Ukraine**: Stable squad — consistent performance likely (confidence: MEDIUM)

## 8. V3 Watchlist

**Cameroon** [WATCHLIST]: High stability + depth — public may underrate squad readiness
**Spain** [WATCHLIST]: High stability + depth — public may underrate squad readiness
**Tunisia** [WATCHLIST]: High stability + depth — public may underrate squad readiness
**USA** [WATCHLIST]: High stability + depth — public may underrate squad readiness

## 9. Betting recommendations?

**NONE.** Zero betting recommendations in any output file. All outputs are observation-only.
Perception Gap analysis is pre-screening, not trading signal.

## 10. V4 modified?

**NO.** V4 files, scripts, and strategy untouched.

## 11. Next phase data needs

1. Player stats: caps/goals/minutes from players?team=X&season=2026
2. Injury reports: real injury status for all squads
3. Friendlies: pre-tournament lineup data
4. Market data: FIFA/Elo rankings, odds
5. Club form: player club performance
6. Coach profiles: playing style, formations
7. WC history: team tournament data

## Files Generated

| File | Description |
|------|-------------|
| data/v3_worldcup/rosters/worldcup_rosters_20260526.json | 46-team rosters |
| data/v3_worldcup/team_profiles/roster_delta_20260526.json | Delta scores |
| data/v3_worldcup/team_profiles/team_profiles_20260526.json | Team profiles |
| data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json | PG watchlist |
| data/runtime/dashboard/v3_worldcup_roster_intel.html | Dashboard |
| tools/v3_worldcup_roster_schema.py | Schema |
| tools/check_v3_worldcup_roster_baseline.py | Checker |
| docs/V3_WORLDCUP_ROSTER_INTELLIGENCE_BASELINE_20260526.md | This report |

---

**V3_WORLDCUP_ROSTER_INTELLIGENCE_BASELINE_WARN_ONLY**
*WARN reason: caps/goals/season_minutes need supplement*
