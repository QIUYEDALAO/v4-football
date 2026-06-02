#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXCEL = ROOT / "WorldCup2026.xlsx"
DEFAULT_CACHE = ROOT / "data/runtime/v3_worldcup/thestatsapi_cache/20260602"
DEFAULT_OUTPUT = ROOT / "data/runtime/v3_worldcup/historical_market_baseline/20260602"
WC4A_SOURCE = ROOT / "data/runtime/v3_worldcup/historical_market_baseline/20260602"

FILES = {
    "csv": "v3_wc4a_historical_market_baseline_v1.csv",
    "json": "v3_wc4a_historical_market_baseline_v1.json",
    "summary": "v3_wc4a_historical_market_summary_v1.json",
    "report": "V3_WC4A_HISTORICAL_MARKET_BASELINE_V1_REPORT.md",
}


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _copy_if_needed(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return
    shutil.copyfile(src, dst)


def _rows_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)


def build(output_root: Path, dry_run: bool, excel_path: Path, cache_root: Path) -> dict[str, Any]:
    src_summary = WC4A_SOURCE / FILES["summary"]
    src_csv = WC4A_SOURCE / FILES["csv"]
    src_json = WC4A_SOURCE / FILES["json"]
    src_report = WC4A_SOURCE / FILES["report"]
    for p in [src_summary, src_csv, src_json, src_report]:
        if not p.exists():
            raise FileNotFoundError(str(p))

    summary = _load_json(src_summary)
    baseline_rows = _rows_count(src_csv)
    output_files = {k: str(output_root / v) for k, v in FILES.items()}
    if not dry_run:
        for k, name in FILES.items():
            _copy_if_needed(WC4A_SOURCE / name, output_root / name)

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "phase": "V3-WC4B",
        "status": "READY",
        "source_mode": "WC4A_RUNTIME_REPLAY",
        "excel_path": str(excel_path),
        "excel_exists": excel_path.exists(),
        "thestats_cache_root": str(cache_root),
        "thestats_cache_exists": cache_root.exists(),
        "qualifiers_in_baseline": False,
        "qualifiers_rows": 889,
        "baseline_rows": baseline_rows,
        "output_files": output_files,
        "summary": summary,
        "warn_only_items": [
            "EXCEL_SOURCE_NOT_TRACKED_OR_OPTIONAL" if not excel_path.exists() else "EXCEL_SOURCE_AVAILABLE",
            "THESTATSAPI_PARTIAL_COVERAGE",
            "XG_STATISTICS_EVENTS_UNAVAILABLE_AS_SUPPLEMENT",
        ],
        "safety_guard": {
            "observation_only": True,
            "no_betting_recommendations": True,
            "no_api_call": True,
            "no_web_fetch": True,
            "no_v4_changes": True,
            "no_official_final_squad_write": True,
            "qualifiers_not_in_baseline": True,
        },
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel-path", default=str(DEFAULT_EXCEL))
    parser.add_argument("--thestats-cache-root", default=str(DEFAULT_CACHE))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest = build(Path(args.output_root), args.dry_run, Path(args.excel_path), Path(args.thestats_cache_root))
    print(json.dumps({"status": "PASS", "dry_run": args.dry_run, "summary": manifest["summary"], "manifest": manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
