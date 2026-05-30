# V4_COLLECTION_PIPELINE_REDESIGN_SHADOW_FAIL_20260530

## Failed Commit
- commit: `6d06be0b6e256ed2d72ec47d2419d246536e4bf4`
- topic: Phase 3A collection pipeline redesign (RF-first / Market-before-H2H / Lazy H2H / Lazy Events / Lazy CPL placeholder)

## Failure Evidence (formal entry, serial + whitelist + no-push)
- 2026-05-30: raw fixtures=30, scanned=0, scout rows=0
- 2026-05-29: raw fixtures=73, scanned=0, scout rows=0
- 2026-05-27: raw fixtures=48, scanned=0, scout rows=0
- candidate_view output showed A/B/C/SKIP all 0 on these runs.

## Production Risk
This creates a direct production risk for the 12:00 official scan window: formal scan may output empty scout/candidate artifacts, which is not acceptable on `main`.

## Handling Strategy
- Immediate strategy: revert `6d06be0` to protect production behavior first.
- Keep failure record and patch backup for later redesign.

## Redesign Constraints (next attempt)
1. Never directly cut off official scan row generation.
2. Lazy gating must start as observe-only, not blocking official row emission.
3. Official legacy scan chain must remain fully intact.
4. Collection fields can be shadow-recorded, but must not prevent scout row generation.
5. `h2h_required=false` must not result in empty scout outputs.

## Backup Artifacts
- `/tmp/v4_phase3a_fail_backup/6d06be0.stat.txt`
- `/tmp/v4_phase3a_fail_backup/6d06be0.patch`
