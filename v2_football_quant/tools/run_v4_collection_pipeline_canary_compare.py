#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine" / "v4_scan_and_brief.py"
REPORT = ROOT / "data" / "daily_reports"
STATUS = ROOT / "data" / "runtime" / "status"
UNIVERSE = ROOT / "data" / "universe"
ACCEPTANCE_DEFAULT = ROOT / "data" / "runtime" / "acceptance"
TZ = timezone(timedelta(hours=8))


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                rows.append(obj)
        except Exception:
            continue
    return rows


def _counter(rows: list[dict[str, Any]], field: str) -> Counter:
    c: Counter = Counter()
    for r in rows:
        c[str(r.get(field) or "").upper()] += 1
    return c


def _count_bool(rows: list[dict[str, Any]], key: str, target: bool) -> int:
    return sum(1 for r in rows if bool(r.get(key)) is target)


def _count_nonempty(rows: list[dict[str, Any]], key: str) -> int:
    return sum(1 for r in rows if str(r.get(key) or "").strip() != "")


def _latest_path(path: Path) -> Path:
    return path


def _run_scan(scan_date: str, window: str, fixture_universe: str, mode: str, max_fixtures: int) -> tuple[int, str, str]:
    cmd = [
        "python3",
        "-u",
        str(ENGINE),
        "--scan-date",
        scan_date,
        "--window",
        window,
        "--no-push",
        "--scan-engine",
        "serial",
        "--fixture-universe",
        fixture_universe,
        "--collection-mode",
        mode,
        "--max-fixtures",
        str(max_fixtures),
    ]
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return p.returncode, " ".join(shlex.quote(x) for x in cmd), (p.stdout + "\n" + p.stderr).strip()


def _build_mode_summary(scan_date: str, mode: str) -> dict[str, Any]:
    scout_path = REPORT / f"scout_v4_{scan_date}.json"
    universe_path = UNIVERSE / f"fixtures_universe_{scan_date}.jsonl"

    scout_rows = _read_json(scout_path) if scout_path.exists() else []
    if not isinstance(scout_rows, list):
        scout_rows = []
    scout_rows = [r for r in scout_rows if isinstance(r, dict)]
    universe_rows = _read_jsonl(universe_path)

    grade_counter = _counter(scout_rows, "grade")
    reason_counter = _counter(scout_rows, "reason")

    out: dict[str, Any] = {
        "mode": mode,
        "raw_fixture_count": len(universe_rows),
        "scout_row_count": len(scout_rows),
        "A_count": grade_counter.get("A", 0),
        "B_count": grade_counter.get("B", 0),
        "C_count": grade_counter.get("C", 0),
        "SKIP_count": grade_counter.get("SKIP", 0),
        "DATA_TIMEOUT_count": reason_counter.get("DATA_TIMEOUT", 0),
        "SCORE_INCOMPLETE_count": reason_counter.get("SCORE_INCOMPLETE", 0),
        "scout_path": str(scout_path),
        "universe_path": str(universe_path),
    }

    if mode == "rf_lazy_shadow":
        out.update(
            {
                "h2h_required_true_count": _count_bool(scout_rows, "h2h_required", True),
                "h2h_required_false_count": _count_bool(scout_rows, "h2h_required", False),
                "h2h_collected_count": _count_bool(scout_rows, "h2h_collected", True),
                "h2h_skipped_count": _count_nonempty(scout_rows, "h2h_skipped_reason"),
                "events_required_true_count": _count_bool(scout_rows, "events_required", True),
                "events_required_false_count": _count_bool(scout_rows, "events_required", False),
                "events_collected_count": _count_bool(scout_rows, "events_collected", True),
                "events_skipped_count": _count_nonempty(scout_rows, "events_skipped_reason"),
                "cpl_required_true_count": _count_bool(scout_rows, "cpl_required", True),
                "cpl_required_false_count": _count_bool(scout_rows, "cpl_required", False),
                "cpl_collected_count": _count_bool(scout_rows, "cpl_collected", True),
                "cpl_skipped_count": _count_nonempty(scout_rows, "cpl_skipped_reason"),
                "estimated_expensive_calls_saved": int(
                    sum(int(r.get("expensive_calls_saved") or 0) for r in scout_rows)
                ),
            }
        )

    return out


def _grade_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    m: dict[str, str] = {}
    for r in rows:
        fid = str(r.get("fixture_id") or "").strip()
        if not fid:
            continue
        g = str(r.get("official_grade") or r.get("grade") or "").upper()
        m[fid] = g
    return m


def _fixture_id_set(rows: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for r in rows:
        fid = str(r.get("fixture_id") or "").strip()
        if fid:
            out.add(fid)
    return out


def _ab_fixture_id_set(rows: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for r in rows:
        fid = str(r.get("fixture_id") or "").strip()
        if not fid:
            continue
        g = str(r.get("official_grade") or r.get("grade") or "").upper()
        if g in {"A", "B"}:
            out.add(fid)
    return out


def _safe_explained(flag: bool, detail: str) -> dict[str, Any]:
    return {"ok": bool(flag), "detail": detail}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    off = payload["official_legacy"]
    lazy = payload["rf_lazy_shadow"]
    cmpv = payload["comparison"]
    lines = [
        f"# V4 Lazy Shadow Canary Compare ({payload['scan_date']})",
        "",
        f"- fixture_universe: `{payload['fixture_universe']}`",
        f"- max_fixtures: `{payload['max_fixtures']}`",
        f"- no_push: `{payload['no_push']}`",
        f"- serial: `{payload['scan_engine']}`",
        "",
        "## official_legacy",
        f"- raw/scout: `{off['raw_fixture_count']}` / `{off['scout_row_count']}`",
        f"- A/B/C/SKIP: `{off['A_count']}` / `{off['B_count']}` / `{off['C_count']}` / `{off['SKIP_count']}`",
        f"- DATA_TIMEOUT: `{off['DATA_TIMEOUT_count']}`",
        f"- SCORE_INCOMPLETE: `{off['SCORE_INCOMPLETE_count']}`",
        "",
        "## rf_lazy_shadow",
        f"- raw/scout: `{lazy['raw_fixture_count']}` / `{lazy['scout_row_count']}`",
        f"- A/B/C/SKIP: `{lazy['A_count']}` / `{lazy['B_count']}` / `{lazy['C_count']}` / `{lazy['SKIP_count']}`",
        f"- h2h required true/false: `{lazy.get('h2h_required_true_count',0)}` / `{lazy.get('h2h_required_false_count',0)}`",
        f"- h2h collected/skipped: `{lazy.get('h2h_collected_count',0)}` / `{lazy.get('h2h_skipped_count',0)}`",
        f"- events required true/false: `{lazy.get('events_required_true_count',0)}` / `{lazy.get('events_required_false_count',0)}`",
        f"- events collected/skipped: `{lazy.get('events_collected_count',0)}` / `{lazy.get('events_skipped_count',0)}`",
        f"- cpl required true/false: `{lazy.get('cpl_required_true_count',0)}` / `{lazy.get('cpl_required_false_count',0)}`",
        f"- cpl collected/skipped: `{lazy.get('cpl_collected_count',0)}` / `{lazy.get('cpl_skipped_count',0)}`",
        f"- estimated expensive calls saved: `{lazy.get('estimated_expensive_calls_saved',0)}`",
        "",
        "## comparison",
        f"- scout_row_count_same_or_explained: `{cmpv['scout_row_count_same_or_explained']['ok']}` ({cmpv['scout_row_count_same_or_explained']['detail']})",
        f"- official_grade_same_or_explained: `{cmpv['official_grade_same_or_explained']['ok']}` ({cmpv['official_grade_same_or_explained']['detail']})",
        f"- no_scout_zero: `{cmpv['no_scout_zero']['ok']}` ({cmpv['no_scout_zero']['detail']})",
        f"- no_regrade: `{cmpv['no_regrade']['ok']}` ({cmpv['no_regrade']['detail']})",
        f"- no_validation: `{cmpv['no_validation']['ok']}`",
        f"- no_live_bet_mutation: `{cmpv['no_live_bet_mutation']['ok']}`",
        f"- no_qq_push: `{cmpv['no_qq_push']['ok']}`",
        f"- canary_status: `{cmpv['canary_status']}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-date", required=True)
    parser.add_argument("--window", default="midday")
    parser.add_argument("--fixture-universe", default="whitelist", choices=["whitelist", "all_eligible"])
    parser.add_argument("--max-fixtures", type=int, default=5)
    parser.add_argument("--output-dir", default=str(ACCEPTANCE_DEFAULT))
    args = parser.parse_args()

    if args.max_fixtures <= 0:
        raise SystemExit("--max-fixtures must be positive")
    if args.max_fixtures > 15:
        raise SystemExit("--max-fixtures must be <= 15 for canary compare")

    _load_env_file(Path.home() / ".openclaw" / ".env")

    rc_off, cmd_off, out_off = _run_scan(
        scan_date=args.scan_date,
        window=args.window,
        fixture_universe=args.fixture_universe,
        mode="official_legacy",
        max_fixtures=args.max_fixtures,
    )
    if rc_off != 0:
        print(json.dumps({
            "status": "FAILED",
            "stage": "official_legacy_run",
            "return_code": rc_off,
            "command": cmd_off,
            "tail": out_off[-2000:],
        }, ensure_ascii=False, indent=2))
        return 1

    off_summary = _build_mode_summary(args.scan_date, "official_legacy")
    off_scout_rows = _read_json(Path(off_summary["scout_path"])) if Path(off_summary["scout_path"]).exists() else []
    off_scout_rows = [r for r in off_scout_rows if isinstance(r, dict)]

    rc_lazy, cmd_lazy, out_lazy = _run_scan(
        scan_date=args.scan_date,
        window=args.window,
        fixture_universe=args.fixture_universe,
        mode="rf_lazy_shadow",
        max_fixtures=args.max_fixtures,
    )
    if rc_lazy != 0:
        print(json.dumps({
            "status": "FAILED",
            "stage": "rf_lazy_shadow_run",
            "return_code": rc_lazy,
            "command": cmd_lazy,
            "tail": out_lazy[-2000:],
        }, ensure_ascii=False, indent=2))
        return 1

    lazy_summary = _build_mode_summary(args.scan_date, "rf_lazy_shadow")
    lazy_scout_rows = _read_json(Path(lazy_summary["scout_path"])) if Path(lazy_summary["scout_path"]).exists() else []
    lazy_scout_rows = [r for r in lazy_scout_rows if isinstance(r, dict)]

    off_grade_map = _grade_map(off_scout_rows)
    lazy_grade_map = _grade_map(lazy_scout_rows)
    off_fixture_ids = _fixture_id_set(off_scout_rows)
    lazy_fixture_ids = _fixture_id_set(lazy_scout_rows)
    off_ab_fixture_ids = _ab_fixture_id_set(off_scout_rows)
    missing_official_ids_in_lazy = sorted(off_fixture_ids - lazy_fixture_ids)
    missing_official_ab_ids_in_lazy = sorted(off_ab_fixture_ids - lazy_fixture_ids)
    common_ids = sorted(set(off_grade_map) & set(lazy_grade_map))
    mismatch_ids = [fid for fid in common_ids if off_grade_map.get(fid) != lazy_grade_map.get(fid)]

    scout_same = off_summary["scout_row_count"] == lazy_summary["scout_row_count"]
    scout_explain = f"official={off_summary['scout_row_count']},lazy={lazy_summary['scout_row_count']}"
    grade_same = len(mismatch_ids) == 0
    grade_explain = f"common={len(common_ids)},mismatch={len(mismatch_ids)}"

    cmpv = {
        "scout_row_count_same_or_explained": _safe_explained(scout_same, scout_explain),
        "official_grade_same_or_explained": _safe_explained(grade_same, grade_explain),
        "no_scout_zero": _safe_explained(
            (off_summary["scout_row_count"] > 0 and lazy_summary["scout_row_count"] > 0),
            f"official={off_summary['scout_row_count']},lazy={lazy_summary['scout_row_count']}",
        ),
        "no_regrade": _safe_explained(grade_same, grade_explain),
        "no_validation": {"ok": True, "detail": "canary tool does not run validation"},
        "no_live_bet_mutation": {"ok": True, "detail": "canary tool does not write live bet files"},
        "no_qq_push": {"ok": True, "detail": "command forces --no-push and QQ is hard-disabled"},
        "official_fixture_ids_covered_by_lazy": _safe_explained(
            len(missing_official_ids_in_lazy) == 0,
            f"official={len(off_fixture_ids)},lazy={len(lazy_fixture_ids)},missing={len(missing_official_ids_in_lazy)}",
        ),
        "official_ab_fixture_ids_covered_by_lazy": _safe_explained(
            len(missing_official_ab_ids_in_lazy) == 0,
            f"official_ab={len(off_ab_fixture_ids)},missing={len(missing_official_ab_ids_in_lazy)}",
        ),
        "canary_status": "PASS" if (off_summary["scout_row_count"] > 0 and lazy_summary["scout_row_count"] > 0 and grade_same) else "WARN",
        "official_command": cmd_off,
        "lazy_command": cmd_lazy,
    }

    payload = {
        "scan_date": args.scan_date,
        "window": args.window,
        "fixture_universe": args.fixture_universe,
        "max_fixtures": args.max_fixtures,
        "no_push": True,
        "scan_engine": "serial",
        "official_legacy": off_summary,
        "rf_lazy_shadow": lazy_summary,
        "official_fixture_ids": sorted(off_fixture_ids),
        "lazy_fixture_ids": sorted(lazy_fixture_ids),
        "official_ab_fixture_ids": sorted(off_ab_fixture_ids),
        "missing_official_fixture_ids_in_lazy": missing_official_ids_in_lazy,
        "missing_official_ab_fixture_ids_in_lazy": missing_official_ab_ids_in_lazy,
        "comparison": cmpv,
        "generated_at": datetime.now(TZ).isoformat(),
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"v4_collection_pipeline_canary_compare_{args.scan_date}_{ts}.json"
    md_path = out_dir / f"v4_collection_pipeline_canary_compare_{args.scan_date}_{ts}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(md_path, payload)

    print(json.dumps({
        "status": "OK",
        "compare_json": str(json_path),
        "compare_md": str(md_path),
        "official_command": cmd_off,
        "lazy_command": cmd_lazy,
        "canary_status": cmpv["canary_status"],
        "official_scout_row_count": off_summary["scout_row_count"],
        "lazy_scout_row_count": lazy_summary["scout_row_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
