#!/usr/bin/env python3
"""Refresh the canonical V4 Control Center model from formal scan inputs only."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DAILY = ROOT / "data/daily_reports"
BUILDER = ROOT / "tools/build_v4_control_center_model.py"
OFFICIAL_CANDIDATE_BUILDER = ROOT / "tools/build_v4_official_candidate_view.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--phase", choices=["after-scan", "after-validation"], required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], required=True)
    parser.add_argument("--no-api", action="store_true", required=True)
    parser.add_argument("--no-capture", action="store_true", required=True)
    parser.add_argument("--no-push", action="store_true", required=True)
    parser.add_argument("--no-cloud", action="store_true", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    required = {
        "scan_perf": DAILY / f"scan_perf_v4_{args.date}.json",
        "scout": DAILY / f"scout_v4_{args.date}.json",
        "brief": DAILY / f"v4_openclaw_brief_{args.date}.txt",
    }
    blockers = [f"missing_formal_input:{name}" for name, path in required.items() if not path.exists()]
    official_candidate_step = None
    build_step = None
    if args.mode == "apply" and not blockers:
        official_proc = subprocess.run(
            [sys.executable, str(OFFICIAL_CANDIDATE_BUILDER), "--date", args.date],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=120,
        )
        official_candidate_step = {
            "returncode": official_proc.returncode,
            "stdout_tail": official_proc.stdout[-800:],
            "stderr_tail": official_proc.stderr[-800:],
        }
        if official_proc.returncode != 0:
            blockers.append(f"official_candidate_view_build_rc_{official_proc.returncode}")
    if args.mode == "apply" and not blockers:
        proc = subprocess.run(
            [sys.executable, str(BUILDER)],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=120,
        )
        build_step = {
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-800:],
            "stderr_tail": proc.stderr[-800:],
        }
        if proc.returncode != 0:
            blockers.append(f"control_center_model_build_rc_{proc.returncode}")

    marker = {
        "schema_version": "v4_control_center_refresh.v1",
        "generated_at": datetime.now().isoformat(),
        "date": args.date,
        "phase": args.phase,
        "mode": args.mode,
        "canonical_entry": "data/runtime/dashboard/v4_control_center.html",
        "canonical_builder": "tools/build_v4_control_center_model.py",
        "official_candidate_builder": "tools/build_v4_official_candidate_view.py",
        "formal_inputs": {name: str(path.relative_to(ROOT)) for name, path in required.items()},
        "model_refreshed": args.mode == "apply" and not blockers,
        "official_candidate_step": official_candidate_step,
        "build_step": build_step,
        "scan_ran": False,
        "validation_recomputed": False,
        "QQ_push": False,
        "cloud_publish": False,
        "cron_modified": False,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    out = STATUS / f"v4_control_center_refresh_{args.phase.replace('-', '_')}_{args.mode.replace('-', '_')}_{args.date}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(marker, ensure_ascii=False, indent=2))
    return 2 if args.strict and blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
