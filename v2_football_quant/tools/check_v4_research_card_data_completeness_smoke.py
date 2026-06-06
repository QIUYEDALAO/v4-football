#!/usr/bin/env python3
"""Check V4 research-card data completeness smoke output and safety locks."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "data/runtime/v4_research_card_smoke/v4_research_card_data_completeness_smoke_summary_20260607.json"
SAMPLES = ROOT / "data/runtime/v4_research_card_smoke/v4_research_card_data_completeness_smoke_samples_20260607.json"
RUNNER = ROOT / "tools/run_v4_research_card_data_completeness_smoke.py"
DOC = ROOT / "docs/V4_RESEARCH_CARD_DATA_COMPLETENESS_SMOKE_PACK_20260607.md"
STRATEGY_CHECKER = ROOT / "tools/check_v4_market_strategy_research_cards.py"
FIVE_CHECKER = ROOT / "tools/check_v4_five_dimension_lite.py"
LEAGUE_CHECKER = ROOT / "tools/check_v4_main_league_admission_guard.py"
PRICE_CHECKER = ROOT / "tools/check_v4_price_field_persistence_pipeline.py"
PRODUCTION_GUARD = ROOT / "tools/check_v4_production_default_rules_guard.py"

FORBIDDEN_TERMS = re.compile(
    r"推荐|投注|下注|实单|必中|稳胆|资金流|steam|drift|sharp|betting signal|must bet",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"
)
REQUIRED_COVERAGE_FIELDS = {
    "fixtures",
    "odds",
    "standings",
    "team_statistics",
    "lineups",
    "injuries",
    "h2h",
    "has_1x2",
    "has_ft_ou",
    "has_ah_or_handicap",
    "has_double_chance",
    "line_exists",
    "odds_exists",
}
ALLOWED_CONCLUSIONS = {"OBSERVE", "WAIT", "PASS"}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


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


def main() -> int:
    summary = load(SUMMARY) or {}
    samples_payload = load(SAMPLES) or {}
    samples = samples_payload.get("samples", []) if isinstance(samples_payload, dict) else []
    text = json.dumps({"summary": summary, "samples": samples_payload}, ensure_ascii=False)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    tracked_runtime = [
        path for path in git(["ls-files", "v2_football_quant/data/runtime"]).splitlines()
        if "v4_research_card_smoke" in path
    ]
    strategy = run_checker(STRATEGY_CHECKER)
    five = run_checker(FIVE_CHECKER)
    league = run_checker(LEAGUE_CHECKER)
    price = run_checker(PRICE_CHECKER)
    production = run_checker(PRODUCTION_GUARD)
    conclusion_counts = summary.get("conclusion_counts") or {}
    missing_counts = summary.get("missing_context_counts") or {}
    field_counts = summary.get("field_coverage_counts") or {}
    coverage_keys = set()
    for sample in samples:
        coverage_keys.update((sample.get("field_coverage") or {}).keys())
    sample_checks = []
    for sample in samples:
        coverage = sample.get("field_coverage") or {}
        policy = sample.get("policy_lock") or {}
        conclusion = sample.get("strategy_card_conclusion")
        missing = set(sample.get("missing_context") or [])
        sample_checks.append({
            "coverage_schema_complete": REQUIRED_COVERAGE_FIELDS.issubset(set(coverage)),
            "conclusion_allowed": conclusion in ALLOWED_CONCLUSIONS,
            "price_missing_no_observe_edge": not ("PRICE_MISSING" in missing and conclusion == "OBSERVE"),
            "line_missing_no_observe_edge": not ("LINE_MISSING" in missing and conclusion == "OBSERVE"),
            "market_missing_no_observe_edge": not ("MARKET_MISSING" in missing and conclusion == "OBSERVE"),
            "policy_lock_clean": all(
                policy.get(key) is False
                for key in [
                    "official_grade_changed",
                    "pending_written",
                    "qq_sent",
                    "cron_or_launchd_modified",
                    "b_realtime_restored",
                    "rf_shadow_promotion_released",
                ]
            ),
        })
    policy = summary.get("policy_lock") or {}
    checks = {
        "runner_exists": RUNNER.exists(),
        "doc_exists": DOC.exists(),
        "summary_exists": SUMMARY.exists(),
        "samples_exist": SAMPLES.exists(),
        "runtime_only": samples_payload.get("runtime_only") is True,
        "sample_count_3_to_5": 3 <= int(summary.get("sample_count") or 0) <= 5,
        "field_coverage_schema_complete": REQUIRED_COVERAGE_FIELDS.issubset(coverage_keys),
        "conclusion_distribution_complete": set(conclusion_counts) == ALLOWED_CONCLUSIONS,
        "missing_context_summary_present": isinstance(missing_counts, dict),
        "field_coverage_counts_present": isinstance(field_counts, dict) and bool(field_counts),
        "sample_guards_pass": all(all(row.values()) for row in sample_checks),
        "no_forbidden_terms": FORBIDDEN_TERMS.search(text) is None,
        "no_secret_literals": SECRET_VALUE_RE.search(text) is None,
        "runtime_not_tracked": not tracked_runtime,
        "no_runtime_or_secret_staged": not staged_forbidden(staged),
        "official_policy_locked": all(
            policy.get(key) is False
            for key in [
                "official_grade_changed",
                "ab_threshold_changed",
                "pending_written",
                "qq_sent",
                "cron_or_launchd_modified",
                "b_realtime_restored",
                "rf_shadow_promotion_released",
            ]
        ),
        "not_recommendation": policy.get("not_recommendation") is True,
        "not_betting_advice": policy.get("not_betting_advice") is True,
        "strategy_card_checker_pass": strategy["returncode"] == 0 and strategy.get("payload", {}).get("conclusion") == "PASS",
        "five_dimension_checker_pass": five["returncode"] == 0 and five.get("payload", {}).get("conclusion") == "PASS",
        "main_league_checker_pass": league["returncode"] == 0 and league.get("payload", {}).get("conclusion") == "PASS",
        "price_persistence_checker_pass": price["returncode"] == 0 and price.get("payload", {}).get("conclusion") == "PASS",
        "production_guard_pass": production["returncode"] == 0 and production.get("payload", {}).get("conclusion") == "PASS",
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_research_card_data_completeness_smoke_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "sample_count": summary.get("sample_count"),
        "source_leagues": summary.get("source_leagues"),
        "conclusion_counts": conclusion_counts,
        "missing_context_counts": missing_counts,
        "field_coverage_counts": field_counts,
        "sample_checks": sample_checks,
        "tracked_runtime": tracked_runtime,
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
