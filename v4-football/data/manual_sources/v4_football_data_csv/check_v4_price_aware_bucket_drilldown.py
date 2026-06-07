#!/usr/bin/env python3
"""Check V4 Football-Data price-aware bucket drilldown outputs."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parents[3]
BUILDER = DATA_DIR / "build_v4_price_aware_bucket_drilldown.py"
BUCKET_CHECKER = DATA_DIR / "check_v4_price_aware_bucket_analysis.py"
CORE_CHECKER = DATA_DIR / "check_v4_price_aware_replay_core.py"
DATASET_CHECKER = DATA_DIR / "check_v4_football_data_replay_dataset.py"
OUT_JSON = DATA_DIR / "processed/v4_price_aware_bucket_drilldown.json"
OUT_MD = DATA_DIR / "processed/v4_price_aware_bucket_drilldown.md"
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
    bucket = run_py(BUCKET_CHECKER)
    core = run_py(CORE_CHECKER)
    dataset = run_py(DATASET_CHECKER)
    data = load_json(OUT_JSON)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    text = json.dumps(data, ensure_ascii=False)
    if OUT_MD.exists():
        text += OUT_MD.read_text(encoding="utf-8")
    candidates = data.get("candidates") or []
    watchlist = data.get("watchlist") or []
    dc_policy = data.get("double_chance_policy") or {}
    policy = data.get("policy_lock") or {}
    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder.returncode == 0,
        "bucket_checker_pass": bucket.returncode == 0,
        "core_checker_pass": core.returncode == 0,
        "dataset_checker_pass": dataset.returncode == 0,
        "json_exists": OUT_JSON.exists(),
        "md_exists": OUT_MD.exists(),
        "input_bucket_rows_2683": data.get("input_bucket_rows") == 2683,
        "confidence_counts_expected": data.get("input_confidence_counts") == {
            "LOW_CONFIDENCE": 143,
            "MEDIUM_CONFIDENCE": 135,
            "SMALL_SAMPLE": 2405,
        },
        "source_top_research_candidates_zero": data.get("source_top_research_candidates_count") == 0,
        "small_sample_not_candidate": all(row.get("confidence_flag") != "SMALL_SAMPLE" for row in candidates),
        "low_confidence_not_candidate": all(row.get("confidence_flag") != "LOW_CONFIDENCE" for row in candidates),
        "candidate_sample_min_300": all(int(row.get("sample_count", 0)) >= 300 for row in candidates),
        "candidate_no_high_drawdown": all("HIGH_DRAWDOWN_RISK" not in row.get("risk_flags", []) for row in candidates),
        "candidate_primary_markets_only": all(row.get("market") in {"ASIAN_HANDICAP", "FT_OVER25"} for row in candidates),
        "watchlist_not_candidate": all(row.get("status") == "WATCHLIST_ONLY" for row in watchlist),
        "dc_proxy_no_roi": dc_policy.get("roi_proxy_flat_1u") is None
        and dc_policy.get("reason") == "NO_REAL_DC_ODDS",
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
        "schema_version": "v4_price_aware_bucket_drilldown_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "candidate_count": len(candidates),
        "watchlist_count": len(watchlist),
        "exclusion_counts": data.get("exclusion_counts"),
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
