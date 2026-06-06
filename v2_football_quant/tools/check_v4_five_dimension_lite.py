#!/usr/bin/env python3
"""Check V4 five-dimension Lite stays a locked observation-only skeleton."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "config/v4_five_dimension_lite_schema.json"
SAMPLES = ROOT / "data/manual_sources/v4/five_dimension_lite/v4_five_dimension_lite_samples_20260607.json"
SUMMARY = ROOT / "data/manual_sources/v4/five_dimension_lite/v4_five_dimension_lite_summary_20260607.json"
BUILDER = ROOT / "tools/build_v4_five_dimension_lite.py"
DOC = ROOT / "docs/V4_FIVE_DIMENSION_LITE_SCHEMA_PACK_20260607.md"
MAIN_LEAGUE_CHECKER = ROOT / "tools/check_v4_main_league_admission_guard.py"
PRICE_CHECKER = ROOT / "tools/check_v4_price_field_persistence_pipeline.py"
SELECTION_CHECKER = ROOT / "tools/check_v4_selection_strategy_redesign_freeze.py"
PRODUCTION_GUARD = ROOT / "tools/check_v4_production_default_rules_guard.py"

DIMENSIONS = {
    "strength_gap",
    "tactical_efficiency",
    "squad_context",
    "market_confirmation",
    "external_risk",
}
ALLOWED_CONCLUSIONS = {"OBSERVE", "WAIT", "PASS"}
REQUIRED_MISSING_TAGS = {
    "PRICE_MISSING",
    "LINE_MISSING",
    "MARKET_MISSING",
    "STANDINGS_MISSING",
    "TEAM_STATS_MISSING",
    "LINEUP_MISSING",
    "LINEUP_WAIT_EVENT",
    "INJURY_SOURCE_MISSING",
    "EXTERNAL_CONTEXT_PENDING",
    "DATA_INSUFFICIENT",
}
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
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=180)
    payload: Any = {}
    text = proc.stdout.strip()
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


def sample_checks(sample: dict[str, Any]) -> dict[str, bool]:
    missing = set(sample.get("missing_context") or [])
    conclusion = (sample.get("conclusion_guard") or {}).get("conclusion")
    market = sample.get("market_confirmation") or {}
    strength = sample.get("strength_gap") or {}
    squad = sample.get("squad_context") or {}
    safety = sample.get("conclusion_guard") or {}
    return {
        "dimensions_present": all(key in sample and isinstance(sample.get(key), dict) for key in DIMENSIONS),
        "missing_context_present": bool(missing),
        "conclusion_allowed": conclusion in ALLOWED_CONCLUSIONS,
        "price_or_line_missing_no_market_pass": not (
            ("PRICE_MISSING" in missing or "LINE_MISSING" in missing) and market.get("status") == "PASS"
        ),
        "market_missing_no_market_pass": not ("MARKET_MISSING" in missing and market.get("status") == "PASS"),
        "standings_team_stats_missing_no_strength_pass": not (
            "STANDINGS_MISSING" in missing and "TEAM_STATS_MISSING" in missing and strength.get("status") == "PASS"
        ),
        "lineup_wait_event": squad.get("lineup_status") == "LINEUP_WAIT_EVENT",
        "injury_missing_marked": squad.get("injury_status") == "INJURY_SOURCE_MISSING",
        "ht_over_not_standalone": market.get("ht_over_standalone_ab_allowed") is False,
        "official_policy_locked": safety.get("official_grade_changed") is False
        and safety.get("pending_written") is False
        and safety.get("qq_sent") is False
        and safety.get("cron_or_launchd_modified") is False
        and safety.get("b_realtime_restored") is False
        and safety.get("rf_shadow_promotion_released") is False,
    }


def main() -> int:
    builder_proc = subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, capture_output=True, text=True, timeout=180)
    schema = load(SCHEMA) or {}
    payload = load(SAMPLES) or {}
    summary = load(SUMMARY) or {}
    samples = payload.get("samples", []) if isinstance(payload, dict) else []
    text = json.dumps(payload, ensure_ascii=False) + "\n" + (DOC.read_text(encoding="utf-8") if DOC.exists() else "")

    main_league = run_checker(MAIN_LEAGUE_CHECKER)
    price = run_checker(PRICE_CHECKER)
    selection = run_checker(SELECTION_CHECKER)
    production = run_checker(PRODUCTION_GUARD)

    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = staged_forbidden(staged)
    per_sample = [sample_checks(sample) for sample in samples]
    observed_missing = set()
    for sample in samples:
        observed_missing.update(sample.get("missing_context") or [])

    checks = {
        "schema_exists": SCHEMA.exists(),
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder_proc.returncode == 0,
        "samples_exist": SAMPLES.exists(),
        "summary_exists": SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "schema_dimensions_complete": set((schema.get("dimensions") or {}).keys()) == DIMENSIONS,
        "schema_missing_tags_complete": set(schema.get("required_missing_tags") or []) == REQUIRED_MISSING_TAGS,
        "sample_count_1_to_3": 1 <= len(samples) <= 3,
        "payload_dimensions_complete": set(payload.get("dimensions_required") or []) == DIMENSIONS,
        "allowed_conclusions_complete": set(payload.get("allowed_conclusions") or []) == ALLOWED_CONCLUSIONS,
        "required_missing_tags_observed": REQUIRED_MISSING_TAGS.issubset(observed_missing),
        "sample_guards_pass": all(all(row.values()) for row in per_sample),
        "summary_conclusions_complete": set((summary.get("conclusion_counts") or {}).keys()) == ALLOWED_CONCLUSIONS,
        "no_forbidden_terms": FORBIDDEN_TERMS.search(text) is None,
        "no_live_api": payload.get("live_api_called") is False,
        "policy_lock": all(
            (payload.get("policy_lock") or {}).get(key) is False
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
        "main_league_guard_pass": main_league["returncode"] == 0 and main_league.get("payload", {}).get("conclusion") == "PASS",
        "price_persistence_pass": price["returncode"] == 0 and price.get("payload", {}).get("conclusion") == "PASS",
        "selection_freeze_pass": selection["returncode"] == 0 and selection.get("payload", {}).get("conclusion") == "PASS",
        "production_guard_pass": production["returncode"] == 0 and production.get("payload", {}).get("conclusion") == "PASS",
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_five_dimension_lite_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "sample_count": len(samples),
        "dimensions": sorted(DIMENSIONS),
        "missing_tags_observed": sorted(observed_missing),
        "conclusion_counts": summary.get("conclusion_counts"),
        "per_sample": per_sample,
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
