#!/usr/bin/env python3
"""Check V4 context-aware replay outputs."""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parents[3]
BUILDER = DATA_DIR / "build_v4_context_aware_replay.py"
FEATURE_CHECKER = DATA_DIR / "check_v4_replay_feature_enriched_dataset.py"
NEGATIVE_CHECKER = DATA_DIR / "check_v4_price_aware_negative_findings.py"
CORE_CHECKER = DATA_DIR / "check_v4_price_aware_replay_core.py"
OUT_CSV = DATA_DIR / "processed/v4_context_aware_replay.csv"
OUT_SUMMARY = DATA_DIR / "processed/v4_context_aware_replay_summary.json"
DOC = DATA_DIR / "V4_CONTEXT_AWARE_REPLAY.md"
FORBIDDEN_TEXT = re.compile(
    r"推荐|投注建议|下注|实单|必中|稳胆|must bet|betting advice|steam|sharp|fund[-_ ]?flow",
    re.IGNORECASE,
)
EXPECTED_FILTERS = {
    "strength_gap_bucket",
    "recent_5_points_gap_bucket",
    "over25_close_implied_prob_bucket",
    "odds_over25_move_direction",
    "early_season_status",
    "league_code",
    "season",
    "rank_gap_bucket",
    "points_gap_bucket",
    "ah_home_close_implied_prob_bucket",
    "ah_move_direction",
    "asian_handicap_line_bucket",
    "home_away_side",
}


def run_py(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> int:
    builder = run_py(BUILDER)
    feature = run_py(FEATURE_CHECKER)
    negative = run_py(NEGATIVE_CHECKER)
    core = run_py(CORE_CHECKER)
    rows = read_csv(OUT_CSV)
    summary = load_json(OUT_SUMMARY)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    text = json.dumps(summary, ensure_ascii=False)
    if DOC.exists():
        text += DOC.read_text(encoding="utf-8")
    markets = {row.get("market") for row in rows}
    candidates = summary.get("research_candidates") or []
    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder.returncode == 0,
        "feature_checker_pass": feature.returncode == 0,
        "negative_checker_pass": negative.returncode == 0,
        "core_checker_pass": core.returncode == 0,
        "csv_exists": OUT_CSV.exists(),
        "summary_exists": OUT_SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "no_2025_26": "2025/26" not in set(summary.get("seasons") or []),
        "markets_only_ft_ah": markets == {"ASIAN_HANDICAP", "FT_OVER25"}
        and set(summary.get("markets") or []) == {"ASIAN_HANDICAP", "FT_OVER25"},
        "context_filters_complete": EXPECTED_FILTERS.issubset(set(summary.get("context_filters") or [])),
        "small_sample_not_candidate": all(int(row.get("sample_count", 0)) >= 300 for row in candidates)
        and all(row.get("confidence_flag") != "SMALL_SAMPLE" for row in candidates),
        "early_season_not_main_candidate": all(
            not (
                row.get("context_filter") == "early_season_status"
                and row.get("context_value") == "EARLY_SEASON_INSUFFICIENT"
            )
            for row in candidates
        ),
        "positive_roi_research_only": all(
            "POSITIVE_ROI_RESEARCH_ONLY" in row.get("risk_flags", "")
            for row in rows
            if row.get("roi_proxy_flat_1u") not in {"", None} and float(row["roi_proxy_flat_1u"]) > 0
        ),
        "no_forbidden_text": FORBIDDEN_TEXT.search(text) is None,
        "policy_lock": summary.get("policy_lock", {}).get("api_football_called") is False
        and summary.get("policy_lock", {}).get("v4_scan_executed") is False
        and summary.get("policy_lock", {}).get("official_grade_changed") is False
        and summary.get("policy_lock", {}).get("pending_written") is False
        and summary.get("policy_lock", {}).get("qq_sent") is False
        and summary.get("policy_lock", {}).get("cron_or_launchd_modified") is False
        and summary.get("policy_lock", {}).get("recommendation_generated") is False
        and summary.get("policy_lock", {}).get("edge_claim_generated") is False,
        "no_runtime_cache_log_secret_staged": not staged_forbidden(staged),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_context_aware_replay_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "context_bucket_count": len(rows),
        "confidence_counts": summary.get("confidence_counts"),
        "research_candidate_count": summary.get("research_candidate_count"),
        "risk_summary": summary.get("risk_summary"),
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
