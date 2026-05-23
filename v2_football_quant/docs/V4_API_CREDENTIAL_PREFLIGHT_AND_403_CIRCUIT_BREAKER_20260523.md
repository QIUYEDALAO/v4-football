# V4 API Credential Preflight and 403 Circuit Breaker — 20260523

## Root Cause Assessment

This 403 is not proof that the subscription expired. When BOSS confirms the subscription is valid, the most likely causes are provider/key/host/header/listing mismatch or a local environment pointing to the wrong or missing key. The local shell currently reports `API_KEY_MISSING`, so the preflight did not issue a remote status request and `safe_to_scan=false`.

## Request Chain

- scanner_path: `engine/v4_scan_and_brief.py`
- api_client_path: `engine/net_utils.py`
- urllib_call_path: `engine/net_utils.py:_urllib_raw_get`
- curl_fallback_path: `engine/net_utils.py:_curl_raw_get`
- cache_layer_path: `engine/v4_runner.py:_cached_api_client`
- active_provider: `api_sports_direct`
- endpoint_host: `v3.football.api-sports.io`
- header_names: `['x-apisports-key']`
- key_fingerprint: `MISSING`

## Provider Routing Matrix

- RapidAPI: `api-football-v1.p.rapidapi.com`, headers `x-rapidapi-key`, `x-rapidapi-host`.
- API-SPORTS direct: `v3.football.api-sports.io`, header `x-apisports-key`.
- Active provider is unique: `api_sports_direct`.
- provider_mismatch: `False`.
- host_mismatch: `False`.
- header_mismatch: `False`.

## Preflight Result

- http_status: `None`
- api_status: `API_KEY_MISSING`
- safe_to_scan: `False`
- request_count: `0`
- secret_printed: `false`

## Circuit Breaker

- subscription 403 fail-fast: `True`
- curl fallback on subscription 403: `False`
- max_remote_requests: `1200`
- max_forbidden_errors: `1`
- negative_cache_enabled: `True`
- scanner preflight required: `True`
- scan allowed when preflight fails: `False`

## Dashboard Status

The dashboard now exposes API abnormal state and preserves last_good when preflight is unsafe. It must not show normal 今日已更新 when API preflight is blocked.

## Prohibited Actions Confirmation

- full_scan_ran=false
- capture_ran=false
- QQ_push=false
- cloud_publish=false
- cron_created=false
- git_commit=false
- git_push=false
- V2 restored=false
- V33 active=false
- strategy_changed=false
- v4_candidate_numbers_changed=false
- validation_numbers_changed=false
- attribution_numbers_changed=false
- secrets_printed=false
- secrets_committed=false

## Conclusion

`V4_API_CREDENTIAL_PREFLIGHT_403_CIRCUIT_BREAKER_WARN_ONLY`
