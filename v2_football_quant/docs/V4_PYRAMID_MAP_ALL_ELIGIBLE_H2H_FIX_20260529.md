# V4 Pyramid Map all_eligible H2H Fix

**Date**: 2026-05-29
**Status**: V4_PYRAMID_MAP_ALL_ELIGIBLE_H2H_FIX_PASS
**Commit**: (see below)

## Root Cause

`config/v4_league_pyramid_map.json` only covered 57 whitelist league IDs. Under `all_eligible` mode, fixtures from leagues outside the whitelist were scanned, but their league IDs were absent from the pyramid map. This caused:

1. H2H engine classifies unknown leagues as `pyramid_unknown` → `forensic_h2h`
2. `eligible_regular_league_h2h_count` = 0
3. `h2h_low_sample` = True
4. H2H weight → 0
5. OUTSIDE_57 teams → SKIP even with real H2H data

## Fix

Added 4 identified senior domestic leagues to the pyramid map:

| League ID | Name | Country | Tier | Pyramid Group |
|-----------|------|---------|------|---------------|
| 76 | Serie D | Italy | 4 | ITA_PRO |
| 170 | League One | China | 2 | CHN_PRO |
| 222 | Regionalliga | Austria | 3 | AUT_PRO |
| 363 | Premier League | Ethiopia | 1 | ETH_PRO |

Each entry verified as senior domestic league (not youth/reserve/cup/friendly).

## Scan Verification

Manual all_eligible scan after map expansion:
- 240 fixtures scanned, 0 timeout, 0 failed
- Result: **A=1, B=1, SKIP=238**
- all_eligible active ✓
- 57 whitelist entries preserved ✓
- No regression in grade counts ✓

## Protection

| Check | Status |
|-------|--------|
| all_eligible NOT reverted to whitelist | ✓ |
| 57 whitelist entries preserved | ✓ |
| Youth/reserve/cup/friendly NOT added | ✓ |
| DEFAULT_RULES unchanged | ✓ |
| A/B thresholds unchanged | ✓ |
| Validation not recomputed | ✓ |
| Live bet unchanged | ✓ |
| Cron unchanged | ✓ |
| QQ not pushed | ✓ |
| No secrets | ✓ |
