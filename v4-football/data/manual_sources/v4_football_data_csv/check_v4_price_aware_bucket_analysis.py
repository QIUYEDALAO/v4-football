#!/usr/bin/env python3
"""Check V4 Football-Data price-aware bucket analysis outputs."""
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
BUILDER = DATA_DIR / "build_v4_price_aware_bucket_analysis.py"
CORE_CHECKER = DATA_DIR / "check_v4_price_aware_replay_core.py"
DATASET_CHECKER = DATA_DIR / "check_v4_football_data_replay_dataset.py"
LEDGER = DATA_DIR / "processed/v4_price_aware_replay_core_ledger.csv"
OUT_CSV = DATA_DIR / "processed/v4_price_aware_bucket_analysis.csv"
OUT_SUMMARY = DATA_DIR / "processed/v4_price_aware_bucket_summary.json"
DOC = DATA_DIR / "V4_FOOTBALL_DATA_PRICE_AWARE_BUCKET_ANALYSIS.md"

EXPECTED_MARKETS = {
    "FT_OVER25": 15448,
    "1X2": 46344,
    "ASIAN_HANDICAP": 30896,
    "DOUBLE_CHANCE_PROXY": 46344,
}
EXPECTED_COLUMNS = [
    "market",
    "league_code",
    "season",
    "close_odds_band",
    "asian_handicap_line_bucket",
    "over25_price_band",
    "home_away_side",
    "sample_size_bucket",
    "sample_count",
    "settled_count",
    "hit_count",
    "hit_rate",
    "avg_close_odds",
    "roi_proxy_flat_1u",
    "max_fail_streak",
    "max_drawdown_proxy",
    "price_missing_count",
    "settlement_uncertain_count",
    "confidence_flag",
    "risk_flags",
]
FORBIDDEN_TEXT = re.compile(
    r"推荐|投注建议|下注|实单|必中|稳胆|must bet|betting advice",
    re.IGNORECASE,
)


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


def expected_confidence(sample_count: int) -> str:
    if sample_count < 100:
        return "SMALL_SAMPLE"
    if sample_count < 300:
        return "LOW_CONFIDENCE"
    if sample_count < 1000:
        return "MEDIUM_CONFIDENCE"
    return "HIGH_CONFIDENCE"


def is_positive(value: str) -> bool:
    if value == "":
        return False
    try:
        return float(value) > 0
    except ValueError:
        return False


def main() -> int:
    builder = run_py(BUILDER)
    core = run_py(CORE_CHECKER)
    dataset = run_py(DATASET_CHECKER)
    rows = read_csv(OUT_CSV)
    ledger = read_csv(LEDGER)
    summary = load_json(OUT_SUMMARY)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    doc_text = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    summary_text = json.dumps(summary, ensure_ascii=False)
    markets = {market: 0 for market in EXPECTED_MARKETS}
    for row in ledger:
        markets[row.get("market", "")] = markets.get(row.get("market", ""), 0) + 1

    confidence_ok = True
    small_sample_ok = True
    double_chance_ok = True
    no_recommendation_flags = True
    for row in rows:
        sample_count = int(row["sample_count"])
        if row["confidence_flag"] != expected_confidence(sample_count):
            confidence_ok = False
        if sample_count < 100 and "SMALL_SAMPLE_NO_EDGE_CLAIM" not in row["risk_flags"]:
            small_sample_ok = False
        if row["market"] == "DOUBLE_CHANCE_PROXY":
            if row["roi_proxy_flat_1u"] != "" or row["max_drawdown_proxy"] != "":
                double_chance_ok = False
            if "NO_REAL_DC_ODDS" not in row["risk_flags"]:
                double_chance_ok = False
        if "EDGE" in row["risk_flags"] and "NO_EDGE_CLAIM" not in row["risk_flags"]:
            no_recommendation_flags = False

    roi_real_close_only = all(
        row.get("price_status") == "REAL_CLOSE_ODDS"
        for row in ledger
        if row.get("pnl_proxy_flat_1u")
    )
    seasons = {row.get("season") for row in ledger}
    policy = summary.get("policy_lock") or {}
    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder.returncode == 0,
        "core_checker_pass": core.returncode == 0,
        "dataset_checker_pass": dataset.returncode == 0,
        "bucket_csv_exists": OUT_CSV.exists(),
        "bucket_summary_exists": OUT_SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "columns_complete": bool(rows) and list(rows[0].keys()) == EXPECTED_COLUMNS,
        "expected_market_counts": markets == EXPECTED_MARKETS,
        "no_2025_26": "2025/26" not in seasons,
        "bucket_dimensions_complete": set(summary.get("bucket_dimensions") or []) == {
            "market",
            "league_code",
            "season",
            "close_odds_band",
            "asian_handicap_line_bucket",
            "over25_price_band",
            "home_away_side",
            "sample_size_bucket",
        },
        "bucket_rows_present": len(rows) > 0 and summary.get("bucket_rows") == len(rows),
        "confidence_rules": confidence_ok,
        "small_sample_no_edge_claim": small_sample_ok,
        "double_chance_proxy_no_roi": double_chance_ok,
        "roi_real_close_only": roi_real_close_only,
        "positive_roi_not_edge_claim": no_recommendation_flags,
        "top_candidates_not_small_sample": all(
            row.get("confidence_flag") in {"MEDIUM_CONFIDENCE", "HIGH_CONFIDENCE"}
            and int(row.get("sample_count", 0)) >= 300
            for row in summary.get("top_research_candidates", [])
        ),
        "no_forbidden_text": FORBIDDEN_TEXT.search(doc_text + summary_text) is None,
        "policy_lock": policy.get("api_football_called") is False
        and policy.get("v4_scan_executed") is False
        and policy.get("official_grade_changed") is False
        and policy.get("pending_written") is False
        and policy.get("qq_sent") is False
        and policy.get("cron_or_launchd_modified") is False
        and policy.get("strategy_online") is False
        and policy.get("recommendation_generated") is False
        and policy.get("edge_claim_generated") is False,
        "no_runtime_cache_log_secret_staged": not staged_forbidden(staged),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_price_aware_bucket_analysis_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "bucket_rows": len(rows),
        "market_counts": markets,
        "confidence_counts": summary.get("confidence_counts"),
        "positive_roi_bucket_count": summary.get("positive_roi_bucket_count"),
        "positive_roi_high_drawdown_risk_count": summary.get("positive_roi_high_drawdown_risk_count"),
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
