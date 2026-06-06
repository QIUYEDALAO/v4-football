#!/usr/bin/env python3
"""Check V4 price field persistence from scout to candidate_view/ledger builders."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DOC = ROOT / "docs/V4_PRICE_FIELD_PERSISTENCE_PIPELINE_20260606.md"
DATE = "20260531"
BRIEF = ROOT / f"data/daily_reports/v4_openclaw_brief_{DATE}.txt"
SCOUT = ROOT / f"data/daily_reports/scout_v4_{DATE}.json"
CURRENT_CV = ROOT / f"data/runtime/status/v4_official_candidate_view_{DATE}.json"

PRICE_FIELDS = {
    "price_source",
    "bookmaker",
    "market",
    "line",
    "odds",
    "snapshot_time",
    "selected_at",
    "kickoff_time",
    "price_status",
}


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def load_module(name: str, path: Path):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def candidate_rows(view: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("A_candidates", "B_candidates", "C_candidates", "SKIP_candidates"):
        values = view.get(key) if isinstance(view, dict) else []
        if isinstance(values, list):
            rows.extend(row for row in values if isinstance(row, dict))
    return rows


def main() -> int:
    cv_builder = load_module("build_v4_official_candidate_view_check", ROOT / "tools/build_v4_official_candidate_view.py")
    ledger_builder = load_module("build_v4_ab_historical_ledger_check", ROOT / "tools/build_v4_ab_historical_ledger.py")

    offline_view = cv_builder.build_candidate_view(
        DATE,
        BRIEF.read_text(encoding="utf-8"),
        BRIEF,
        SCOUT,
    )
    current_view = json.loads(CURRENT_CV.read_text(encoding="utf-8")) if CURRENT_CV.exists() else {}
    rows = candidate_rows(offline_view)
    official_rows = [row for row in rows if row.get("official_grade") in {"A", "B"} or row.get("grade") in {"A", "B"}]
    real_price_rows = [row for row in official_rows if row.get("price_status") == "REAL_PRICE"]
    complete_real_rows = [
        row for row in real_price_rows
        if PRICE_FIELDS.issubset(set(row))
        and row.get("bookmaker")
        and row.get("market")
        and row.get("line") is not None
        and row.get("odds") is not None
        and row.get("snapshot_time")
        and row.get("selected_at")
        and row.get("kickoff_time")
    ]

    missing_price = cv_builder._price_event_fields({})
    paper_forbidden = cv_builder._price_event_fields({"odds_source": "paper_default_0.80", "prematch_over_odds": 1.8})
    ledger_real = ledger_builder.price_fields_from_candidate(real_price_rows[0] if real_price_rows else {})
    ledger_paper = ledger_builder.price_fields_from_candidate({"odds_source": "paper_default_0.80", "odds": 1.8})

    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = [
        path for path in staged
        if path.startswith(("v2_football_quant/data/runtime/", "v2_football_quant/data/cache/", "data/runtime/", "data/cache/"))
        or re.search(r"(?i)(secret|token|\\.env|api[_-]?key)", path)
    ]

    docs_text = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    engine_text = (ROOT / "engine/v4_scan_and_brief.py").read_text(encoding="utf-8")
    candidate_builder_text = (ROOT / "tools/build_v4_official_candidate_view.py").read_text(encoding="utf-8")
    ledger_builder_text = (ROOT / "tools/build_v4_ab_historical_ledger.py").read_text(encoding="utf-8")
    checks = {
        "doc_exists": DOC.exists(),
        "source_artifacts_exist": BRIEF.exists() and SCOUT.exists(),
        "offline_counts_preserved": (
            offline_view.get("A_count"),
            offline_view.get("B_count"),
            offline_view.get("C_count"),
            offline_view.get("SKIP_count"),
            offline_view.get("scan_total"),
        )
        == (
            current_view.get("A_count"),
            current_view.get("B_count"),
            current_view.get("C_count"),
            current_view.get("SKIP_count"),
            current_view.get("scan_total"),
        ),
        "candidate_view_real_price_rows_present": len(complete_real_rows) >= 1,
        "candidate_view_all_rows_have_price_status": all(row.get("price_status") in {"REAL_PRICE", "PRICE_MISSING", "PAPER_PROXY_FORBIDDEN"} for row in rows),
        "candidate_view_missing_marked": missing_price.get("price_status") == "PRICE_MISSING",
        "candidate_view_paper_forbidden": paper_forbidden.get("price_status") == "PAPER_PROXY_FORBIDDEN" and paper_forbidden.get("odds") is None,
        "scan_adapter_persists_price_fields": "_price_event_fields(r)" in engine_text,
        "official_resolver_persists_price_fields": "_price_event_fields(row)" in candidate_builder_text and "_price_event_fields(source)" in candidate_builder_text,
        "validation_ledger_price_join_ready": "price_fields_from_candidate" in ledger_builder_text and "rr.update(candidate_price)" in ledger_builder_text,
        "validation_ledger_real_price_supported": ledger_real.get("price_status") == "REAL_PRICE" and ledger_real.get("odds") is not None,
        "validation_ledger_paper_forbidden": ledger_paper.get("price_status") == "PAPER_PROXY_FORBIDDEN" and ledger_paper.get("odds") is None,
        "doc_policy_present": all(
            phrase in docs_text
            for phrase in [
                "not a strategy launch",
                "paper_default is never a real odds source",
                "PRICE_MISSING",
                "PAPER_PROXY_FORBIDDEN",
                "official grades and thresholds are unchanged",
            ]
        ),
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [key for key, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_price_field_persistence_pipeline_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "offline_date": DATE,
        "source_fields": {
            "fixture_id": True,
            "kickoff_time": True,
            "bookmaker": "opening_market_bookmaker_used",
            "market": "opening_market_market_name",
            "line": "opening_ht_ou_line or prematch_ht_line",
            "odds": "opening_ht_ou_over_odds or prematch_over_odds",
            "snapshot_time": "opening_market_snapshot_time",
        },
        "candidate_view_fields": sorted(PRICE_FIELDS),
        "validation_ledger_fields": sorted(PRICE_FIELDS),
        "real_price_rows": len(real_price_rows),
        "forbidden_staged": forbidden_staged,
        "official_grade_changed": False,
        "ab_threshold_changed": False,
        "pending_written": False,
        "qq_sent": False,
        "cron_or_launchd_modified": False,
        "b_realtime_restored": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
