# V4 Active Contamination Inventory (Phase V4-A.1)

## Scope

- Scan scope: `engine/v4_*`, `templates/v4_*`, `docs/V4_*`, `config/v4_*`, plus V4 guard/checker paths.
- Goal: clean active contamination in formal output chain while preserving denylist/deprecated safety references.

## Classification Rules

- `active_v33_reference` / `active_v38_reference`: forbidden in formal output path.
- `active_non_standard_grade`: forbidden in formal output path.
- `renderer_output_pollution` / `qq_brief_pollution` / `report_template_pollution`: must be removed or reworded.
- `guard_denylist_allowed`: allowed only as blocked-term guard.
- `deprecated_doc_allowed`: allowed only as historical/forbidden documentation context.
- `false_positive`: token exists but not grade/output meaning.

## Inventory

| path | line_or_context | token | contamination_type | active_output_risk | allowed_context | action | reason |
|---|---|---|---|---|---|---|---|
| `engine/v4_openclaw_brief.py` | final warning line | `V33` | `active_v33_reference` | HIGH | `formal_output` | `REWORD` | Formal brief text contained legacy token and could leak into official QQ brief output. |
| `engine/v4_scan_and_brief.py` | `FORBIDDEN_KEYWORDS` list | `V33`, `按V33策略` | `guard_denylist_allowed` | LOW | `guard_denylist` | `KEEP_AS_DENYLIST` | Used as block list tokens, not output recommendation vocabulary. |
| `engine/v4_review_guard.py` | `FORBIDDEN` list / qq rule comment | `V33`, `BET_LOCKED` | `guard_denylist_allowed` | LOW | `guard_denylist` | `KEEP_AS_DENYLIST` | Guard explicitly blocks legacy/v2 leakage before push route. |
| `docs/V4_BOUNDARY_AND_CONTRACT.md` | prohibition section | `WATCH`, `CANDIDATE`, `V33`, `主推` | `deprecated_doc_allowed` | LOW | `deprecated_doc` | `MARK_DEPRECATED` | Terms are listed as forbidden examples, not formal output content. |
| `docs/V4_REFACTOR_ROADMAP.md` | prohibition line in V4-G | `V33` | `deprecated_doc_allowed` | LOW | `deprecated_doc` | `MARK_DEPRECATED` | Legacy term appears only in prohibition statement. |
| `config/v4_candidate_rules.yaml` | `allowed_pullback_fit` enum | `STRONG` | `false_positive` | LOW | `false_positive` | `KEEP_AS_FALSE_POSITIVE` | Internal fit enum; not a final grade or recommendation class. |
| `engine/v4_match_intelligence.py` | pullback fit / internal reasoning | `STRONG` | `false_positive` | LOW | `false_positive` | `KEEP_AS_FALSE_POSITIVE` | Internal gate feature value, not output grade schema. |
| `engine/v4_dashboard.py` | legacy dashboard tier mapping | `S` | `false_positive` | LOW | `false_positive` | `KEEP_AS_FALSE_POSITIVE` | Legacy dashboard visualization context; outside formal V4-A.1 output contract chain. |

## Resolution Summary

- Active contamination requiring mutation: **1 item** (`engine/v4_openclaw_brief.py` V33 output wording).
- Active `V38` in formal output path: **none found**.
- Renderer/QQ/report-template non-standard grade pollution in formal path: **none found** after recheck.
- Denylist/deprecated/false-positive contexts retained with explicit classification only.
