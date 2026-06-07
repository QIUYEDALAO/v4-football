#!/usr/bin/env python3
"""Check V4 context positive bucket explanation audit."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parents[3]
BUILDER = DATA_DIR / "build_v4_context_positive_bucket_explanation_audit.py"
CONTEXT_CHECKER = DATA_DIR / "check_v4_context_aware_replay.py"
FEATURE_CHECKER = DATA_DIR / "check_v4_replay_feature_enriched_dataset.py"
NEGATIVE_CHECKER = DATA_DIR / "check_v4_price_aware_negative_findings.py"
OUT_JSON = DATA_DIR / "processed/v4_context_positive_bucket_explanation_audit.json"
OUT_MD = DATA_DIR / "processed/v4_context_positive_bucket_explanation_audit.md"
DOC = DATA_DIR / "V4_CONTEXT_POSITIVE_BUCKET_EXPLANATION_AUDIT.md"
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


def text_without_policy_keys(data: dict[str, Any]) -> str:
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("recommendation_generated", "").replace("edge_claim_generated", "")


def main() -> int:
    builder = run_py(BUILDER)
    context = run_py(CONTEXT_CHECKER)
    feature = run_py(FEATURE_CHECKER)
    negative = run_py(NEGATIVE_CHECKER)
    data = load_json(OUT_JSON)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    text = text_without_policy_keys(data)
    for path in [OUT_MD, DOC]:
        if path.exists():
            text += path.read_text(encoding="utf-8").replace("recommendation_generated", "").replace("edge_claim_generated", "")
    audited = data.get("audited_buckets") or []
    policy = data.get("policy_lock") or {}
    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder.returncode == 0,
        "context_checker_pass": context.returncode == 0,
        "feature_checker_pass": feature.returncode == 0,
        "negative_checker_pass": negative.returncode == 0,
        "json_exists": OUT_JSON.exists(),
        "md_exists": OUT_MD.exists(),
        "doc_exists": DOC.exists(),
        "context_bucket_count_85": data.get("context_bucket_count") == 85,
        "positive_exactly_2": data.get("positive_roi_bucket_count") == 2 and len(audited) == 2,
        "research_candidate_zero": data.get("research_candidate_count") == 0,
        "markets_only_ft_ah": set(data.get("markets") or []) == {"ASIAN_HANDICAP", "FT_OVER25"},
        "risk_flags_present": all(bucket.get("risk_flags") for bucket in audited),
        "classification_present": all(
            any(flag in bucket.get("risk_flags", []) for flag in ["SINGLE_CLUSTER_RISK", "EARLY_SEASON_RISK", "NOT_HIGH_CONFIDENCE", "STRUCTURAL_NOISE"])
            for bucket in audited
        ),
        "required_fields_present": all(
            all(field in bucket for field in [
                "market",
                "context_filter",
                "sample_count",
                "hit_rate",
                "avg_close_odds",
                "roi_proxy_flat_1u",
                "max_fail_streak",
                "max_drawdown_proxy",
                "confidence_flag",
                "league_distribution",
                "season_distribution",
                "early_season_share",
                "price_move_direction",
                "strength_context",
                "risk_flags",
            ])
            for bucket in audited
        ),
        "no_online_action": all(bucket.get("online_policy") == "NO_ONLINE_ACTION_RESEARCH_ONLY" for bucket in audited),
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
        "schema_version": "v4_context_positive_bucket_explanation_audit_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "audited_bucket_count": len(audited),
        "classification_summary": data.get("classification_summary"),
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
