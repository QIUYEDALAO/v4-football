# V4 Renderer Guard

## 1) Renderer Input Requirements

- Renderer must consume structured V4 schema input, not free-form text.
- Renderer must not recalculate or re-rank grades.
- Renderer must enforce grade whitelist before output rendering.
- Renderer must fail-closed on schema mismatch.

## 2) Renderer Output Requirements

- Formal output grade must be exactly one of `A/B/C/SKIP`.
- `SKIP` output must remain skip/no-recommendation.
- `C` output must not be phrased as main recommendation.
- Output must not include active legacy references `V33/V38`.
- Output must not include non-standard formal grades:
  - `WATCH`, `CANDIDATE`, `S`, `S+`, `D`, `BET`, `STRONG`, `主推`

## 3) Template Guard Requirements

- Full report / QQ template / brief template must use unified schema fields.
- Templates must include schema guard marker field (`schema_guard_status`) or equivalent schema-driven contract indication.
- Templates must not hardcode legacy grade system in formal output path.
- Template render path must not bypass guard checks.

## 4) Failure Behavior

- Schema mismatch -> `BLOCKER`
- Non-standard grade in formal output -> `BLOCKER`
- `SKIP` recommendation wording -> `BLOCKER`
- `C` main recommendation wording -> `BLOCKER`
- Any active `V33/V38` in formal output -> `BLOCKER`
- QQ route remains closed in V4-B (`qq_push_allowed=false`)

## 5) Non-Execution Boundary

- V4-B guard hardening does not execute V4 production tasks.
- V4-B does not enable QQ push, cron, or production verification.
- Phase E remains disallowed.
