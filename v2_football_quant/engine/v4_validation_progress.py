from __future__ import annotations

import argparse
import json
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
SNAP_ROOT = BASE_DIR / "data" / "live_odds_snapshots"
OUT_DIR = BASE_DIR / "data" / "ops" / "validation_progress"

TARGETS = {
    "a_samples": 50,
    "b_shadow": 200,
    "decay_snapshots": 3000,
    "asian_line_coverage_pct": 80.0,
}


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def build_progress(month: str) -> dict:
    # month: YYYYMM
    task_files = sorted(MONITOR_DIR.glob(f"v4_capture_tasks_{month}*.json"))
    a = 0
    b = 0
    decay = 0
    norm = 0
    asian = 0

    for tf in task_files:
        obj = _load_json(tf, {})
        a += int((obj.get("tier_counts") or {}).get("A_candidate", 0))
        b += int((obj.get("tier_counts") or {}).get("B_shadow", 0))

    for day_dir in SNAP_ROOT.glob(f"{month}*"):
        decay += _count_jsonl(day_dir / "live_odds_raw.jsonl")
        norm_path = day_dir / "live_odds_normalized.jsonl"
        if norm_path.exists():
            with open(norm_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    norm += 1
                    line_v = row.get("line")
                    if line_v in (0.75, 1.0, 1.25):
                        asian += 1

    cov = round(asian / norm * 100, 2) if norm else 0.0
    today = date.today()
    deadline = date(int(month[:4]), int(month[4:6]), 31)
    days_left = (deadline - today).days

    behind = []
    if a < TARGETS["a_samples"]:
        behind.append("A")
    if b < TARGETS["b_shadow"]:
        behind.append("B")
    if decay < TARGETS["decay_snapshots"]:
        behind.append("DECAY")
    if cov < TARGETS["asian_line_coverage_pct"]:
        behind.append("ASIAN_COV")
    status = "BEHIND" if behind else "ON_TRACK"

    out = {
        "month": month,
        "generated_at": datetime.now().isoformat(),
        "a_samples": {"current": a, "target": TARGETS["a_samples"]},
        "b_shadow": {"current": b, "target": TARGETS["b_shadow"]},
        "decay_snapshots": {"current": decay, "target": TARGETS["decay_snapshots"]},
        "asian_line_coverage_pct": {"current": cov, "target": TARGETS["asian_line_coverage_pct"]},
        "days_to_deadline": days_left,
        "status": status,
        "behind_items": behind,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"v4_validation_progress_{month}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["output_path"] = str(out_path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=datetime.now().strftime("%Y%m"))
    args = parser.parse_args()
    print(json.dumps(build_progress(args.month), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
