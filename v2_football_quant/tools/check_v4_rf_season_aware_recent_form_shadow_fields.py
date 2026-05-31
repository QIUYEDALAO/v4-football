#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "daily_reports"
STATUS_DIR = ROOT / "data" / "runtime" / "status"
ACCEPT_DIR = ROOT / "data" / "runtime" / "acceptance"
TZ = timezone(timedelta(hours=8))

REQUIRED_SEASON_FIELDS = [
    "season_phase",
    "league_tier",
    "rf_window_policy",
    "recent60_match_count_home",
    "recent60_match_count_away",
    "recent90_match_count_home",
    "recent90_match_count_away",
    "recent10_used_count_home",
    "recent10_used_count_away",
    "recent5_used_count_home",
    "recent5_used_count_away",
    "recent10_window_days_home",
    "recent10_window_days_away",
    "recent5_window_days_home",
    "recent5_window_days_away",
    "current_season_match_count_home",
    "current_season_match_count_away",
    "days_since_last_official_match_home",
    "days_since_last_official_match_away",
    "last_season_baseline_available",
    "last_season_baseline_score",
    "rf_baseline_only_flag",
    "rf_sample_status",
    "rf_freshness_status",
    "rf_early_season_penalty",
    "rf_short_break_penalty",
    "rf_season_aware_reason",
    "rf_season_adjusted_shadow_grade",
]
REASON_CODE_FIELDS = [
    "season_phase_reason_code",
    "league_tier_reason_code",
    "current_season_count_reason_code",
]

BAD_STRINGS = {"undefined", "null", "nan"}
ALLOWED_SEASON_PHASE = {
    "ACTIVE_SEASON",
    "SHORT_BREAK",
    "EARLY_SEASON",
    "POST_OFFSEASON_RETURN",
    "OFFSEASON",
    "UNKNOWN",
}
ALLOWED_LEAGUE_TIER = {
    "TIER_1_ELITE",
    "TIER_2_MAINSTREAM",
    "TIER_3_WEAK_COVERAGE",
    "TIER_4_NON_FORMAL",
    "UNKNOWN_TIER",
}


def _latest(pattern: str, base: Path) -> Path | None:
    files = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ok(checks: list[dict], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _run(script: str, args: list[str] | None = None) -> tuple[bool, str]:
    cmd = ["python3", str(ROOT / "tools" / script)]
    if args:
        cmd.extend(args)
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def _is_bad(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return str(v).lower() == "nan"
    if isinstance(v, str):
        return v.strip().lower() in BAD_STRINGS or v.strip() == ""
    return False


def _dist(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "UNKNOWN").strip() or "UNKNOWN"
        out[k] = out.get(k, 0) + 1
    return out


def _to_int(v: Any, default: int = -1) -> int:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _find_dryrun(date_key: str) -> Path | None:
    p = ACCEPT_DIR / f"v4_rf_shadow_to_official_promotion_dryrun_{date_key}.json"
    if p.exists():
        return p
    return _latest("v4_rf_shadow_to_official_promotion_dryrun_*.json", ACCEPT_DIR)


def main() -> int:
    checks: list[dict] = []
    warnings: list[str] = []
    blockers: list[str] = []

    scout_path = _latest("scout_v4_*.json", REPORT_DIR)
    model_path = _latest("v4_control_center_model_*.json", STATUS_DIR)
    _ok(checks, "scout_exists", scout_path is not None and scout_path.exists(), str(scout_path) if scout_path else "")
    _ok(checks, "model_exists", model_path is not None and model_path.exists(), str(model_path) if model_path else "")
    if not scout_path or not model_path:
        blockers.append("required_artifact_missing")
        return _finish(checks, warnings, blockers)

    scout_rows = _load_json(scout_path)
    if not isinstance(scout_rows, list):
        scout_rows = []
    date_key = scout_path.stem.replace("scout_v4_", "")
    dryrun_path = _find_dryrun(date_key)
    _ok(checks, "dryrun_artifact_exists", dryrun_path is not None and dryrun_path.exists(), str(dryrun_path) if dryrun_path else "")
    if dryrun_path is None:
        blockers.append("dryrun_artifact_missing")
        return _finish(checks, warnings, blockers)

    dryrun = _load_json(dryrun_path)
    model = _load_json(model_path)

    _ok(checks, "scout_rows_positive", len(scout_rows) > 0, str(len(scout_rows)))
    if len(scout_rows) <= 0:
        blockers.append("scout_rows_zero")

    # 1-10 scout field presence
    missing_fields: list[str] = []
    bad_fields: list[str] = []
    for f in REQUIRED_SEASON_FIELDS:
        has_all = all((f in row) for row in scout_rows)
        _ok(checks, f"scout_has_{f}", has_all)
        if not has_all:
            missing_fields.append(f)
            continue
        has_bad = any(_is_bad(row.get(f)) for row in scout_rows)
        _ok(checks, f"scout_{f}_no_bad_values", not has_bad)
        if has_bad:
            bad_fields.append(f)

    if missing_fields:
        blockers.append("missing_fields:" + ",".join(missing_fields))
    if bad_fields:
        blockers.append("bad_values:" + ",".join(bad_fields))

    reason_fields_in_scout = {f: all((f in row) for row in scout_rows) for f in REASON_CODE_FIELDS}
    has_all_reason_fields_in_scout = all(reason_fields_in_scout.values())
    _ok(checks, "reason_code_fields_present_in_scout", has_all_reason_fields_in_scout, json.dumps(reason_fields_in_scout, ensure_ascii=False))
    if not has_all_reason_fields_in_scout:
        warnings.append("legacy_scout_missing_reason_code_fields")
        rf_src = (ROOT / "engine" / "rf_shadow_fields.py").read_text(encoding="utf-8")
        reason_source_ok = all(f'"{k}"' in rf_src for k in REASON_CODE_FIELDS)
        _ok(checks, "reason_code_fields_emitted_by_detector_source", reason_source_ok)
        if not reason_source_ok:
            blockers.append("reason_code_detector_source_missing")

    invalid_phase = sorted(
        {
            str(row.get("season_phase") or "UNKNOWN").strip().upper()
            for row in scout_rows
            if str(row.get("season_phase") or "UNKNOWN").strip().upper() not in ALLOWED_SEASON_PHASE
        }
    )
    invalid_tier = sorted(
        {
            str(row.get("league_tier") or "UNKNOWN_TIER").strip().upper()
            for row in scout_rows
            if str(row.get("league_tier") or "UNKNOWN_TIER").strip().upper() not in ALLOWED_LEAGUE_TIER
        }
    )
    _ok(checks, "season_phase_enum_valid", len(invalid_phase) == 0, ",".join(invalid_phase))
    _ok(checks, "league_tier_enum_valid", len(invalid_tier) == 0, ",".join(invalid_tier))
    if invalid_phase:
        blockers.append("invalid_season_phase_enum")
    if invalid_tier:
        blockers.append("invalid_league_tier_enum")

    bad_current_count = False
    for row in scout_rows:
        h = _to_int(row.get("current_season_match_count_home"))
        a = _to_int(row.get("current_season_match_count_away"))
        if h < 0 or a < 0:
            bad_current_count = True
            break
    _ok(checks, "current_season_match_count_non_negative", not bad_current_count)
    if bad_current_count:
        blockers.append("current_season_match_count_invalid")

    # 11 dashboard model has fields
    items = ((model.get("candidates") or {}).get("items") or [])
    if items:
        model_missing = []
        for f in [*REQUIRED_SEASON_FIELDS, *REASON_CODE_FIELDS]:
            ok = all((f in x and not _is_bad(x.get(f))) for x in items if isinstance(x, dict))
            _ok(checks, f"model_items_has_{f}", ok)
            if not ok:
                model_missing.append(f)
        if model_missing:
            blockers.append("model_missing:" + ",".join(model_missing))
    else:
        warnings.append("candidate_items_empty")
        src = (ROOT / "tools" / "build_v4_control_center_model.py").read_text(encoding="utf-8")
        for f in [*REQUIRED_SEASON_FIELDS, *REASON_CODE_FIELDS]:
            ok = f in src
            _ok(checks, f"model_builder_contains_{f}", ok)
            if not ok:
                blockers.append(f"builder_missing:{f}")

    # 12 dryrun artifact has fields
    dry_entries = []
    for k in ("dryrun_a_candidates", "dryrun_b_candidates", "dryrun_c_candidates"):
        dry_entries.extend(dryrun.get(k) or [])
    if dry_entries:
        miss_dry = []
        dry_need = [
            "season_phase",
            "season_phase_reason_code",
            "league_tier",
            "league_tier_reason_code",
            "current_season_count_reason_code",
            "rf_sample_status",
            "rf_freshness_status",
            "rf_season_aware_reason",
            "rf_season_adjusted_shadow_grade",
        ]
        for f in dry_need:
            ok = all((f in x and not _is_bad(x.get(f))) for x in dry_entries if isinstance(x, dict))
            _ok(checks, f"dryrun_entries_has_{f}", ok)
            if not ok:
                miss_dry.append(f)
        if miss_dry:
            blockers.append("dryrun_missing:" + ",".join(miss_dry))
    else:
        d = dryrun.get("season_aware_field_distribution") or {}
        ok = all(
            k in d
            for k in (
                "season_phase",
                "season_phase_reason_code",
                "league_tier",
                "league_tier_reason_code",
                "current_season_count_reason_code",
                "rf_sample_status",
                "rf_freshness_status",
            )
        )
        _ok(checks, "dryrun_distribution_fallback_exists", ok)
        if not ok:
            blockers.append("dryrun_distribution_missing")

    # 14-17 scoring/official unchanged checks via existing guards
    ok_veto, out_veto = _run("check_v4_rf_promotion_market_veto_policy.py")
    _ok(checks, "market_veto_policy_checker_pass", ok_veto, out_veto[-300:])
    if not ok_veto:
        blockers.append("market_veto_policy_failed")

    ok_promote, out_promote = _run("check_v4_rf_shadow_to_official_promotion_dryrun.py")
    _ok(checks, "promotion_dryrun_checker_pass", ok_promote, out_promote[-300:])
    if not ok_promote:
        blockers.append("promotion_dryrun_checker_failed")

    safe = dryrun.get("safety_checks") or {}
    no_regrade = not bool(safe.get("official_grade_modified"))
    _ok(checks, "official_grade_unchanged_in_dryrun", no_regrade, json.dumps(safe, ensure_ascii=False))
    if not no_regrade:
        blockers.append("official_grade_modified")

    # 18-21 pending/validation/live/qq guards
    todo = model.get("todo_summary") or {}
    pending = todo.get("pending_bet_candidates") or []
    pending_ok = all(str((x or {}).get("grade") or "").upper() in {"A", "B"} for x in pending)
    _ok(checks, "pending_bet_candidates_official_ab_only", pending_ok, f"count={len(pending)}")
    if not pending_ok:
        blockers.append("pending_contains_non_ab")

    val_blob = json.dumps(model.get("cumulative_validation_detail") or {}, ensure_ascii=False)
    validation_uses_season = any(k in val_blob for k in ("rf_season_adjusted_shadow_grade", "season_phase", "league_tier"))
    _ok(checks, "validation_not_using_season_fields", not validation_uses_season)
    if validation_uses_season:
        blockers.append("validation_uses_season_fields")

    live_blob = json.dumps(model.get("live_bet") or {}, ensure_ascii=False)
    live_uses_season = any(k in live_blob for k in ("rf_season_adjusted_shadow_grade", "season_phase", "league_tier"))
    _ok(checks, "live_bet_not_using_season_fields", not live_uses_season)
    if live_uses_season:
        blockers.append("live_bet_uses_season_fields")

    v4_scan_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8").lower()
    qq_lines = "\n".join(line for line in v4_scan_src.splitlines() if "qq" in line)
    qq_uses_season = any(k in qq_lines for k in ("rf_season_adjusted_shadow_grade", "season_phase", "league_tier"))
    _ok(checks, "qq_not_using_season_fields", not qq_uses_season)
    if qq_uses_season:
        blockers.append("qq_uses_season_fields")

    # 22-24 baseline guards
    ok_default, out_default = _run("check_v4_production_default_rules_guard.py")
    _ok(checks, "default_rules_guard_pass", ok_default, out_default[-300:])
    if not ok_default:
        blockers.append("default_rules_guard_failed")

    ok_slim, out_slim = _run("check_v4_system_slim_and_whitelist_mode.py")
    _ok(checks, "cron_whitelist_guard_pass", ok_slim, out_slim[-300:])
    if not ok_slim:
        blockers.append("cron_or_whitelist_guard_failed")

    # 25-26 stage safety
    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    secret_staged = [x for x in staged if any(t in x.lower() for t in [".env", "secret", "token", "apikey", "api_key"])]
    runtime_staged = [x for x in staged if x.startswith("v2_football_quant/data/runtime/")]
    _ok(checks, "no_secrets_staged", len(secret_staged) == 0, ",".join(secret_staged))
    _ok(checks, "runtime_artifact_not_staged", len(runtime_staged) == 0, ",".join(runtime_staged))
    if secret_staged:
        blockers.append("secrets_staged")
    if runtime_staged:
        blockers.append("runtime_artifact_staged")

    # Summary distributions for report reference
    _ok(checks, "season_phase_distribution", True, json.dumps(_dist(scout_rows, "season_phase"), ensure_ascii=False))
    _ok(checks, "league_tier_distribution", True, json.dumps(_dist(scout_rows, "league_tier"), ensure_ascii=False))
    _ok(checks, "rf_sample_status_distribution", True, json.dumps(_dist(scout_rows, "rf_sample_status"), ensure_ascii=False))
    _ok(checks, "rf_freshness_status_distribution", True, json.dumps(_dist(scout_rows, "rf_freshness_status"), ensure_ascii=False))

    return _finish(checks, warnings, blockers)


def _finish(checks: list[dict], warnings: list[str], blockers: list[str]) -> int:
    out = {
        "checker": "check_v4_rf_season_aware_recent_form_shadow_fields",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = STATUS_DIR / f"check_v4_rf_season_aware_recent_form_shadow_fields_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
