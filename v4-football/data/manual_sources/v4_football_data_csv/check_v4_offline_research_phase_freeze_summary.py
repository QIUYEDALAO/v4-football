#!/usr/bin/env python3
"""Check V4 offline research phase freeze summary.

This checker is read-only. It does not call api-football, run scan, send QQ,
change official grades, write pending candidates, or touch cron/launchd.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "v4-football/data/manual_sources/v4_football_data_csv"
PROCESSED = BASE / "processed"
DOC = BASE / "V4_OFFLINE_RESEARCH_PHASE_FREEZE_SUMMARY.md"
SUMMARY = PROCESSED / "v4_offline_research_phase_freeze_summary.json"
CORE = PROCESSED / "v4_price_aware_replay_core_summary.json"
BUCKET = PROCESSED / "v4_price_aware_bucket_summary.json"
DRILLDOWN = PROCESSED / "v4_price_aware_bucket_drilldown.json"
CONTEXT = PROCESSED / "v4_context_aware_replay_summary.json"
POSITIVE = PROCESSED / "v4_context_positive_bucket_explanation_audit.json"
NEGATIVE = PROCESSED / "v4_price_aware_negative_findings_next_feature_plan.json"

ALLOWED_POLICY_LITERAL = "RESEARCH_ONLY_NOT_EDGE"
FORBIDDEN_PHRASES = [
    "上线策略",
    "恢复扫描",
    "恢复QQ",
    "恢复 official",
    "写入pending",
    "投注建议",
    "下注",
    "实单",
    "稳赚",
    "必中",
]


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def approx(actual: float | None, expected: float, tolerance: float = 0.0002) -> bool:
    return actual is not None and math.isclose(float(actual), expected, abs_tol=tolerance)


def int_eq(value, expected: int) -> bool:
    try:
        return int(value) == expected
    except Exception:
        return False


def metric_by_market(core: dict) -> dict[str, dict]:
    return {str(row.get("market")): row for row in core.get("metrics", []) if isinstance(row, dict)}


def no_forbidden_positive_language(text: str) -> bool:
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            return False
    scrubbed = text.replace(ALLOWED_POLICY_LITERAL, "")
    if re.search(r"(?i)(recommendation[^_]|recommend[^a-z_]|betting[^_]|bet[^a-z_]|edge claim|go online|production candidate)", scrubbed):
        return False
    return True


def no_forbidden_staged() -> tuple[bool, list[str], int]:
    cp = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    staged = [line.strip() for line in cp.stdout.splitlines() if line.strip()]
    bad = [
        path
        for path in staged
        if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)
        or re.search(r"(^|/)(\.env|.*\.env|.*\.key|.*secret.*|.*token.*)(/|$)", path, re.I)
    ]
    diff = subprocess.run(
        ["git", "diff", "--cached"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    ).stdout
    added_diff = "\n".join(
        line for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    sensitive_name_re = "api[_-]?" + "key" + "|" + "token" + "|" + "secret"
    sensitive_assign_re = r"(?i)(" + sensitive_name_re + r")\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"
    secret_hits = len(re.findall(sensitive_assign_re, added_diff))
    return (not bad and secret_hits == 0), bad, secret_hits


def main() -> int:
    core = load_json(CORE)
    bucket = load_json(BUCKET)
    drilldown = load_json(DRILLDOWN)
    context = load_json(CONTEXT)
    positive = load_json(POSITIVE)
    negative = load_json(NEGATIVE)
    summary = load_json(SUMMARY)
    doc_text = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    summary_text = json.dumps(summary, ensure_ascii=False)
    metrics = metric_by_market(core)
    stop = summary.get("stop_line", {})
    frozen = summary.get("frozen_findings", {})
    ctx = summary.get("context_findings", {})
    no_bad_staged, staged_bad_paths, secret_hits = no_forbidden_staged()

    checks = {
        "summary_exists": SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "source_artifacts_exist": all(path.exists() for path in [CORE, BUCKET, DRILLDOWN, CONTEXT, POSITIVE, NEGATIVE]),
        "ft_over_roi": approx(metrics.get("FT_OVER25", {}).get("roi_proxy_flat_1u"), -0.0471),
        "one_x_two_roi": approx(metrics.get("1X2", {}).get("roi_proxy_flat_1u"), -0.08),
        "ah_roi": approx(metrics.get("ASIAN_HANDICAP", {}).get("roi_proxy_flat_1u"), -0.0245),
        "dc_proxy_no_roi": metrics.get("DOUBLE_CHANCE_PROXY", {}).get("roi_proxy_flat_1u") is None,
        "bucket_counts": (
            int(bucket.get("bucket_rows") or 0) == 2683
            and int((bucket.get("confidence_counts") or {}).get("MEDIUM_CONFIDENCE") or 0) == 135
            and int((bucket.get("confidence_counts") or {}).get("LOW_CONFIDENCE") or 0) == 143
            and int((bucket.get("confidence_counts") or {}).get("SMALL_SAMPLE") or 0) == 2405
        ),
        "high_confidence_zero": int_eq((summary.get("bucket_findings") or {}).get("HIGH_CONFIDENCE"), 0),
        "drilldown_candidates_zero": len(drilldown.get("candidates") or []) == 0,
        "context_positive_two": int(context.get("positive_roi_bucket_count") or 0) == 2,
        "positive_audit_two": int(positive.get("positive_roi_bucket_count") or 0) == 2
        and len(positive.get("audited_buckets") or []) == 2,
        "research_candidate_zero": (
            int_eq(stop.get("research_candidate_count"), 0)
            and int_eq(context.get("research_candidate_count"), 0)
            and int_eq(positive.get("research_candidate_count"), 0)
            and int_eq((negative.get("bucket_findings") or {}).get("research_candidate"), 0)
        ),
        "cannot_online_true": stop.get("cannot_online") is True,
        "restore_scan_false": stop.get("restore_scan_allowed") is False,
        "restore_qq_false": stop.get("restore_qq_allowed") is False,
        "official_change_false": stop.get("official_change_allowed") is False,
        "pending_cron_false": stop.get("pending_write_allowed") is False
        and stop.get("cron_or_launchd_change_allowed") is False,
        "small_sample_policy_research_only": stop.get("small_sample_positive_roi_policy") == ALLOWED_POLICY_LITERAL
        and ctx.get("positive_bucket_policy") == ALLOWED_POLICY_LITERAL,
        "market_decisions_frozen": all(
            market in frozen for market in ["FT_OVER25", "1X2", "ASIAN_HANDICAP", "DOUBLE_CHANCE_PROXY"]
        ),
        "allowed_next_actions": set(summary.get("allowed_next_actions") or []) == {
            "ADD_CONTEXT_VARIABLES",
            "EXPAND_REPLAY_DATA_SOURCE",
            "REDESIGN_RESEARCH_HYPOTHESIS",
        },
        "policy_lock": all(
            summary.get("policy_lock", {}).get(key) is expected
            for key, expected in {
                "api_football_called": False,
                "v4_scan_executed": False,
                "official_grade_changed": False,
                "pending_written": False,
                "qq_sent": False,
                "cron_or_launchd_modified": False,
                "strategy_online": False,
                "recommendation_generated": False,
                "edge_claim_generated": False,
            }.items()
        ),
        "no_forbidden_text": no_forbidden_positive_language(doc_text + "\n" + summary_text),
        "no_runtime_cache_log_secret_staged": no_bad_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_offline_research_phase_freeze_summary_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "frozen_findings": {
            "FT_OVER25_ROI": round(metrics.get("FT_OVER25", {}).get("roi_proxy_flat_1u", 0), 4),
            "1X2_ROI": round(metrics.get("1X2", {}).get("roi_proxy_flat_1u", 0), 4),
            "ASIAN_HANDICAP_ROI": round(metrics.get("ASIAN_HANDICAP", {}).get("roi_proxy_flat_1u", 0), 4),
            "HIGH_CONFIDENCE": (summary.get("bucket_findings") or {}).get("HIGH_CONFIDENCE"),
            "research_candidate_count": stop.get("research_candidate_count"),
            "positive_roi_bucket_count": ctx.get("positive_roi_bucket_count"),
        },
        "stop_line": stop,
        "allowed_next_actions": summary.get("allowed_next_actions"),
        "forbidden_staged_paths": staged_bad_paths,
        "secret_literal_hit_count": secret_hits,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
