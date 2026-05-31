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
STATUS_DIR = ROOT / "data" / "runtime" / "status"
ACCEPT_DIR = ROOT / "data" / "runtime" / "acceptance"
TZ = timezone(timedelta(hours=8))


def _today_ymd() -> str:
    return datetime.now(TZ).strftime("%Y%m%d")


def _latest_compare_json(before: set[Path], out_dir: Path) -> Path | None:
    after = set(out_dir.glob("v4_collection_pipeline_canary_compare_*.json"))
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime)
    if new_files:
        return new_files[-1]
    all_files = sorted(after, key=lambda p: p.stat().st_mtime)
    return all_files[-1] if all_files else None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_model() -> Path | None:
    files = sorted(STATUS_DIR.glob("v4_control_center_model_*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _status(raw: int, scout: int, mismatch: int) -> str:
    if raw > 0 and scout == 0:
        return "BLOCKED"
    if mismatch > 0:
        return "BLOCKED"
    return "PASS"


def _render_md(path: Path, payload: dict[str, Any]) -> None:
    off = payload["official_legacy"]
    lazy = payload["rf_lazy_shadow"]
    c = payload["comparison"]
    lines = [
        "# V4 Daily Shadow Canary",
        "",
        f"- scan_date: `{payload['scan_date']}`",
        f"- window: `{payload['window']}`",
        f"- fixture_universe: `{payload['fixture_universe']}`",
        f"- max_fixtures: `{payload['max_fixtures']}`",
        f"- no_push: `{payload['no_push']}`",
        f"- scan_engine: `{payload['scan_engine']}`",
        "",
        "## Official",
        f"- raw/scout/A/B/C/SKIP: `{off['raw_fixture_count']}/{off['scout_row_count']}/{off['A_count']}/{off['B_count']}/{off['C_count']}/{off['SKIP_count']}`",
        "",
        "## Lazy",
        f"- raw/scout/A/B/C/SKIP: `{lazy['raw_fixture_count']}/{lazy['scout_row_count']}/{lazy['A_count']}/{lazy['B_count']}/{lazy['C_count']}/{lazy['SKIP_count']}`",
        f"- h2h required true/false: `{lazy['h2h_required_true_count']}/{lazy['h2h_required_false_count']}`",
        f"- h2h collected/skipped: `{lazy['h2h_collected_count']}/{lazy['h2h_skipped_count']}`",
        f"- events required true/false: `{lazy['events_required_true_count']}/{lazy['events_required_false_count']}`",
        f"- events collected/skipped: `{lazy['events_collected_count']}/{lazy['events_skipped_count']}`",
        f"- cpl required true/false: `{lazy['cpl_required_true_count']}/{lazy['cpl_required_false_count']}`",
        f"- cpl collected/skipped: `{lazy['cpl_collected_count']}/{lazy['cpl_skipped_count']}`",
        f"- estimated_saved: `{lazy['estimated_expensive_calls_saved']}`",
        "",
        "## Safety",
        f"- lazy_scout_zero_risk: `{c['lazy_scout_zero_risk']}`",
        f"- official_grade_mismatch_count: `{c['official_grade_mismatch_count']}`",
        f"- official_fixture_coverage_ok: `{c['official_fixture_coverage_ok']}`",
        f"- official_ab_coverage_ok: `{c['official_ab_coverage_ok']}`",
        f"- shadow_only_pending_hits: `{c['shadow_only_pending_hits']}`",
        f"- validation_touched: `{c['validation_touched']}`",
        f"- live_bet_touched: `{c['live_bet_touched']}`",
        f"- qq_pushed: `{c['qq_pushed']}`",
        f"- canary_status: `{payload['daily_canary_status']}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-date", default=_today_ymd())
    parser.add_argument("--window", default="midday")
    parser.add_argument("--fixture-universe", default="whitelist", choices=["whitelist", "all_eligible"])
    parser.add_argument("--max-fixtures", type=int, default=15)
    parser.add_argument("--output-dir", default=str(ACCEPT_DIR))
    args = parser.parse_args()

    if args.max_fixtures <= 0:
        raise SystemExit("--max-fixtures must be positive")
    if args.max_fixtures > 15:
        raise SystemExit("--max-fixtures must be <= 15 for daily shadow canary")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    before = set(out_dir.glob("v4_collection_pipeline_canary_compare_*.json"))
    cmd = [
        "python3",
        str(CANARY_TOOL),
        "--scan-date",
        args.scan_date,
        "--window",
        args.window,
        "--fixture-universe",
        args.fixture_universe,
        "--max-fixtures",
        str(args.max_fixtures),
        "--output-dir",
        str(out_dir),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    compare_json = _latest_compare_json(before, out_dir)

    if proc.returncode != 0 or not compare_json or not compare_json.exists():
        print(json.dumps({
            "status": "FAILED",
            "command": " ".join(shlex.quote(x) for x in cmd),
            "return_code": proc.returncode,
            "tail": (proc.stdout + "\n" + proc.stderr)[-2000:],
            "compare_json": str(compare_json) if compare_json else "",
        }, ensure_ascii=False, indent=2))
        return 1

    cp = _read_json(compare_json)
    off = cp.get("official_legacy") or {}
    lazy = cp.get("rf_lazy_shadow") or {}

    mismatch = 0
    detail = str(((cp.get("comparison") or {}).get("official_grade_same_or_explained") or {}).get("detail") or "")
    for token in detail.split(","):
        token = token.strip()
        if token.startswith("mismatch="):
            try:
                mismatch = int(token.split("=", 1)[1])
            except Exception:
                mismatch = 0

    missing_off = cp.get("missing_official_fixture_ids_in_lazy") or []
    missing_ab = cp.get("missing_official_ab_fixture_ids_in_lazy") or []
    official_ids = set(str(x) for x in (cp.get("official_fixture_ids") or []))
    lazy_ids = set(str(x) for x in (cp.get("lazy_fixture_ids") or []))
    shadow_only = sorted(lazy_ids - official_ids)

    pending_ids: set[str] = set()
    model_path = _latest_model()
    if model_path and model_path.exists():
        model = _read_json(model_path)
        for r in (model.get("pending_bet_candidates") or []):
            if isinstance(r, dict):
                fid = str(r.get("fixture_id") or "").strip()
                if fid:
                    pending_ids.add(fid)

    shadow_pending_hits = sorted(set(shadow_only) & pending_ids)

    cmp_summary = {
        "lazy_scout_zero_risk": (int(lazy.get("raw_fixture_count") or 0) > 0 and int(lazy.get("scout_row_count") or 0) == 0),
        "official_grade_mismatch_count": mismatch,
        "official_fixture_coverage_ok": len(missing_off) == 0,
        "official_ab_coverage_ok": len(missing_ab) == 0,
        "shadow_only_pending_hits": len(shadow_pending_hits),
        "validation_touched": False,
        "live_bet_touched": False,
        "qq_pushed": False,
    }

    payload = {
        "scan_date": args.scan_date,
        "window": args.window,
        "fixture_universe": args.fixture_universe,
        "max_fixtures": args.max_fixtures,
        "scan_engine": "serial",
        "no_push": True,
        "official_legacy": {
            "raw_fixture_count": int(off.get("raw_fixture_count") or 0),
            "scout_row_count": int(off.get("scout_row_count") or 0),
            "A_count": int(off.get("A_count") or 0),
            "B_count": int(off.get("B_count") or 0),
            "C_count": int(off.get("C_count") or 0),
            "SKIP_count": int(off.get("SKIP_count") or 0),
        },
        "rf_lazy_shadow": {
            "raw_fixture_count": int(lazy.get("raw_fixture_count") or 0),
            "scout_row_count": int(lazy.get("scout_row_count") or 0),
            "A_count": int(lazy.get("A_count") or 0),
            "B_count": int(lazy.get("B_count") or 0),
            "C_count": int(lazy.get("C_count") or 0),
            "SKIP_count": int(lazy.get("SKIP_count") or 0),
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
        },
        "comparison": cmp_summary,
        "source_compare_json": str(compare_json),
        "source_compare_md": str(compare_json).replace(".json", ".md"),
        "missing_official_fixture_ids_in_lazy": missing_off,
        "missing_official_ab_fixture_ids_in_lazy": missing_ab,
        "shadow_only_fixture_ids": shadow_only,
        "shadow_only_pending_fixture_ids": shadow_pending_hits,
        "daily_canary_status": _status(
            int(lazy.get("raw_fixture_count") or 0),
            int(lazy.get("scout_row_count") or 0),
            mismatch,
        ),
        "generated_at": datetime.now(TZ).isoformat(),
        "command": " ".join(shlex.quote(x) for x in cmd),
    }

    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    daily_json = out_dir / f"v4_collection_pipeline_daily_shadow_canary_{args.scan_date}_{ts}.json"
    daily_md = out_dir / f"v4_collection_pipeline_daily_shadow_canary_{args.scan_date}_{ts}.md"
    daily_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _render_md(daily_md, payload)

    print(json.dumps({
        "status": payload["daily_canary_status"],
        "daily_json": str(daily_json),
        "daily_md": str(daily_md),
        "source_compare_json": str(compare_json),
        "official_scout": payload["official_legacy"]["scout_row_count"],
        "lazy_scout": payload["rf_lazy_shadow"]["scout_row_count"],
    }, ensure_ascii=False, indent=2))
    return 0 if payload["daily_canary_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
