# V3 WC Venue Stress Layer Code Ready

## Scope

This layer reads the OpenClaw venue stress source pack and adds V3 World Cup
venue-pressure observation fields. It does not change V3/V4 grading, does not
write pending bets, and does not output betting advice.

## Output

- `data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json`
- `data/runtime/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json`

## Safety

- `observation_only=true`
- `betting_recommendation=false`
- video claims are allowed as visible observation context only
- `video_claim_used_for_score=false`
- venue stress is not a win/loss signal
