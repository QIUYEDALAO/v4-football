#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.rf_shadow_fields import build_rf_shadow_grade_layer

STATUS = ROOT / "data" / "runtime" / "status"
TZ = timezone(timedelta(hours=8))


def _ok(checks: list[dict], name: str, cond: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(cond), "detail": detail})


def _run(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def _sample(base: dict, **kwargs) -> dict:
    x = dict(base)
    x.update(kwargs)
    return x


def _rank(g: str) -> int:
    return {"A": 4, "B": 3, "C": 2, "SKIP": 1, "DATA_MISSING": 0, "LOW_SAMPLE": 0}.get(str(g).upper(), 0)


def main() -> int:
    checks: list[dict] = []
    warnings: list[str] = []
    blockers: list[str] = []

    # Source-level guard: output fields must exist in mapper layers.
    model_src = (ROOT / "tools" / "build_v4_control_center_model.py").read_text(encoding="utf-8")
    dryrun_src = (ROOT / "tools" / "build_v4_rf_shadow_to_official_promotion_dryrun.py").read_text(encoding="utf-8")
    required_fields = [
        "season_aware_shadow_grade_before",
        "season_aware_shadow_grade_after",
        "season_aware_shadow_applied",
        "season_aware_shadow_action",
        "season_aware_shadow_reason",
        "rf_shadow_grade",
        "market_adjusted_shadow_grade",
    ]
    for f in required_fields:
        in_model = f in model_src
        in_dryrun = f in dryrun_src
        _ok(checks, f"field_in_model:{f}", in_model)
        _ok(checks, f"field_in_dryrun:{f}", in_dryrun)
        if not in_model:
            blockers.append(f"model_missing:{f}")
        if not in_dryrun:
            blockers.append(f"dryrun_missing:{f}")

    base = {
        "recent10_sample_count_home": 10,
        "recent10_sample_count_away": 10,
        "home_recent10_fh_involved_rate": 0.8,
        "away_recent10_fh_involved_rate": 0.8,
        "combined_recent10_fh_involved_rate": 0.8,
        "home_recent5_fh_involved_rate": 1.0,
        "away_recent5_fh_involved_rate": 1.0,
        "combined_recent5_fh_involved_rate": 1.0,
        "recent_form_primary_score": 88.0,
        "recent_freshness_status": "FRESH",
        "rf_freshness_status": "FRESH",
        "prematch_ht_line": 1.1,
        "prematch_over_odds": 1.88,
        "season_phase": "ACTIVE_SEASON",
        "league_tier": "TIER_1_ELITE",
        "rf_window_policy": "D60_PRIMARY",
        "rf_sample_status": "SUFFICIENT",
        "rf_early_season_penalty": False,
        "rf_short_break_penalty": False,
        "rf_baseline_only_flag": False,
        "last_season_baseline_available": True,
        "last_season_baseline_score": 0.62,
    }
    factors = {"h2h_official_sample_size": 5, "h2h_ht_goal_rate": 0.4, "h2h_total": 10, "h2h_3y_count": 10}

    r_active = build_rf_shadow_grade_layer(base, factors=factors)
    _ok(checks, "active_season_allows_normal_signal", r_active.get("rf_shadow_grade") in {"A", "B"}, str(r_active.get("rf_shadow_grade")))
    if r_active.get("rf_shadow_grade") not in {"A", "B"}:
        blockers.append("active_season_unexpected_over_downgrade")

    r_short = build_rf_shadow_grade_layer(
        _sample(base, season_phase="SHORT_BREAK", rf_window_policy="D90_SHORT_BREAK_FALLBACK", rf_short_break_penalty=True),
        factors=factors,
    )
    _ok(checks, "short_break_has_penalty_reason", "SHORT_BREAK" in str(r_short.get("season_aware_shadow_action", "")), str(r_short.get("season_aware_shadow_action")))
    _ok(checks, "short_break_cap_not_a", _rank(str(r_short.get("rf_shadow_grade"))) <= _rank("B"), str(r_short.get("rf_shadow_grade")))
    if _rank(str(r_short.get("rf_shadow_grade"))) > _rank("B"):
        blockers.append("short_break_not_penalized")

    r_early = build_rf_shadow_grade_layer(
        _sample(base, season_phase="EARLY_SEASON", rf_window_policy="D60_EARLY_GUARD", rf_early_season_penalty=True, rf_sample_status="LOW_SAMPLE"),
        factors=factors,
    )
    _ok(checks, "early_season_restrict_strong_signal", _rank(str(r_early.get("rf_shadow_grade"))) <= _rank("C"), str(r_early.get("rf_shadow_grade")))
    if _rank(str(r_early.get("rf_shadow_grade"))) > _rank("C"):
        blockers.append("early_season_not_restricted")

    r_post = build_rf_shadow_grade_layer(
        _sample(base, season_phase="POST_OFFSEASON_RETURN", rf_window_policy="BASELINE_ONLY", rf_baseline_only_flag=True),
        factors=factors,
    )
    _ok(checks, "post_offseason_baseline_no_strong_ab", _rank(str(r_post.get("rf_shadow_grade"))) <= _rank("C"), str(r_post.get("rf_shadow_grade")))
    if _rank(str(r_post.get("rf_shadow_grade"))) > _rank("C"):
        blockers.append("post_offseason_promoted_too_high")

    r_off = build_rf_shadow_grade_layer(
        _sample(base, season_phase="OFFSEASON", rf_window_policy="BASELINE_ONLY", rf_baseline_only_flag=True),
        factors=factors,
    )
    _ok(checks, "offseason_safe_default", str(r_off.get("rf_shadow_grade")) in {"SKIP", "C"}, str(r_off.get("rf_shadow_grade")))
    if str(r_off.get("rf_shadow_grade")) not in {"SKIP", "C"}:
        blockers.append("offseason_not_safe")

    r_unknown = build_rf_shadow_grade_layer(
        _sample(base, season_phase="UNKNOWN", rf_window_policy="UNKNOWN_POLICY"),
        factors=factors,
    )
    _ok(checks, "unknown_not_force_active_a", _rank(str(r_unknown.get("rf_shadow_grade"))) <= _rank("C"), str(r_unknown.get("rf_shadow_grade")))
    if _rank(str(r_unknown.get("rf_shadow_grade"))) > _rank("C"):
        blockers.append("unknown_forced_high")

    r_tier3 = build_rf_shadow_grade_layer(
        _sample(base, league_tier="TIER_3_WEAK_COVERAGE"),
        factors=factors,
    )
    _ok(checks, "tier3_conservative", _rank(str(r_tier3.get("rf_shadow_grade"))) <= _rank("B"), str(r_tier3.get("rf_shadow_grade")))
    if _rank(str(r_tier3.get("rf_shadow_grade"))) > _rank("B"):
        blockers.append("tier3_not_conservative")

    r_tier4 = build_rf_shadow_grade_layer(
        _sample(base, league_tier="TIER_4_NON_FORMAL", season_phase="UNKNOWN"),
        factors=factors,
    )
    _ok(checks, "tier4_no_strong_grade", _rank(str(r_tier4.get("rf_shadow_grade"))) <= _rank("C"), str(r_tier4.get("rf_shadow_grade")))
    if _rank(str(r_tier4.get("rf_shadow_grade"))) > _rank("C"):
        blockers.append("tier4_generated_strong_grade")

    r_unknown_tier = build_rf_shadow_grade_layer(
        _sample(base, league_tier="UNKNOWN_TIER"),
        factors=factors,
    )
    _ok(checks, "unknown_tier_safe", _rank(str(r_unknown_tier.get("rf_shadow_grade"))) <= _rank("B"), str(r_unknown_tier.get("rf_shadow_grade")))
    if _rank(str(r_unknown_tier.get("rf_shadow_grade"))) > _rank("B"):
        blockers.append("unknown_tier_not_safe")

    r_baseline_unavailable = build_rf_shadow_grade_layer(
        _sample(base, season_phase="POST_OFFSEASON_RETURN", rf_baseline_only_flag=True, last_season_baseline_available=False, last_season_baseline_score=0),
        factors=factors,
    )
    _ok(checks, "baseline_unavailable_safe", _rank(str(r_baseline_unavailable.get("rf_shadow_grade"))) <= _rank("C"), str(r_baseline_unavailable.get("rf_shadow_grade")))
    if _rank(str(r_baseline_unavailable.get("rf_shadow_grade"))) > _rank("C"):
        blockers.append("baseline_unavailable_not_safe")

    r_extreme = build_rf_shadow_grade_layer(
        _sample(base, prematch_ht_line=0.25, prematch_over_odds=2.60),
        factors=factors,
    )
    _ok(checks, "market_extreme_is_direct_skip", r_extreme.get("opening_market_conflict_level") == "MARKET_EXTREME_VETO" and r_extreme.get("market_adjusted_shadow_grade") == "SKIP", f"{r_extreme.get('opening_market_conflict_level')}:{r_extreme.get('market_adjusted_shadow_grade')}")
    if not (r_extreme.get("opening_market_conflict_level") == "MARKET_EXTREME_VETO" and r_extreme.get("market_adjusted_shadow_grade") == "SKIP"):
        blockers.append("extreme_veto_not_direct_skip")

    r_hard_not_extreme = build_rf_shadow_grade_layer(
        _sample(base, prematch_ht_line=0.50, prematch_over_odds=2.20),
        factors=factors,
    )
    _ok(checks, "market_hard_not_auto_extreme", r_hard_not_extreme.get("opening_market_conflict_level") in {"MARKET_STRONG_CONFLICT", "MARKET_LIGHT_CONFLICT"}, str(r_hard_not_extreme.get("opening_market_conflict_level")))
    if r_hard_not_extreme.get("opening_market_conflict_level") == "MARKET_EXTREME_VETO":
        blockers.append("hard_veto_became_extreme_without_trigger")

    r_no_data = build_rf_shadow_grade_layer(
        _sample(base, prematch_ht_line=None, prematch_over_odds=None),
        factors=factors,
    )
    _ok(checks, "market_no_data_not_promote_A", r_no_data.get("market_adjusted_shadow_grade") != "A", str(r_no_data.get("market_adjusted_shadow_grade")))
    if r_no_data.get("market_adjusted_shadow_grade") == "A":
        blockers.append("no_data_promoted_to_A")

    r_h2h_low = build_rf_shadow_grade_layer(
        _sample(base),
        factors={"h2h_official_sample_size": 2, "h2h_ht_goal_rate": 0.0, "h2h_total": 2, "h2h_3y_count": 2},
    )
    _ok(checks, "h2h_low_sample_no_demotion_flag", r_h2h_low.get("h2h_recent5_support_status") == "H2H_LOW_SAMPLE", str(r_h2h_low.get("h2h_recent5_support_status")))
    _ok(checks, "h2h_add_only_boundary", str(r_h2h_low.get("rf_shadow_grade")) in {"A", "B", "C", "SKIP"}, str(r_h2h_low.get("rf_shadow_grade")))

    # Forbidden touch guards.
    for script in [
        "check_v4_production_default_rules_guard.py",
        "check_v4_system_slim_and_whitelist_mode.py",
        "check_v4_control_center.py",
        "check_v4_no_market_core_validation_skip.py",
        "check_v4_lazy_shadow_production_switch_guard.py",
    ]:
        ok, out = _run(script)
        soft_ok = False
        if not ok and "WARN_ONLY" in out:
            soft_ok = True
            warnings.append(f"guard_warn_only:{script}")
        _ok(checks, f"guard:{script}", ok or soft_ok, out[-260:])
        if not (ok or soft_ok):
            blockers.append(f"guard_failed:{script}")

    # Official chain must not reference shadow grading fields.
    mi_src = (ROOT / "engine" / "v4_match_intelligence.py").read_text(encoding="utf-8")
    official_shadow_ref = ("rf_shadow_grade" in mi_src) or ("market_adjusted_shadow_grade" in mi_src)
    _ok(checks, "official_chain_not_using_shadow_grade", not official_shadow_ref)
    if official_shadow_ref:
        blockers.append("official_chain_shadow_ref_detected")

    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    staged_files = [x.strip() for x in staged.stdout.splitlines() if x.strip()]
    runtime_hit = [x for x in staged_files if x.startswith("v2_football_quant/data/runtime/")]
    secret_hit = [x for x in staged_files if any(t in x.lower() for t in [".env", "secret", "token", "apikey", "api_key"])]
    _ok(checks, "runtime_artifact_not_staged", len(runtime_hit) == 0, ",".join(runtime_hit))
    _ok(checks, "no_secrets_staged", len(secret_hit) == 0, ",".join(secret_hit))
    if runtime_hit:
        blockers.append("runtime_artifact_staged")
    if secret_hit:
        blockers.append("secrets_staged")

    out = {
        "checker": "check_v4_rf_season_aware_shadow_grade_integration",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    out_path = STATUS / f"check_v4_rf_season_aware_shadow_grade_integration_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
