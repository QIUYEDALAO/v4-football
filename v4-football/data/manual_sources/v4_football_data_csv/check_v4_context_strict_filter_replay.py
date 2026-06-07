#!/usr/bin/env python3
"""Check V4 strict-filter context replay outputs."""
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
BUILDER = DATA_DIR / "build_v4_context_strict_filter_replay.py"
AUDIT_CHECKER = DATA_DIR / "check_v4_context_positive_bucket_explanation_audit.py"
CONTEXT_CHECKER = DATA_DIR / "check_v4_context_aware_replay.py"
FEATURE_CHECKER = DATA_DIR / "check_v4_replay_feature_enriched_dataset.py"
OUT_CSV = DATA_DIR / "processed/v4_context_strict_filter_replay.csv"
OUT_SUMMARY = DATA_DIR / "processed/v4_context_strict_filter_replay_summary.json"
DOC = DATA_DIR / "V4_CONTEXT_STRICT_FILTER_REPLAY.md"
FORBIDDEN_TEXT = re.compile(
    r"推荐|投注建议|下注|实单|必中|稳胆|must bet|betting advice|recommend|bet\\b",
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


def scrub_policy_text(text: str) -> str:
    return text.replace("recommendation_generated", "").replace("edge_claim_generated", "")


def main() -> int:
    builder = run_py(BUILDER)
    audit = run_py(AUDIT_CHECKER)
    context = run_py(CONTEXT_CHECKER)
    feature = run_py(FEATURE_CHECKER)
    rows = read_csv(OUT_CSV)
    summary = load_json(OUT_SUMMARY)
    candidates = summary.get("research_candidates") or []
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    text = scrub_policy_text(json.dumps(summary, ensure_ascii=False))
    if DOC.exists():
        text += scrub_policy_text(DOC.read_text(encoding="utf-8"))
    policy = summary.get("policy_lock") or {}
    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder.returncode == 0,
        "audit_checker_pass": audit.returncode == 0,
        "context_checker_pass": context.returncode == 0,
        "feature_checker_pass": feature.returncode == 0,
        "csv_exists": OUT_CSV.exists(),
        "summary_exists": OUT_SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "source_positive_buckets_confirmed": summary.get("positive_bucket_audit", {}).get("positive_roi_bucket_count") == 2
        and summary.get("positive_bucket_audit", {}).get("research_candidate_count") == 0,
        "markets_only_ft_ah": set(summary.get("markets") or []) == {"ASIAN_HANDICAP", "FT_OVER25"}
        and {row.get("market") for row in rows} == {"ASIAN_HANDICAP", "FT_OVER25"},
        "small_sample_not_candidate": all(int(row.get("sample_count", 0)) >= 300 for row in candidates),
        "early_season_excluded": "EARLY_SEASON_INSUFFICIENT" in summary.get("row_excluded_reason_counts", {}),
        "single_cluster_not_candidate": all("SINGLE_CLUSTER_RISK" not in row.get("excluded_reason", "") for row in candidates),
        "low_confidence_not_candidate": all(row.get("confidence_flag") == "HIGH_CONFIDENCE" for row in candidates),
        "missing_price_line_excluded": any(
            key in summary.get("row_excluded_reason_counts", {})
            for key in ["FT_OVER25_PRICE_MOVEMENT_MISSING", "AH_HOME_PRICE_MOVEMENT_MISSING", "AH_AWAY_PRICE_MOVEMENT_MISSING", "AH_LINE_MISSING"]
        ),
        "no_forbidden_text": FORBIDDEN_TEXT.search(text) is None,
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
        "schema_version": "v4_context_strict_filter_replay_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "total_buckets_after_filter": summary.get("total_buckets_after_filter"),
        "positive_roi_buckets_after_filter": summary.get("positive_roi_buckets_after_filter"),
        "research_candidate_count": summary.get("research_candidate_count"),
        "row_excluded_reason_counts": summary.get("row_excluded_reason_counts"),
        "bucket_excluded_reason_counts": summary.get("bucket_excluded_reason_counts"),
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
