# V4 Postmatch Review API Direct Header Fix 20260523

## Conclusion

V4_POSTMATCH_REVIEW_API_DIRECT_HEADER_FIX_WARN_ONLY

## Root Cause

`engine/v4_review_result_refresh.py` previously mixed API-SPORTS Direct endpoint semantics with RapidAPI headers. The active postmatch path must not use `x-rapidapi-key` or `x-rapidapi-host` against `v3.football.api-sports.io`.

## Fix

- `engine/v4_review_result_refresh.py` now routes API calls through `engine.net_utils.api_preflight` and `engine.net_utils.api_get`.
- Active provider is `api_sports_direct`.
- Active endpoint is `v3.football.api-sports.io`.
- Active header is `x-apisports-key`.
- RapidAPI active header usage is false.
- Preflight is required before postmatch refresh.
- `safe_to_scan=false` blocks remote postmatch API requests.
- Subscription 403 is fail-fast and does not use curl fallback.
- Request budget and negative cache are provided by `engine.net_utils`.
- Dry-run route audit does not mutate structured review or attribution.

## Route Audit

- postmatch_provider: `api_sports_direct`
- endpoint: `v3.football.api-sports.io`
- header: `x-apisports-key`
- postmatch_rapidapi_found: `False`
- postmatch_uses_preflight: `True`
- forbidden_fail_fast: `True`
- curl_fallback_on_403: `False`
- max_forbidden_errors: `1`
- validation_uses_match_date: `True`
- scan_date_used_for_validation: `False`
- brief_used_for_hit_rate: `False`

## Preflight Result

- http_status: `None`
- api_status: `API_KEY_MISSING`
- safe_to_scan: `False`
- key_fingerprint: `MISSING`
- secret_printed: `False`

Local shell did not contain the API key, so no remote provider request was made in this run. This is WARN_ONLY because scanner and postmatch refresh both block remote requests when preflight is unsafe.

## Dry-run

- status: `ROUTE_AUDIT_ONLY`
- structured_file_exists: `False`
- postmatch_api_request_started: `False`
- attribution_mutated: `False`
- structured_review_mutated: `False`

## Safety Confirmation

- full_scan_ran=false
- capture_ran=false
- QQ_push=false
- cloud_publish=false
- cron_enabled=false
- git_commit=false
- git_push=false
- secrets_printed=false
- secrets_committed=false
- V2 restored=false
- V33 active=false
- C active=false
- last_7d_visible=false
- brief_used_for_hit_rate=false
- scan_date_used_for_validation=false

## Verification

- postmatch route checker: `PASS`
- API preflight: `WARN_ONLY`
- API request chain: `PASS`
- 403 circuit breaker: `PASS`
- scout date integrity: `WARN_ONLY`
- match-date validation history recovery: `None`

## Answers

1. RapidAPI header existed in the old postmatch refresh path: yes, per BOSS precondition; current active file is fixed.
2. Changed to x-apisports-key: yes.
3. Still active x-rapidapi-key: no.
4. Still active x-rapidapi-host: no.
5. Postmatch endpoint is v3.football.api-sports.io: yes.
6. Postmatch provider is api_sports_direct: yes.
7. Postmatch requires preflight: yes.
8. 403 fail-fast: yes.
9. curl fallback on subscription 403: false.
10. Postmatch validation uses match_date: yes.
11. scan_date used for validation: false.
12. brief used for hit rate: false.
13. full scan ran: false.
14. attribution raw results mutated: false.
15. QQ pushed: false.
16. cloud published: false.
17. OpenClaw speed/postmatch validation audit can resume: yes, with local API key injected for live preflight.
18. Final integration acceptance can proceed after BOSS approval and environment key verification.
