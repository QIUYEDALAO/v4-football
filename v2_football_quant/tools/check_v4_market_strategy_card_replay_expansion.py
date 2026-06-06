#!/usr/bin/env python3
"""Check expanded V4 market strategy card replay stays read-only."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "config/v4_market_strategy_card_replay_expansion_schema.json"
LEDGER = ROOT / "data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_expansion_20260607.json"
SUMMARY = ROOT / "data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_expansion_summary_20260607.json"
BUILDER = ROOT / "tools/build_v4_market_strategy_card_replay_expansion.py"
DOC = ROOT / "docs/V4_MARKET_STRATEGY_CARD_REPLAY_EXPANSION_PACK_20260607.md"
STRATEGY_CHECKER = ROOT / "tools/check_v4_market_strategy_research_cards.py"
FIVE_CHECKER = ROOT / "tools/check_v4_five_dimension_lite.py"
MAIN_LEAGUE_CHECKER = ROOT / "tools/check_v4_main_league_admission_guard.py"
PRICE_CHECKER = ROOT / "tools/check_v4_price_field_persistence_pipeline.py"
PRODUCTION_GUARD = ROOT / "tools/check_v4_production_default_rules_guard.py"

REQUIRED_FIELDS = {
    "fixture_id",
    "match_info",
    "league_admission_status",
    "strategy_card_conclusion",
    "strategy_directions",
    "missing_context",
    "price_status",
    "line_status",
    "market_status",
    "result_available",
    "result_hit",
    "result_outcome",
    "replay_status",
}
ALLOWED_CONCLUSIONS = {"OBSERVE", "WAIT", "PASS"}
GAP_TAGS = {"PRICE_MISSING", "LINE_MISSING", "MARKET_MISSING", "DATA_INSUFFICIENT"}
FORBIDDEN_TERMS = re.compile(
    r"推荐|投注|下注|实单|必中|稳胆|梭哈|资金流|sharp|steam|drift|sure win|must bet|betting signal",
    re.IGNORECASE,
)


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def run_checker(path: Path) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=240)
    text = proc.stdout.strip()
    payload: Any = {}
    if "{" in text:
        try:
            payload = json.loads(text[text.find("{"):])
        except Exception:
            payload = {}
    return {"returncode": proc.returncode, "payload": payload}


def staged_forbidden(staged: list[str]) -> list[str]:
    bad: list[str] = []
    for path in staged:
        if path.startswith(("v2_football_quant/data/runtime/", "v2_football_quant/data/cache/")):
            bad.append(path)
        if re.search(r"(?i)(secret|token|\\.env|api[_-]?key)", path):
            bad.append(path)
    return sorted(set(bad))


def hit_rate_policy_ok(summary: dict[str, Any]) -> bool:
    coverage = summary.get("result_coverage") or {}
    for row in coverage.values():
        if not isinstance(row, dict):
            return False
        if row.get("result_missing_count", 0) > 0 and row.get("hit_rate_policy") not in {
            "EXCLUDES_RESULT_MISSING",
            "NOT_COMPUTED_RESULT_MISSING_OR_EMPTY",
        }:
            return False
    return True


def record_guard(row: dict[str, Any]) -> dict[str, bool]:
    missing = set(row.get("missing_context") or [])
    policy = row.get("policy_lock") or {}
    return {
        "required_fields_present": REQUIRED_FIELDS.issubset(set(row)),
        "conclusion_allowed": row.get("strategy_card_conclusion") in ALLOWED_CONCLUSIONS,
        "price_missing_no_edge": not ("PRICE_MISSING" in missing and row.get("edge_inference") != "NOT_EVALUATED"),
        "line_missing_retained": not ("LINE_MISSING" in missing and row.get("line_status") != "LINE_MISSING"),
        "market_missing_retained": not ("MARKET_MISSING" in missing and row.get("market_status") != "MARKET_MISSING"),
        "result_missing_not_hit": not (
            row.get("replay_status") == "RESULT_MISSING"
            and row.get("result_available") is not False
            and row.get("result_hit") is not None
        ),
        "policy_locked": policy.get("official_grade_changed") is False
        and policy.get("pending_written") is False
        and policy.get("qq_sent") is False
        and policy.get("cron_or_launchd_modified") is False
        and policy.get("b_realtime_restored") is False
        and policy.get("rf_shadow_promotion_released") is False,
    }


def main() -> int:
    builder_proc = subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, capture_output=True, text=True, timeout=240)
    schema = load(SCHEMA) or {}
    ledger = load(LEDGER) or {}
    summary = load(SUMMARY) or {}
    records = ledger.get("records", []) if isinstance(ledger, dict) else []
    text = json.dumps({"ledger": ledger, "summary": summary}, ensure_ascii=False)
    strategy = run_checker(STRATEGY_CHECKER)
    five = run_checker(FIVE_CHECKER)
    main_league = run_checker(MAIN_LEAGUE_CHECKER)
    price = run_checker(PRICE_CHECKER)
    production = run_checker(PRODUCTION_GUARD)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = staged_forbidden(staged)
    record_checks = [record_guard(row) for row in records if isinstance(row, dict)]
    warn_only = set(summary.get("warn_only") or [])

    checks = {
        "schema_exists": SCHEMA.exists(),
        "schema_fields_complete": set(schema.get("record_fields") or []) == REQUIRED_FIELDS,
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder_proc.returncode == 0,
        "ledger_exists": LEDGER.exists(),
        "summary_exists": SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "sample_count_expanded": len(records) > 3,
        "record_guards_pass": all(all(row.values()) for row in record_checks),
        "conclusion_distribution_complete": set((summary.get("conclusion_distribution") or {}).keys()) == ALLOWED_CONCLUSIONS,
        "gap_counts_present": GAP_TAGS.issubset(set(summary.get("missing_context_summary") or {})),
        "result_missing_excluded_from_hit_rate": hit_rate_policy_ok(summary),
        "sample_insufficient_warn_only": (
            summary.get("observe_sample_sufficient") is True
            or "OBSERVE_SAMPLE_INSUFFICIENT" in warn_only
        ),
        "observe_blockers_present": bool(summary.get("observe_blockers")),
        "no_forbidden_terms": FORBIDDEN_TERMS.search(text) is None,
        "no_live_api": ledger.get("live_api_called") is False,
        "policy_lock": all(
            (summary.get("policy_lock") or {}).get(key) is False
            for key in [
                "official_grade_changed",
                "ab_threshold_changed",
                "pending_written",
                "qq_sent",
                "cron_or_launchd_modified",
                "b_realtime_restored",
                "rf_shadow_promotion_released",
                "live_api_called",
            ]
        ),
        "strategy_card_checker_pass": strategy["returncode"] == 0 and strategy.get("payload", {}).get("conclusion") == "PASS",
        "five_dimension_lite_pass": five["returncode"] == 0 and five.get("payload", {}).get("conclusion") == "PASS",
        "main_league_guard_pass": main_league["returncode"] == 0 and main_league.get("payload", {}).get("conclusion") == "PASS",
        "price_persistence_pass": price["returncode"] == 0 and price.get("payload", {}).get("conclusion") == "PASS",
        "production_guard_pass": production["returncode"] == 0 and production.get("payload", {}).get("conclusion") == "PASS",
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_market_strategy_card_replay_expansion_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "sample_count": len(records),
        "conclusion_distribution": summary.get("conclusion_distribution"),
        "missing_context_summary": summary.get("missing_context_summary"),
        "result_coverage": summary.get("result_coverage"),
        "observe_blockers": summary.get("observe_blockers"),
        "warn_only": sorted(warn_only),
        "forbidden_staged": forbidden_staged,
        "official_grade_changed": False,
        "pending_written": False,
        "qq_sent": False,
        "cron_or_launchd_modified": False,
        "b_realtime_restored": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
