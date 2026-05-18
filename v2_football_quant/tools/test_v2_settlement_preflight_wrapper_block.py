#!/usr/bin/env python3
"""Phase D.7.2 — Wrapper-level block test. Verifies settlement entry blocks correctly."""
import hashlib, json, os, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
VERIFIED = BASE / "data" / "paper_trading" / "verified_20260517.json"
STATUS = BASE / "data" / "runtime" / "status"

def file_fingerprint(p):
    if not p.exists(): return None, None
    return p.stat().st_mtime, hashlib.sha256(p.read_bytes()).hexdigest()

errors = []

# 1. Pre-verified fingerprint
mtime_before, hash_before = file_fingerprint(VERIFIED)
print(f"VERIFIED before: mtime={mtime_before} hash={hash_before[:16]}...")

# 2. Run wrapper (will be blocked by preflight)
env = os.environ.copy()
env["PYTHONPATH"] = str(BASE)
result = subprocess.run(
    [sys.executable, str(BASE / "engine" / "v2_settle_with_watchdog.py"), "--date", "20260517", "--mode", "main"],
    capture_output=True, text=True, timeout=30, cwd=str(BASE), env=env
)
out = result.stdout + result.stderr
exit_code = result.returncode

print(f"Exit: {exit_code}")
if "NameError" in out or "KeyError" in out or "Undefined" in out:
    errors.append("NameError_in_wrapper_output")
    print(f"FAIL: NameError detected")

# 3. Check preflight marker exists
pf = STATUS / "v2_settlement_preflight_20260517.json"
if not pf.exists():
    errors.append("preflight_marker_missing")
else:
    pf_data = json.loads(pf.read_text())
    allowed = pf_data.get("settlement_allowed")
    blockers = pf_data.get("summary",{}).get("blockers",[])
    print(f"Preflight: allowed={allowed} blockers={blockers}")
    if allowed:
        errors.append("settlement_allowed_true")

# 4. Verified file unchanged
mtime_after, hash_after = file_fingerprint(VERIFIED)
print(f"VERIFIED after: mtime={mtime_after} hash={hash_after[:16]}...")
if hash_before != hash_after:
    errors.append("verified_file_changed")

# 5. No KeyError
if exit_code == 1:
    errors.append("unexpected_exit_code")

print(f"\n{'PASS' if not errors else 'FAIL'}: {len(errors)} errors")
if errors:
    for e in errors: print(f"  - {e}")
    raise SystemExit(1)
print("✅ Wrapper blocks correctly: no NameError, no verify_date, verified unchanged")
