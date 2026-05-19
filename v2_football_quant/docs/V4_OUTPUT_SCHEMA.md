# V4 Output Schema

## Scope

- System: `V4` (上半场进球情报系统)
- This schema applies to formal V4 outputs (`full report`, `qq brief`, `daily review structured output`).
- Phase V4-B is schema/guard only. It does not grant execution, push, cron, or production rights.

## Root Schema

Required root fields:

- `schema_version`
- `generated_at`
- `run_date`
- `window`
- `system="V4"`
- `production_verified=false`
- `phase_e_allowed=false`
- `qq_push_allowed=false`
- `matches` (list)

Example root contract:

```json
{
  "schema_version": "v4_output_schema.v1",
  "generated_at": "2026-05-19T00:00:00+08:00",
  "run_date": "20260519",
  "window": "midday",
  "system": "V4",
  "production_verified": false,
  "phase_e_allowed": false,
  "qq_push_allowed": false,
  "matches": []
}
```

## Match Item Schema

Each match item must contain:

- `match_id`
- `kickoff_time`
- `league`
- `home_team`
- `away_team`
- `grade`
- `conclusion`
- `reason_codes`
- `intelligence_summary`
- `risk_flags`
- `data_quality`
- `source_trace`
- `guard_status`
- `output_allowed`
- `qq_allowed`
- `report_allowed`

Type requirements:

- `grade`: `"A" | "B" | "C" | "SKIP"`
- `reason_codes`: `list[str]`
- `guard_status`: `"PASS" | "WARN" | "BLOCKER" | "SKIP"`
- `output_allowed`, `qq_allowed`, `report_allowed`: `bool`

## Grade Contract

- Allowed grades exactly: `A`, `B`, `C`, `SKIP`
- No alternative formal grade is allowed.
- Forbidden formal grade/output words: `WATCH`, `CANDIDATE`, `S`, `S+`, `D`, `BET`, `STRONG`, `主推`
- No active legacy reference is allowed in formal output: `V33`, `V38`

## Conclusion Contract

- `A/B`: may carry formal recommendation conclusion.
- `C`: only low-intensity/observation conclusion; **must not** be main recommendation wording.
- `SKIP`: must represent skip/no-recommendation; **must not** be recommendation wording.

Required policy phrases:

- `SKIP is not recommendation`
- `C is not main recommendation`

## reason_codes Contract

- `reason_codes` must be machine-readable list of strings.
- `reason_codes` must not carry legacy or non-standard formal grade terms.
- `reason_codes` must not include V33/V38 active semantics.

## Guard Contract

- `guard_status=PASS` is required before any QQ route eligibility.
- `guard_status=BLOCKER` must block report/qq output.
- `output_allowed=true` only when schema + renderer/template guard both pass.

## Phase Gate (V4-B)

- `production_verified=false`
- `phase_e_allowed=false`
- `qq_push_allowed=false`
- `v4_c_allowed_to_generate=true`
- `v4_c_allowed_to_execute=false`
