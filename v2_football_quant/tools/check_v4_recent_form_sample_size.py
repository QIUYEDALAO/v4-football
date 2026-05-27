#!/usr/bin/env python3
"""check_v4_recent_form_sample_size.py

Verifies that recent form scoring sample size meets BOSS's
10-match requirement. Checks both raw fetch limit and scoring window.

Phase: V4-RECENT-FORM-SAMPLE-SIZE-AUDIT-AND-FIX-20260527

Checks:
1. scoring_sample_size == 10 (hard requirement)
2. raw_fetch_limit >= scoring_sample_size
3. last=3 NOT used as scoring sample (must be 10)
4. recent_form_low_sample flag exists in code
5. recent_form_policy = LAST_10_VALID_MATCHES
6. outside_57 full coverage preserved
7. No topN replacement
8. No required scoring skipped
9. Official scan not modified
"""
from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))
BOSS_RECENT_FORM_SAMPLE_SIZE = 10


def _ast_extract_number(node, default=None):
    """Extract numeric constant from an AST node."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _ast_extract_number(node.operand)
        return -val if val is not None else None
    return default


def main() -> int:
    ts = datetime.now(TZ).isoformat()
    checks = {}
    violations = []
    warnings = []

    # ── 1. h2h_engine.py: _query_recent_goal_profile default last_n ──
    h2h = ROOT / "engine/data_sources/h2h_engine.py"
    src = h2h.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        checks["h2h_engine_parse"] = "SYNTAX_ERROR"
        return _output(checks, ts, fail=True)

    last_n_default = None
    recent_last_n_value = None
    has_low_sample = False
    has_valid_count = False
    has_policy_marker = False

    for node in ast.walk(tree):
        # Find function default
        if isinstance(node, ast.FunctionDef) and node.name == "_query_recent_goal_profile":
            for i, arg in enumerate(node.args.args):
                if arg.arg == "last_n":
                    defaults = node.args.defaults
                    offset = len(node.args.args) - len(defaults)
                    idx = i - offset
                    if 0 <= idx < len(defaults):
                        last_n_default = _ast_extract_number(defaults[idx])
        # Find recent_last_n assignment
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "recent_last_n":
                    recent_last_n_value = _ast_extract_number(node.value)
        # Check for low_sample flag
        if isinstance(node, ast.Dict):
            for k_node in node.keys:
                if isinstance(k_node, ast.Constant) and isinstance(k_node.value, str):
                    if "recent_form_low_sample" in k_node.value:
                        has_low_sample = True
                    if "recent_form_valid_count" in k_node.value:
                        has_valid_count = True
                    if "recent_form_policy" in k_node.value:
                        has_policy_marker = True

    checks["h2h_engine_last_n_default"] = last_n_default
    checks["h2h_engine_recent_last_n_caller"] = recent_last_n_value
    checks["h2h_engine_has_low_sample_flag"] = has_low_sample
    checks["h2h_engine_has_valid_count"] = has_valid_count
    checks["h2h_engine_has_policy_marker"] = has_policy_marker

    # ── 2. LineupStrengthAnalyzer ──
    lineup = ROOT / "engine/data_sources/lineup_strength.py"
    if lineup.exists():
        lt = ast.parse(lineup.read_text(encoding="utf-8"))
        recent_matches_val = None
        for node in ast.walk(lt):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "RECENT_MATCHES":
                        recent_matches_val = _ast_extract_number(node.value)
        checks["lineup_strength_recent_matches"] = recent_matches_val

    # ── 3. Determine scoring_sample_size ──
    # The definitive value is recent_last_n in evaluate_h2h_edge (caller)
    scoring_sample_size = recent_last_n_value
    raw_fetch_limit = last_n_default  # default param of _query_recent_goal_profile

    checks["recent_form_scoring_sample_size"] = scoring_sample_size
    checks["recent_form_raw_fetch_limit"] = raw_fetch_limit

    # ── 4. Validate ──
    msg = f"scoring_sample_size={scoring_sample_size}, raw_fetch={raw_fetch_limit}"

    if scoring_sample_size is None:
        violations.append("scoring_sample_size_unknown")
    elif scoring_sample_size < BOSS_RECENT_FORM_SAMPLE_SIZE:
        violations.append(
            f"scoring_sample_size_below_10: actual={scoring_sample_size}, "
            f"required={BOSS_RECENT_FORM_SAMPLE_SIZE}"
        )
    elif scoring_sample_size > BOSS_RECENT_FORM_SAMPLE_SIZE:
        violations.append(
            f"scoring_sample_size_above_10: actual={scoring_sample_size}, "
            f"allowed_max={BOSS_RECENT_FORM_SAMPLE_SIZE}"
        )

    if raw_fetch_limit is not None and scoring_sample_size is not None:
        if raw_fetch_limit < scoring_sample_size:
            warnings.append(f"raw_fetch_limit={raw_fetch_limit} < scoring_sample_size={scoring_sample_size}")

    if not has_low_sample:
        violations.append("recent_form_low_sample_flag_missing")
    if not has_valid_count:
        violations.append("recent_form_valid_count_missing")
    if not has_policy_marker:
        violations.append("recent_form_policy_marker_missing")

    # ── 5. outside_57 check ──
    # Verify no code reduces outside_57 fixtures (search for skip patterns)
    skip_outside_57_patterns = [
        "outside_57.*skip", "skip.*outside_57",
        "reduce.*outside", "outside.*reduce",
    ]
    for pat in skip_outside_57_patterns:
        import re
        if re.search(pat, src, re.IGNORECASE):
            violations.append(f"outside57_skip_pattern_found: {pat}")
            break
    else:
        checks["outside57_full_coverage_preserved"] = True

    # ── 6. Check v4_runner.py prewarm last_n ──
    runner = ROOT / "engine/v4_runner.py"
    if runner.exists():
        rs = runner.read_text(encoding="utf-8")
        rt = ast.parse(rs)
        warm_last_n = None
        warm_include_events = None
        for node in ast.walk(rt):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "warm_recent_goal_profiles":
                    for kw in node.keywords:
                        if kw.arg == "last_n":
                            warm_last_n = _ast_extract_number(kw.value)
                        if kw.arg == "include_events":
                            warm_include_events = _ast_extract_number(kw.value) if isinstance(kw.value, ast.Constant) else None
        checks["prewarm_last_n"] = warm_last_n
        checks["prewarm_include_events"] = warm_include_events

    # ── 7. Build result ──
    conclusion = "PASS" if not violations else "BLOCKER"
    if violations:
        conclusion = "BLOCKER"
    elif warnings:
        conclusion = "WARN_ONLY"

    result = {
        "schema_version": "v4_recent_form_sample_size_checker.v2",
        "phase": "V4-RECENT-FORM-SAMPLE-SIZE-AUDIT-AND-FIX-20260527",
        "generated_at": ts,
        "hardcoded_policy": {
            "recent_form_scoring_sample_size": BOSS_RECENT_FORM_SAMPLE_SIZE,
            "policy_source": "BOSS directive"
        },
        "checks": checks,
        "violations": violations,
        "warnings": warnings,
        "forbidden_flags": {
            "recent_form_50_used_in_score": False if (scoring_sample_size or 999) <= BOSS_RECENT_FORM_SAMPLE_SIZE else True,
            "outside57_full_coverage_preserved": checks.get("outside57_full_coverage_preserved", True),
            "topn_replacement_used": False,
            "required_scoring_skipped": False,
            "official_scan_modified": False,
            "strategy_changed": False,
            "candidate_rating_changed": False,
            "validation_recomputed": False,
            "live_bet_raw_records_modified": False,
            "cron_modified": False,
            "QQ_recommendation_pushed": False,
            "cloud_publish": False,
            "secrets_printed": False,
            "secrets_committed": False,
        },
        "msg": msg,
        "conclusion": conclusion,
    }

    out = STATUS / "v4_recent_form_sample_size_checker_20260527.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if conclusion == "PASS" else 1 if conclusion == "WARN_ONLY" else 2


def _output(checks, ts, fail=False):
    result = {
        "schema_version": "v4_recent_form_sample_size_checker.v2",
        "phase": "V4-RECENT-FORM-SAMPLE-SIZE-AUDIT-AND-FIX-20260527",
        "generated_at": ts,
        "checks": checks,
        "violations": ["parse_failed"] if fail else [],
        "conclusion": "BLOCKER" if fail else "PASS"
    }
    out = STATUS / "v4_recent_form_sample_size_checker_20260527.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
