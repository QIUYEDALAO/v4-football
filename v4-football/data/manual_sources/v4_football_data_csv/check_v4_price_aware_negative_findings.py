#!/usr/bin/env python3
"""Check V4 price-aware negative findings and next feature plan."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parents[3]
CORE_SUMMARY = DATA_DIR / "processed/v4_price_aware_replay_core_summary.json"
BUCKET_SUMMARY = DATA_DIR / "processed/v4_price_aware_bucket_summary.json"
DRILLDOWN = DATA_DIR / "processed/v4_price_aware_bucket_drilldown.json"
PLAN_JSON = DATA_DIR / "processed/v4_price_aware_negative_findings_next_feature_plan.json"
PLAN_DOC = DATA_DIR / "V4_PRICE_AWARE_REPLAY_NEGATIVE_FINDINGS_AND_NEXT_FEATURE_PLAN.md"
DRILLDOWN_CHECKER = DATA_DIR / "check_v4_price_aware_bucket_drilldown.py"
BUCKET_CHECKER = DATA_DIR / "check_v4_price_aware_bucket_analysis.py"
CORE_CHECKER = DATA_DIR / "check_v4_price_aware_replay_core.py"
FORBIDDEN_TEXT = re.compile(
    r"推荐|投注建议|下注|实单|必中|稳胆|must bet|betting advice",
    re.IGNORECASE,
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_py(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def staged_forbidden(staged: list[str]) -> list[str]:
    bad: list[str] = []
    for path in staged:
        lower = path.lower()
        if re.search(r"(^|/)(runtime|cache|logs?|secrets?)(/|$)", lower):
            bad.append(path)
        if re.search(r"(^|/)(\\.env|.*\\.env|.*\\.key|.*token.*)(/|$)", lower):
            bad.append(path)
    return sorted(set(bad))


def market_metrics(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["market"]: row for row in summary.get("metrics", []) if isinstance(row, dict)}


def close(actual: Any, expected: float, tolerance: float = 0.0001) -> bool:
    try:
        return abs(float(actual) - expected) <= tolerance
    except (TypeError, ValueError):
        return False


def main() -> int:
    core = load_json(CORE_SUMMARY)
    bucket = load_json(BUCKET_SUMMARY)
    drilldown = load_json(DRILLDOWN)
    plan = load_json(PLAN_JSON)
    metrics = market_metrics(core)
    market_plan = plan.get("market_metrics") or {}
    policy = plan.get("policy_lock") or {}
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    text = json.dumps(plan, ensure_ascii=False)
    if PLAN_DOC.exists():
        text += PLAN_DOC.read_text(encoding="utf-8")
    drilldown_checker = run_py(DRILLDOWN_CHECKER)
    bucket_checker = run_py(BUCKET_CHECKER)
    core_checker = run_py(CORE_CHECKER)
    checks = {
        "source_files_exist": CORE_SUMMARY.exists()
        and BUCKET_SUMMARY.exists()
        and DRILLDOWN.exists()
        and PLAN_JSON.exists()
        and PLAN_DOC.exists(),
        "drilldown_checker_pass": drilldown_checker.returncode == 0,
        "bucket_checker_pass": bucket_checker.returncode == 0,
        "core_checker_pass": core_checker.returncode == 0,
        "ft_over_roi": close(metrics.get("FT_OVER25", {}).get("roi_proxy_flat_1u"), -0.0471),
        "one_x_two_roi": close(metrics.get("1X2", {}).get("roi_proxy_flat_1u"), -0.0800),
        "ah_roi": close(metrics.get("ASIAN_HANDICAP", {}).get("roi_proxy_flat_1u"), -0.0245),
        "dc_proxy_no_roi": metrics.get("DOUBLE_CHANCE_PROXY", {}).get("roi_proxy_flat_1u") is None
        and market_plan.get("DOUBLE_CHANCE_PROXY", {}).get("roi_proxy_flat_1u") is None,
        "bucket_counts": bucket.get("bucket_rows") == 2683
        and bucket.get("confidence_counts", {}).get("MEDIUM_CONFIDENCE") == 135
        and bucket.get("confidence_counts", {}).get("LOW_CONFIDENCE") == 143
        and bucket.get("confidence_counts", {}).get("SMALL_SAMPLE") == 2405
        and bucket.get("confidence_counts", {}).get("HIGH_CONFIDENCE", 0) == 0,
        "research_candidate_zero": len(drilldown.get("candidates") or []) == 0
        and plan.get("bucket_findings", {}).get("research_candidate") == 0,
        "watchlist_not_edge": plan.get("bucket_findings", {}).get("low_confidence_watchlist") == 13
        and policy.get("edge_claim_generated") is False,
        "cannot_online": policy.get("cannot_online") is True and policy.get("strategy_online") is False,
        "one_x_two_auxiliary": market_plan.get("1X2", {}).get("decision") == "AUXILIARY_ONLY_DOWNGRADED",
        "ft_over_research_only": market_plan.get("FT_OVER25", {}).get("decision")
        == "RESEARCH_CONTINUE_NEEDS_ATTACK_DEFENSE_TEMPO_CONTEXT",
        "ah_research_only": market_plan.get("ASIAN_HANDICAP", {}).get("decision")
        == "RESEARCH_CONTINUE_NEEDS_STRENGTH_PRICE_AND_SCHEDULE_CONTEXT",
        "next_features_complete": [item.get("feature_group") for item in plan.get("next_feature_plan", [])] == [
            "team_strength_context",
            "price_movement_context",
            "tactical_stat_context",
            "fatigue_context",
            "exclusion_filters",
        ],
        "no_forbidden_text": FORBIDDEN_TEXT.search(text) is None,
        "policy_lock": policy.get("api_football_called") is False
        and policy.get("v4_scan_executed") is False
        and policy.get("official_grade_changed") is False
        and policy.get("pending_written") is False
        and policy.get("qq_sent") is False
        and policy.get("cron_or_launchd_modified") is False
        and policy.get("recommendation_generated") is False,
        "no_runtime_cache_log_secret_staged": not staged_forbidden(staged),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_price_aware_negative_findings_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "market_decisions": {
            market: data.get("decision")
            for market, data in market_plan.items()
        },
        "bucket_findings": plan.get("bucket_findings"),
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
