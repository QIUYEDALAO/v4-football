# V4 API Key Local Injection & Preflight Verify — Final Report

**Phase:** V4-API-KEY-LOCAL-INJECTION-AND-PREFLIGHT-VERIFY-20260523
**Generated:** 2026-05-23 23:45 CST

---

## 1. Step Summary

| Step | Status |
|:-----|:------:|
| Step 1: Active Provider | ✅ **PASS** |
| Step 2: Key Source | ✅ **PASS** |
| Step 3: Runtime Injection | ✅ **PASS** |
| Step 4: Readonly Preflight | ✅ **PASS** |
| Step 5: Scanner Gate | ✅ **PASS** |
| Step 6: Report | ✅ **PASS** |

## 2. Key Findings

| Field | Value |
|:------|:------|
| Active Provider | `api_sports_direct` |
| Endpoint | `v3.football.api-sports.io` |
| Header | `x-apisports-key` |
| Key Source | `OPENCLAW_APIFOOTBALL_KEY` (env) |
| Key Fingerprint | `e5e3...7a01` |
| HTTP Status | **200** |
| API Status | **API_OK** |
| Subscription | **Ultra**, active until **2026-06-04** |
| Quota Used | 34,746 / 75,000 daily |
| **safe_to_scan** | **✅ true** |
| Provider/Host/Header Match | ✅ All matched |

## 3. Root Cause of Previous 403

The key was valid all along. The issue was the **endpoint**:
- **Before:** `api-football-v1.p.rapidapi.com` (RapidAPI proxy) → 403 Not Subscribed
- **After:** `v3.football.api-sports.io` (Direct) → **200 OK**

The same `x-apisports-key` works directly with api-sports.io. The RapidAPI subscription had expired, but the direct API subscription was still active.

## 4. Scanner Gate Status

| Checker | Result |
|:--------|:------:|
| check_v4_api_preflight | ✅ PASS (200, safe_to_scan=true) |
| check_v4_api_403_circuit_breaker | ✅ PASS |
| check_v4_single_daily_1200_scan_policy | ✅ PASS (23/23) |
| check_v4_api_request_chain | ✅ PASS |

## 5. Prohibition Confirmation

| Prohibition | Status |
|:------------|:------:|
| Full scan ran | False |
| Secret printed (full) | False |
| Secret committed | False |
| git add/commit/push | False |
| QQ_push | False |
| cloud_publish | False |
| cron_created | False |
| strategy_changed | False |

## 6. Final Conclusion

```
V4_API_KEY_LOCAL_PREFLIGHT_VERIFY_PASS
```
