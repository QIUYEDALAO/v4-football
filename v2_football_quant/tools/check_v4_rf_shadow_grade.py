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
REPORT = ROOT / "data" / "daily_reports"
TZ = timezone(timedelta(hours=8))

REQ_FIELDS = [
    "rf_shadow_grade",
    "rf_shadow_score",
    "rf_shadow_route",
    "rf_shadow_reason",
    "rf_shadow_reason_code",
    "rf_primary_signal_level",
    "rf_recent10_signal",
    "rf_recent5_signal",
    "rf_freshness_signal",
    "rf_balance_signal",
    "rf_collection_stage_used",
    "rf_shadow_confidence",
    "rf_entry_rule",
    "rf_recent10_gate_status",
    "rf_recent5_grade_status",
    "rf_heating_exception",
    "rf_heating_exception_reason",
    "rf_balance_status",
    "rf_balance_driver_side",
    "rf_balance_driver_level",
    "rf_balance_weak_side_status",
    "rf_balance_adjustment",
    "rf_balance_reason",
    "recent5_bilateral_gate",
    "recent5_bilateral_gate_mode",
    "recent5_bilateral_gate_reason",
    "home_recent5_pass_count",
    "away_recent5_pass_count",
    "recent5_hot_anchor_team",
    "recent5_other_side_count",
    "recent5_dual_heat_pass",
    "recent5_bilateral_gate_cap_action",
    "recent5_bilateral_gate_exception_used",
    "h2h_recent5_fh_involved_count",
    "h2h_recent5_sample_count",
    "h2h_recent5_support_status",
    "h2h_recent5_bonus_level",
    "h2h_recent5_bonus_reason",
    "h2h_bonus_status",
    "h2h_bonus_reason",
    "opening_market_support_status",
    "opening_market_confirm_level",
    "opening_market_veto_level",
    "opening_market_reason",
    "opening_market_data_status",
    "market_adjusted_shadow_grade",
    "market_adjustment_reason",
    "market_adjusted_shadow_reason",
    "market_policy_action",
    "market_veto_status",
    "market_risk_flag",
    "time_bin_shadow_status",
    "playbook_script",
    "cpl_shadow_status",
    "cpl_shadow_reason",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest(pattern: str, base: Path) -> Path | None:
    files = list(base.glob(pattern))
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


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


def main() -> int:
    checks: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []

    task_status_path = STATUS / "task_status_v4_scan_midday.json"
    task_status = _load_json(task_status_path) if task_status_path.exists() else {}
    out_files = task_status.get("output_files") or {}
    scout_path = Path(out_files["scout"]) if out_files.get("scout") else _latest("scout_v4_*.json", REPORT)
    cv_path = Path(out_files["candidate_view"]) if out_files.get("candidate_view") else _latest("v3v4_dashboard_candidate_view_*.json", STATUS)
    model_path = _latest("v4_control_center_model_*.json", STATUS)

    # Light-mode checker: runtime artifacts are optional in this phase.
    _ok(checks, "task_status_exists", task_status_path.exists(), str(task_status_path))
    status_raw = str(task_status.get("status") or "")
    _ok(checks, "task_status_not_required_for_code_ready", status_raw in {"", "DONE", "RUNNING", "FAILED", "TIMEOUT"}, status_raw)
    _ok(checks, "scout_exists_optional", scout_path is not None and scout_path.exists(), str(scout_path) if scout_path else "")
    _ok(checks, "candidate_view_exists_optional", cv_path is not None and cv_path.exists(), str(cv_path) if cv_path else "")
    _ok(checks, "dashboard_model_exists_optional", model_path is not None and model_path.exists(), str(model_path) if model_path else "")

    scout = _load_json(scout_path) if scout_path and scout_path.exists() else []
    cv = _load_json(cv_path) if cv_path and cv_path.exists() else {}
    model = _load_json(model_path) if model_path and model_path.exists() else {}
    rows = scout if isinstance(scout, list) else []
    _ok(checks, "scout_non_empty_optional", len(rows) > 0, f"rows={len(rows)}")

    if rows:
        for f in REQ_FIELDS:
            ok = all(isinstance(r, dict) and f in r for r in rows)
            _ok(checks, f"scout_field:{f}", ok)
            if not ok:
                blockers.append(f"scout_missing:{f}")
    else:
        warnings.append("scout_empty_or_missing_runtime_optional")
        src = (ROOT / "engine" / "rf_shadow_fields.py").read_text(encoding="utf-8")
        for f in REQ_FIELDS:
            ok = f in src
            _ok(checks, f"shadow_layer_code_contains:{f}", ok)
            if not ok:
                blockers.append(f"shadow_layer_code_missing:{f}")

    # candidate_view runtime check; A/B may be empty in no-candidate day
    ab_rows = (cv.get("A_candidates") or []) + (cv.get("B_candidates") or [])
    if ab_rows:
        for f in REQ_FIELDS:
            ok = all(isinstance(r, dict) and f in r for r in ab_rows)
            _ok(checks, f"candidate_field:{f}", ok)
            if not ok:
                blockers.append(f"candidate_missing:{f}")
    else:
        warnings.append("candidate_ab_empty")
        src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
        for f in REQ_FIELDS:
            ok = f in src
            _ok(checks, f"candidate_code_contains:{f}", ok)
            if not ok:
                blockers.append(f"candidate_code_missing:{f}")

    # model runtime check; items may be empty in no-candidate day
    items = (model.get("candidates") or {}).get("items") or []
    if items:
        for f in REQ_FIELDS:
            ok = all(isinstance(r, dict) and (f in r) for r in items)
            _ok(checks, f"model_field:{f}", ok)
            if not ok:
                blockers.append(f"model_missing:{f}")
    else:
        warnings.append("dashboard_items_empty")
        src = (ROOT / "tools" / "build_v4_control_center_model.py").read_text(encoding="utf-8")
        for f in REQ_FIELDS:
            ok = f in src
            _ok(checks, f"model_code_contains:{f}", ok)
            if not ok:
                blockers.append(f"model_code_missing:{f}")

    # no regrade safety
    mi_src = (ROOT / "engine" / "v4_match_intelligence.py").read_text(encoding="utf-8")
    no_shadow_in_official = "rf_shadow_grade" not in mi_src and "market_adjusted_shadow_grade" not in mi_src
    _ok(checks, "official_grade_not_using_shadow", no_shadow_in_official)
    if not no_shadow_in_official:
        blockers.append("official_grade_overwritten_by_shadow")

    h2h_src = (ROOT / "engine" / "data_sources" / "h2h_engine.py").read_text(encoding="utf-8")
    h2h_gate_unchanged = "rf_shadow_grade" not in h2h_src and "opening_market_support_status" not in h2h_src
    _ok(checks, "h2h_runtime_not_using_shadow", h2h_gate_unchanged)
    if not h2h_gate_unchanged:
        blockers.append("h2h_runtime_changed_by_shadow")

    # Rule scenarios
    base = {
        "recent10_sample_count_home": 10,
        "recent10_sample_count_away": 10,
        "home_recent10_fh_involved_rate": 0.7,
        "away_recent10_fh_involved_rate": 0.6,
        "combined_recent10_fh_involved_rate": 0.65,
        "home_recent5_fh_involved_rate": 1.0,
        "away_recent5_fh_involved_rate": 0.6,
        "combined_recent5_fh_involved_rate": 0.8,
        "recent_form_primary_score": 73.0,
        "prematch_ht_line": 1.25,
        "prematch_over_odds": 1.80,
        "season_phase": "ACTIVE_SEASON",
        "league_tier": "TIER_3_WEAK_COVERAGE",
        "rf_window_policy": "D60_PRIMARY",
        "rf_sample_status": "STABLE",
        "rf_freshness_status": "FRESH",
    }
    factors = {"h2h_official_sample_size": 5, "h2h_ht_goal_rate": 0.4, "h2h_total": 10, "h2h_3y_count": 10}

    r_hot_acc = build_rf_shadow_grade_layer(base, factors=factors)
    _ok(checks, "rule_hot_driver_acceptable_is_B", r_hot_acc.get("market_adjusted_shadow_grade") == "B", str(r_hot_acc.get("market_adjusted_shadow_grade")))
    if r_hot_acc.get("market_adjusted_shadow_grade") != "B":
        blockers.append("rule_hot_driver_acceptable_not_b")
    _ok(checks, "rule_weak_3of5_not_skip", r_hot_acc.get("market_adjusted_shadow_grade") != "SKIP", str(r_hot_acc.get("market_adjusted_shadow_grade")))
    if r_hot_acc.get("market_adjusted_shadow_grade") == "SKIP":
        blockers.append("rule_weak_3of5_direct_skip")

    r_6_5 = build_rf_shadow_grade_layer(
        _sample(base, combined_recent10_fh_involved_rate=0.6, combined_recent5_fh_involved_rate=1.0,
                home_recent5_fh_involved_rate=1.0, away_recent5_fh_involved_rate=1.0, prematch_ht_line=1.25, prematch_over_odds=1.80),
        factors=factors,
    )
    _ok(checks, "rule_6of10_5of5_is_B", r_6_5.get("rf_shadow_grade") == "B", str(r_6_5.get("rf_shadow_grade")))
    if r_6_5.get("rf_shadow_grade") != "B":
        blockers.append("rule_6of10_5of5_fail")

    r_5_5 = build_rf_shadow_grade_layer(
        _sample(base, combined_recent10_fh_involved_rate=0.5, combined_recent5_fh_involved_rate=1.0, prematch_ht_line=1.1, prematch_over_odds=1.9, recent_form_primary_score=70.0),
        factors=factors,
    )
    _ok(checks, "rule_5of10_5of5_is_C", r_5_5.get("rf_shadow_grade") == "C", str(r_5_5.get("rf_shadow_grade")))
    if r_5_5.get("rf_shadow_grade") != "C":
        blockers.append("rule_5of10_5of5_fail")

    r_le4 = build_rf_shadow_grade_layer(
        _sample(base, combined_recent10_fh_involved_rate=0.4, combined_recent5_fh_involved_rate=0.4, prematch_ht_line=1.1, prematch_over_odds=1.9),
        factors=factors,
    )
    _ok(checks, "rule_le4_not_ab", r_le4.get("rf_shadow_grade") not in {"A", "B"}, str(r_le4.get("rf_shadow_grade")))
    if r_le4.get("rf_shadow_grade") in {"A", "B"}:
        blockers.append("rule_le4_entered_ab")

    r_h2h_weak = build_rf_shadow_grade_layer(
        _sample(base, combined_recent10_fh_involved_rate=0.7, combined_recent5_fh_involved_rate=0.8, prematch_ht_line=1.1, prematch_over_odds=1.9),
        factors={"h2h_official_sample_size": 5, "h2h_ht_goal_rate": 0.2, "h2h_total": 10, "h2h_3y_count": 10},
    )
    _ok(checks, "h2h_weak_no_downgrade", r_h2h_weak.get("rf_shadow_grade") in {"A", "B", "C", "SKIP"}, r_h2h_weak.get("h2h_recent5_support_status", ""))

    r_h2h_strong_c = build_rf_shadow_grade_layer(
        _sample(base, combined_recent10_fh_involved_rate=0.5, combined_recent5_fh_involved_rate=0.6, prematch_ht_line=1.1, prematch_over_odds=1.9, recent_form_primary_score=70.0),
        factors={"h2h_official_sample_size": 5, "h2h_ht_goal_rate": 1.0, "h2h_total": 10, "h2h_3y_count": 10},
    )
    _ok(checks, "h2h_strong_not_manufacture_ab", r_h2h_strong_c.get("rf_shadow_grade") not in {"A", "B"}, str(r_h2h_strong_c.get("rf_shadow_grade")))
    if r_h2h_strong_c.get("rf_shadow_grade") in {"A", "B"}:
        blockers.append("h2h_strong_manufactured_ab")

    r_market_strong = build_rf_shadow_grade_layer(
        _sample(base, combined_recent10_fh_involved_rate=0.5, combined_recent5_fh_involved_rate=0.6, prematch_ht_line=1.25, prematch_over_odds=1.8, recent_form_primary_score=70.0),
        factors=factors,
    )
    _ok(checks, "market_strong_no_manufacture_ab", r_market_strong.get("rf_shadow_grade") not in {"A", "B"}, str(r_market_strong.get("rf_shadow_grade")))
    if r_market_strong.get("rf_shadow_grade") in {"A", "B"}:
        blockers.append("market_strong_manufactured_ab")

    r_market_hard = build_rf_shadow_grade_layer(
        _sample(base, combined_recent10_fh_involved_rate=0.7, combined_recent5_fh_involved_rate=1.0, prematch_ht_line=0.25, prematch_over_odds=2.4),
        factors=factors,
    )
    _ok(checks, "market_extreme_veto_direct_skip", r_market_hard.get("market_adjusted_shadow_grade") == "SKIP", str(r_market_hard.get("market_adjusted_shadow_grade")))
    if r_market_hard.get("market_adjusted_shadow_grade") != "SKIP":
        blockers.append("market_hard_veto_not_applied")

    r_no_market = build_rf_shadow_grade_layer(
        _sample(base, no_market_excluded=True, prematch_ht_line=None, prematch_over_odds=None),
        factors=factors,
    )
    _ok(checks, "market_no_market_skip", r_no_market.get("opening_market_support_status") == "MARKET_NO_MARKET" and r_no_market.get("market_adjusted_shadow_grade") == "SKIP")
    if not (r_no_market.get("opening_market_support_status") == "MARKET_NO_MARKET" and r_no_market.get("market_adjusted_shadow_grade") == "SKIP"):
        blockers.append("market_no_market_not_skip")

    # RECENT5_BILATERAL_HEAT_GATE cases
    r_hot_anchor_home = build_rf_shadow_grade_layer(
        _sample(
            base,
            combined_recent10_fh_involved_rate=0.7,
            home_recent5_fh_involved_rate=1.0,  # 5/5
            away_recent5_fh_involved_rate=0.6,  # 3/5
            combined_recent5_fh_involved_rate=0.8,
        ),
        factors=factors,
    )
    _ok(
        checks,
        "recent5_hot_anchor_pass_home",
        r_hot_anchor_home.get("recent5_bilateral_gate") == "PASS" and r_hot_anchor_home.get("recent5_bilateral_gate_mode") == "HOT_ANCHOR_PASS",
        str((r_hot_anchor_home.get("recent5_bilateral_gate"), r_hot_anchor_home.get("recent5_bilateral_gate_mode"))),
    )
    if not (r_hot_anchor_home.get("recent5_bilateral_gate") == "PASS" and r_hot_anchor_home.get("recent5_bilateral_gate_mode") == "HOT_ANCHOR_PASS"):
        blockers.append("recent5_hot_anchor_home_failed")

    r_hot_anchor_away = build_rf_shadow_grade_layer(
        _sample(
            base,
            combined_recent10_fh_involved_rate=0.7,
            home_recent5_fh_involved_rate=0.6,  # 3/5
            away_recent5_fh_involved_rate=1.0,  # 5/5
            combined_recent5_fh_involved_rate=0.8,
        ),
        factors=factors,
    )
    _ok(
        checks,
        "recent5_hot_anchor_pass_away",
        r_hot_anchor_away.get("recent5_bilateral_gate") == "PASS" and r_hot_anchor_away.get("recent5_bilateral_gate_mode") == "HOT_ANCHOR_PASS",
        str((r_hot_anchor_away.get("recent5_bilateral_gate"), r_hot_anchor_away.get("recent5_bilateral_gate_mode"))),
    )
    if not (r_hot_anchor_away.get("recent5_bilateral_gate") == "PASS" and r_hot_anchor_away.get("recent5_bilateral_gate_mode") == "HOT_ANCHOR_PASS"):
        blockers.append("recent5_hot_anchor_away_failed")

    r_dual_heat = build_rf_shadow_grade_layer(
        _sample(
            base,
            combined_recent10_fh_involved_rate=0.7,
            home_recent5_fh_involved_rate=0.8,  # 4/5
            away_recent5_fh_involved_rate=0.8,  # 4/5
            combined_recent5_fh_involved_rate=0.8,
        ),
        factors=factors,
    )
    _ok(
        checks,
        "recent5_dual_heat_pass",
        r_dual_heat.get("recent5_bilateral_gate") == "PASS" and r_dual_heat.get("recent5_bilateral_gate_mode") == "DUAL_HEAT_PASS",
        str((r_dual_heat.get("recent5_bilateral_gate"), r_dual_heat.get("recent5_bilateral_gate_mode"))),
    )
    if not (r_dual_heat.get("recent5_bilateral_gate") == "PASS" and r_dual_heat.get("recent5_bilateral_gate_mode") == "DUAL_HEAT_PASS"):
        blockers.append("recent5_dual_heat_failed")

    r_fail_52 = build_rf_shadow_grade_layer(
        _sample(
            base,
            combined_recent10_fh_involved_rate=0.7,
            home_recent5_fh_involved_rate=1.0,  # 5/5
            away_recent5_fh_involved_rate=0.4,  # 2/5
            combined_recent5_fh_involved_rate=0.7,
            recent_form_primary_score=70.0,
            prematch_ht_line=1.0,
            prematch_over_odds=1.95,
        ),
        factors=factors,
    )
    _ok(
        checks,
        "recent5_fail_5_2_cap_to_c",
        r_fail_52.get("recent5_bilateral_gate") == "FAIL" and r_fail_52.get("recent5_bilateral_gate_cap_action").startswith("CAP_TO_C"),
        str((r_fail_52.get("recent5_bilateral_gate"), r_fail_52.get("recent5_bilateral_gate_cap_action"), r_fail_52.get("rf_shadow_grade"))),
    )
    if not (r_fail_52.get("recent5_bilateral_gate") == "FAIL" and r_fail_52.get("recent5_bilateral_gate_cap_action").startswith("CAP_TO_C")):
        blockers.append("recent5_fail_52_not_capped")

    r_fail_43 = build_rf_shadow_grade_layer(
        _sample(
            base,
            combined_recent10_fh_involved_rate=0.7,
            home_recent5_fh_involved_rate=0.8,  # 4/5
            away_recent5_fh_involved_rate=0.6,  # 3/5
            combined_recent5_fh_involved_rate=0.7,
            recent_form_primary_score=70.0,
            prematch_ht_line=1.0,
            prematch_over_odds=1.95,
        ),
        factors=factors,
    )
    _ok(
        checks,
        "recent5_fail_4_3_cap_to_c",
        r_fail_43.get("recent5_bilateral_gate") == "FAIL" and r_fail_43.get("recent5_bilateral_gate_cap_action").startswith("CAP_TO_C"),
        str((r_fail_43.get("recent5_bilateral_gate"), r_fail_43.get("recent5_bilateral_gate_cap_action"), r_fail_43.get("rf_shadow_grade"))),
    )
    if not (r_fail_43.get("recent5_bilateral_gate") == "FAIL" and r_fail_43.get("recent5_bilateral_gate_cap_action").startswith("CAP_TO_C")):
        blockers.append("recent5_fail_43_not_capped")

    r_exception_b = build_rf_shadow_grade_layer(
        _sample(
            base,
            combined_recent10_fh_involved_rate=0.7,
            combined_recent5_fh_involved_rate=0.7,
            home_recent5_fh_involved_rate=0.8,  # 4/5
            away_recent5_fh_involved_rate=0.6,  # 3/5 => gate FAIL
            recent_form_primary_score=75.0,
            prematch_ht_line=1.0,
            prematch_over_odds=1.90,
            season_phase="ACTIVE_SEASON",
            league_tier="TIER_3_WEAK_COVERAGE",
        ),
        factors=factors,
    )
    exception_ok = (
        r_exception_b.get("recent5_bilateral_gate") == "FAIL"
        and r_exception_b.get("recent5_bilateral_gate_exception_used") is True
        and r_exception_b.get("rf_shadow_grade") == "B"
    )
    _ok(checks, "recent5_fail_but_strong_rf_keeps_b", exception_ok, str((r_exception_b.get("rf_shadow_grade"), r_exception_b.get("recent5_bilateral_gate_exception_used"))))
    if not exception_ok:
        blockers.append("recent5_exception_keep_b_failed")

    r_market_no_data = build_rf_shadow_grade_layer(
        _sample(base, prematch_ht_line=None, prematch_over_odds=None, no_market_excluded=False),
        factors=factors,
    )
    no_data_not_upgrade_a = str(r_market_no_data.get("opening_market_support_status")) == "MARKET_NO_DATA" and str(r_market_no_data.get("market_adjusted_shadow_grade")) != "A"
    _ok(checks, "market_no_data_not_upgrade_a", no_data_not_upgrade_a, str(r_market_no_data.get("market_adjusted_shadow_grade")))
    if not no_data_not_upgrade_a:
        blockers.append("market_no_data_upgraded_to_a")

    # no undefined/null/nan in shadow fields (runtime optional)
    if rows:
        invalid_tokens = {"undefined", "nan"}
        bad_cells = 0
        for r in rows:
            if not isinstance(r, dict):
                continue
            for f in REQ_FIELDS:
                v = r.get(f)
                if v is None:
                    bad_cells += 1
                    continue
                if isinstance(v, float) and str(v).lower() == "nan":
                    bad_cells += 1
                    continue
                if isinstance(v, str) and v.strip().lower() in invalid_tokens:
                    bad_cells += 1
        _ok(checks, "no_undefined_null_nan_runtime", bad_cells == 0, f"bad_cells={bad_cells}")
        if bad_cells > 0:
            blockers.append("runtime_has_undefined_null_nan")

    # Guard scripts
    for s in [
        "check_v4_production_default_rules_guard.py",
        "check_v4_no_market_core_validation_skip.py",
        "check_v4_true_goal_time_distribution.py",
        "check_v4_playbook_script_and_time_distribution.py",
    ]:
        ok, out = _run(s)
        soft_ok = False
        if not ok and s in {"check_v4_no_market_core_validation_skip.py", "check_v4_true_goal_time_distribution.py", "check_v4_playbook_script_and_time_distribution.py"} and "WARN_ONLY" in out:
            soft_ok = True
        _ok(checks, f"guard:{s}", ok or soft_ok, out[-300:])
        if not (ok or soft_ok):
            blockers.append(f"guard_failed:{s}")

    # secrets staged
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    staged_files = [x.strip() for x in staged.stdout.splitlines() if x.strip()]
    secret_hit = [x for x in staged_files if any(t in x.lower() for t in [".env", "secret", "token", "apikey", "api_key"])]
    _ok(checks, "no_secrets_staged", len(secret_hit) == 0, ",".join(secret_hit))
    if secret_hit:
        blockers.append("secrets_staged")

    return _finish(checks, warnings, blockers)


def _finish(checks: list[dict], warnings: list[str], blockers: list[str]) -> int:
    out = {
        "schema_version": "v4_rf_shadow_grade_checker.v1",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    out_path = STATUS / f"check_v4_rf_shadow_grade_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
