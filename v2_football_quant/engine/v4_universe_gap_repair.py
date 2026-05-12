from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
OUT_DIR = BASE_DIR / "data" / "ops" / "daily_ops_summary"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def repair_universe_gaps(date_str: str, profile: str = "may_sprint") -> dict:
    key = _date_key(date_str)
    task = _load_json(MONITOR_DIR / f"v4_capture_tasks_{key}.json", {})
    missing = list(task.get("universe_files_missing") or [])
    used = set(task.get("universe_files_used") or [])
    expected = list(task.get("universe_files_expected") or [])

    attempts = []
    repaired = []
    skipped = []

    # Best-effort repair: backfill each missing day by v4_runner --date.
    has_key = bool(os.environ.get("APIFOOTBALL_KEY"))
    for k in missing:
        if not has_key:
            skipped.append({"key": k, "reason": "missing_APIFOOTBALL_KEY"})
            continue
        cmd = [
            "python3",
            "engine/v4_runner.py",
            "--date",
            k,
            "--scan-mode",
            "fast",
            "--recent-prewarm",
            "off",
        ]
        proc = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
        attempts.append({"key": k, "cmd": cmd, "returncode": proc.returncode})
        if proc.returncode == 0:
            repaired.append(k)
        else:
            skipped.append({"key": k, "reason": "runner_failed", "stderr_tail": proc.stderr[-300:]})

    out = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "profile": profile,
        "expected_keys": expected,
        "used_keys": sorted(used),
        "missing_keys": missing,
        "attempts": attempts,
        "repaired_keys": repaired,
        "skipped": skipped,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"v4_universe_gap_repair_{key}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["output_path"] = str(path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--profile", default="may_sprint")
    args = parser.parse_args()
    print(json.dumps(repair_universe_gaps(args.date, args.profile), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
