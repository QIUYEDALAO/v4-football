#!/usr/bin/env python3
"""V4 API credential preflight: one status request for the active provider only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.net_utils import api_preflight  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = api_preflight(args.date, strict=args.strict, write_status=True)
    blockers = list(result.get("blockers") or [])
    api_status = result.get("api_status")
    if result.get("safe_to_scan") is True:
        check_status = "PASS"
    elif api_status == "API_FORBIDDEN_NOT_SUBSCRIBED":
        check_status = "WARN_ONLY"
    elif api_status == "API_KEY_MISSING":
        check_status = "WARN_ONLY"
    else:
        check_status = "BLOCKER" if api_status in {"API_PROVIDER_MISMATCH", "API_HOST_MISMATCH", "API_HEADER_MISMATCH"} else "WARN_ONLY"
    result["check_status"] = check_status
    result["scanner_must_block_when_safe_to_scan_false"] = True
    out = ROOT / "data/runtime/status" / f"v4_api_preflight_{args.date}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "guard_state"}, ensure_ascii=False, indent=2))
    if check_status == "BLOCKER":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
