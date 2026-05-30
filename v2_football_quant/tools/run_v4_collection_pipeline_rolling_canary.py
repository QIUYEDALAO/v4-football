#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANARY_TOOL = ROOT / "tools" / "run_v4_collection_pipeline_canary_compare.py"
ACCEPT_DIR = ROOT / "data" / "runtime" / "acceptance"
TZ = timezone(timedelta(hours=8))
DEFAULT_DATES = ["20260530", "20260529", "20260528"]


def _parse_dates(raw: str | None) -> list[str]:
    if not raw:
        return DEFAULT_DATES
    out: list[str] = []
    for part in raw.split(","):
        s = part.strip()
        if s:
            out.append(s)
    return out or DEFAULT_DATES


def _latest_compare_json(before: set[Path], out_dir: Path) -> Path | None:
    after = set(out_dir.glob("v4_collection_pipeline_canary_compare_*.json"))
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime)
    if new_files:
        return new_files[-1]
    all_files = sorted(after, key=lambda p: p.stat().st_mtime)
    return all_files[-1] if all_files else None


def _run_one_date(scan_date: str, window: str, fixture_universe: str, max_fixtures: int, output_dir: Path) -> dict[str, Any]:
    before = set(output_dir.glob("v4_collection_pipeline_canary_compare_*.json"))
    cmd = [
        "python3",
        str(CANARY_TOOL),
        "--scan-date",
        scan_date,
        "--window",
        window,
        "--fixture-universe",
        fixture_universe,
        "--max-fixtures",
        str(max_fixtures),
        "--output-dir",
        str(output_dir),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    combined = (proc.stdout + "\n" + proc.stderr).strip()
    compare_json = _latest_compare_json(before, output_dir)

    base = {
        "date": scan_date,
        "command": " ".join(shlex.quote(x) for x in cmd),
        "return_code": proc.returncode,
        "compare_json": str(compare_json) if compare_json else "",
        "error_tail": combined[-2000:] if proc.returncode != 0 else "",
    }
    if proc.returncode != 0 or not compare_json or not compare_json.exists():
        base.update(
            {
                "status": "FAILED",
                "official_legacy_raw": 0,
                "official_legacy_scout": 0,
                "official_legacy_A": 0,
                "official_legacy_B": 0,
                "official_legacy_C": 0,
                "official_legacy_SKIP": 0,
                "rf_lazy_shadow_raw": 0,
                "rf_lazy_shadow_scout": 0,
                "rf_lazy_shadow_A": 0,
                "rf_lazy_shadow_B": 0,
                "rf_lazy_shadow_C": 0,
                "rf_lazy_shadow_SKIP": 0,
                "scout_zero_risk": True,
                "common_fixture_count": 0,
                "official_grade_mismatch_count": 0,
                "h2h_required_true_count": 0,
                "h2h_required_false_count": 0,
                "h2h_collected_count": 0,
                "h2h_skipped_count": 0,
                "events_required_true_count": 0,
                "events_required_false_count": 0,
                "events_collected_count": 0,
                "events_skipped_count": 0,
                "cpl_required_true_count": 0,
                "cpl_required_false_count": 0,
                "cpl_collected_count": 0,
                "cpl_skipped_count": 0,
                "estimated_expensive_calls_saved": 0,
                "no_regrade": False,
            }
        )
        return base

    payload = json.loads(compare_json.read_text(encoding="utf-8"))
    off = payload.get("official_legacy") or {}
    lazy = payload.get("rf_lazy_shadow") or {}
    cmpv = payload.get("comparison") or {}

    common_count = 0
    mismatch_count = 0
    detail = str((cmpv.get("official_grade_same_or_explained") or {}).get("detail") or "")
    for token in detail.split(","):
        token = token.strip()
        if token.startswith("common="):
            try:
                common_count = int(token.split("=", 1)[1])
            except Exception:
                common_count = 0
        if token.startswith("mismatch="):
            try:
                mismatch_count = int(token.split("=", 1)[1])
            except Exception:
                mismatch_count = 0

    lazy_raw = int(lazy.get("raw_fixture_count") or 0)
    lazy_scout = int(lazy.get("scout_row_count") or 0)
    # Rolling risk should focus on the lazy pipeline itself.
    lazy_scout_zero_risk = lazy_raw > 0 and lazy_scout == 0

    base.update(
        {
            "status": "PASS",
            "official_legacy_raw": int(off.get("raw_fixture_count") or 0),
            "official_legacy_scout": int(off.get("scout_row_count") or 0),
            "official_legacy_A": int(off.get("A_count") or 0),
            "official_legacy_B": int(off.get("B_count") or 0),
            "official_legacy_C": int(off.get("C_count") or 0),
            "official_legacy_SKIP": int(off.get("SKIP_count") or 0),
            "rf_lazy_shadow_raw": lazy_raw,
            "rf_lazy_shadow_scout": lazy_scout,
            "rf_lazy_shadow_A": int(lazy.get("A_count") or 0),
            "rf_lazy_shadow_B": int(lazy.get("B_count") or 0),
            "rf_lazy_shadow_C": int(lazy.get("C_count") or 0),
            "rf_lazy_shadow_SKIP": int(lazy.get("SKIP_count") or 0),
            "scout_zero_risk": lazy_scout_zero_risk,
            "common_fixture_count": common_count,
            "official_grade_mismatch_count": mismatch_count,
            "h2h_required_true_count": int(lazy.get("h2h_required_true_count") or 0),
            "h2h_required_false_count": int(lazy.get("h2h_required_false_count") or 0),
            "h2h_collected_count": int(lazy.get("h2h_collected_count") or 0),
            "h2h_skipped_count": int(lazy.get("h2h_skipped_count") or 0),
            "events_required_true_count": int(lazy.get("events_required_true_count") or 0),
            "events_required_false_count": int(lazy.get("events_required_false_count") or 0),
            "events_collected_count": int(lazy.get("events_collected_count") or 0),
            "events_skipped_count": int(lazy.get("events_skipped_count") or 0),
            "cpl_required_true_count": int(lazy.get("cpl_required_true_count") or 0),
            "cpl_required_false_count": int(lazy.get("cpl_required_false_count") or 0),
            "cpl_collected_count": int(lazy.get("cpl_collected_count") or 0),
            "cpl_skipped_count": int(lazy.get("cpl_skipped_count") or 0),
            "estimated_expensive_calls_saved": int(lazy.get("estimated_expensive_calls_saved") or 0),
            "no_regrade": bool((cmpv.get("no_regrade") or {}).get("ok")),
        }
    )
    return base


def _render_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# V4 Lazy Shadow Rolling Canary",
        "",
        f"- dates: `{','.join(payload['dates'])}`",
        f"- max_fixtures: `{payload['max_fixtures']}`",
        f"- fixture_universe: `{payload['fixture_universe']}`",
        f"- window: `{payload['window']}`",
        "",
        "## Per-date",
    ]

    for row in payload["per_date_results"]:
        lines.extend(
            [
                f"### {row['date']} ({row['status']})",
                f"- official raw/scout/A/B/C/SKIP: `{row['official_legacy_raw']}/{row['official_legacy_scout']}/{row['official_legacy_A']}/{row['official_legacy_B']}/{row['official_legacy_C']}/{row['official_legacy_SKIP']}`",
                f"- lazy raw/scout/A/B/C/SKIP: `{row['rf_lazy_shadow_raw']}/{row['rf_lazy_shadow_scout']}/{row['rf_lazy_shadow_A']}/{row['rf_lazy_shadow_B']}/{row['rf_lazy_shadow_C']}/{row['rf_lazy_shadow_SKIP']}`",
                f"- scout_zero_risk: `{row['scout_zero_risk']}`",
                f"- common/mismatch: `{row['common_fixture_count']}/{row['official_grade_mismatch_count']}`",
                f"- h2h true/false/collected/skipped: `{row['h2h_required_true_count']}/{row['h2h_required_false_count']}/{row['h2h_collected_count']}/{row['h2h_skipped_count']}`",
                f"- events true/false/collected/skipped: `{row['events_required_true_count']}/{row['events_required_false_count']}/{row['events_collected_count']}/{row['events_skipped_count']}`",
                f"- cpl true/false/collected/skipped: `{row['cpl_required_true_count']}/{row['cpl_required_false_count']}/{row['cpl_collected_count']}/{row['cpl_skipped_count']}`",
                f"- estimated_saved: `{row['estimated_expensive_calls_saved']}`",
            ]
        )
        if row.get("error_tail"):
            lines.append(f"- error: `{row['error_tail'][:240]}`")
        lines.append("")

    agg = payload["aggregate"]
    lines.extend(
        [
            "## Aggregate",
            f"- dates_total/passed/blocked: `{agg['dates_total']}/{agg['dates_passed']}/{agg['dates_blocked']}`",
            f"- total_official_scout: `{agg['total_official_scout']}`",
            f"- total_lazy_scout: `{agg['total_lazy_scout']}`",
            f"- total_common_fixtures: `{agg['total_common_fixtures']}`",
            f"- total_official_grade_mismatch: `{agg['total_official_grade_mismatch']}`",
            f"- total_expensive_calls_saved: `{agg['total_expensive_calls_saved']}`",
            f"- any_scout_zero/any_regrade: `{agg['any_scout_zero']}/{agg['any_regrade']}`",
            f"- any_validation_touch/any_live_bet_touch/any_qq_push: `{agg['any_validation_touch']}/{agg['any_live_bet_touch']}/{agg['any_qq_push']}`",
            f"- rolling_canary_status: `{agg['rolling_canary_status']}`",
        ]
    )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", default=",".join(DEFAULT_DATES))
    parser.add_argument("--window", default="midday")
    parser.add_argument("--fixture-universe", default="whitelist", choices=["whitelist", "all_eligible"])
    parser.add_argument("--max-fixtures", type=int, default=5)
    parser.add_argument("--output-dir", default=str(ACCEPT_DIR))
    args = parser.parse_args()

    if args.max_fixtures <= 0:
        raise SystemExit("--max-fixtures must be positive")
    if args.max_fixtures > 15:
        raise SystemExit("--max-fixtures must be <= 15 for rolling canary")

    dates = _parse_dates(args.dates)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    per_date: list[dict[str, Any]] = []
    for d in dates:
        per_date.append(
            _run_one_date(
                scan_date=d,
                window=args.window,
                fixture_universe=args.fixture_universe,
                max_fixtures=args.max_fixtures,
                output_dir=output_dir,
            )
        )

    dates_total = len(per_date)
    dates_passed = sum(1 for r in per_date if r.get("status") == "PASS")
    dates_blocked = dates_total - dates_passed

    total_official_scout = sum(int(r.get("official_legacy_scout") or 0) for r in per_date)
    total_lazy_scout = sum(int(r.get("rf_lazy_shadow_scout") or 0) for r in per_date)
    total_common = sum(int(r.get("common_fixture_count") or 0) for r in per_date)
    total_mismatch = sum(int(r.get("official_grade_mismatch_count") or 0) for r in per_date)
    total_saved = sum(int(r.get("estimated_expensive_calls_saved") or 0) for r in per_date)

    any_scout_zero = any(bool(r.get("scout_zero_risk")) for r in per_date)
    any_regrade = total_mismatch > 0 or any(not bool(r.get("no_regrade", False)) for r in per_date if r.get("status") == "PASS")

    aggregate = {
        "dates_total": dates_total,
        "dates_passed": dates_passed,
        "dates_blocked": dates_blocked,
        "total_official_scout": total_official_scout,
        "total_lazy_scout": total_lazy_scout,
        "total_common_fixtures": total_common,
        "total_official_grade_mismatch": total_mismatch,
        "total_expensive_calls_saved": total_saved,
        "any_scout_zero": any_scout_zero,
        "any_regrade": any_regrade,
        "any_validation_touch": False,
        "any_live_bet_touch": False,
        "any_qq_push": False,
        "rolling_canary_status": "PASS" if (dates_passed >= 2 and not any_scout_zero and not any_regrade) else "BLOCKED",
    }

    payload = {
        "dates": dates,
        "window": args.window,
        "fixture_universe": args.fixture_universe,
        "max_fixtures": args.max_fixtures,
        "per_date_results": per_date,
        "aggregate": aggregate,
        "generated_at": datetime.now(TZ).isoformat(),
    }

    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    out_json = output_dir / f"v4_collection_pipeline_rolling_canary_{ts}.json"
    out_md = output_dir / f"v4_collection_pipeline_rolling_canary_{ts}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _render_markdown(out_md, payload)

    print(
        json.dumps(
            {
                "status": aggregate["rolling_canary_status"],
                "dates": dates,
                "dates_passed": dates_passed,
                "dates_blocked": dates_blocked,
                "rolling_json": str(out_json),
                "rolling_md": str(out_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if aggregate["rolling_canary_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
