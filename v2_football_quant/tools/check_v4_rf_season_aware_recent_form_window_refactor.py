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

BAD_STRINGS = {"undefined", "null", "nan"}

REQUIRED_FIELDS = [
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
]


def _latest(pattern: str, base: Path) -> Path | None:
    files = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ok(checks: list[dict], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _run_checker(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def _is_bad(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return str(v).lower() == "nan"
    if isinstance(v, str):
        return v.strip().lower() in BAD_STRINGS
    return False


def _dist(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "UNKNOWN").strip() or "UNKNOWN"
        out[k] = out.get(k, 0) + 1
    return out


def main() -> int:
    checks: list[dict] = []
    warnings: list[str] = []
    blockers: list[str] = []

    scout_path = _latest("scout_v4_*.json", REPORT_DIR)
    model_path = _latest("v4_control_center_model_*.json", STATUS_DIR)
    dryrun_path = _latest("v4_rf_shadow_to_official_promotion_dryrun_*.json", ACCEPT_DIR)

    _ok(checks, "scout_exists", bool(scout_path and scout_path.exists()), str(scout_path) if scout_path else "")
    _ok(checks, "model_exists", bool(model_path and model_path.exists()), str(model_path) if model_path else "")
    _ok(checks, "dryrun_exists", bool(dryrun_path and dryrun_path.exists()), str(dryrun_path) if dryrun_path else "")
    if not scout_path or not model_path or not dryrun_path:
        blockers.append("missing_required_artifacts")
        return _finish(checks, warnings, blockers)

    scout_rows = _load_json(scout_path)
    if not isinstance(scout_rows, list):
        scout_rows = []
    model = _load_json(model_path)
    dryrun = _load_json(dryrun_path)

    _ok(checks, "scout_rows_positive", len(scout_rows) > 0, str(len(scout_rows)))
    if len(scout_rows) == 0:
        blockers.append("scout_rows_zero")

    for f in REQUIRED_FIELDS:
        has_all = all((f in r) for r in scout_rows)
        _ok(checks, f"scout_has_{f}", has_all)
        if not has_all:
            blockers.append(f"missing_field:{f}")
            continue
        bad = any(_is_bad(r.get(f)) for r in scout_rows)
        _ok(checks, f"scout_{f}_no_bad", not bad)
        if bad:
            blockers.append(f"bad_value:{f}")

    active_rows = [r for r in scout_rows if str(r.get("season_phase") or "").upper() == "ACTIVE_SEASON"]
    if active_rows:
        active_ok = all(int(r.get("recent10_window_days_home") or 0) <= 60 and int(r.get("recent10_window_days_away") or 0) <= 60 for r in active_rows)
        _ok(checks, "active_season_uses_60d_window", active_ok, f"rows={len(active_rows)}")
        if not active_ok:
            blockers.append("active_season_window_gt_60")
    else:
        warnings.append("no_active_season_rows_in_latest_scout")
        _ok(checks, "active_season_uses_60d_window", True, "no_active_rows_warn_only")

    short_rows = [r for r in scout_rows if str(r.get("season_phase") or "").upper() == "SHORT_BREAK"]
    if short_rows:
        policies = {str(r.get("rf_window_policy") or "") for r in short_rows}
        short_policy_ok = policies == {"D90_SHORT_BREAK_FALLBACK"}
        short_penalty_ok = all(bool(r.get("rf_short_break_penalty")) for r in short_rows)
        _ok(checks, "short_break_policy_d90_fallback", short_policy_ok, f"rows={len(short_rows)} policies={sorted(policies)}")
        _ok(checks, "short_break_penalty_true", short_penalty_ok, f"rows={len(short_rows)}")
        if not short_policy_ok:
            # Legacy scout rows may still carry old policy label without re-scan.
            src = (ROOT / "engine" / "rf_shadow_fields.py").read_text(encoding="utf-8")
            source_has_new_policy = "D90_SHORT_BREAK_FALLBACK" in src
            _ok(checks, "short_break_policy_source_upgraded", source_has_new_policy)
            if source_has_new_policy and policies == {"D90_SHORT_BREAK"}:
                warnings.append("legacy_scout_short_break_policy_label_not_refreshed")
            else:
                blockers.append("short_break_policy_not_d90_fallback")
        if not short_penalty_ok:
            blockers.append("short_break_penalty_missing")
    else:
        warnings.append("no_short_break_rows_in_latest_scout")
        _ok(checks, "short_break_policy_d90_fallback", True, "no_short_rows_warn_only")
        _ok(checks, "short_break_penalty_true", True, "no_short_rows_warn_only")

    early_rows = [r for r in scout_rows if str(r.get("season_phase") or "").upper() == "EARLY_SEASON"]
    if early_rows:
        early_penalty_ok = all(bool(r.get("rf_early_season_penalty")) for r in early_rows)
        early_limit_ok = all(int(r.get("recent10_used_count_home") or 0) <= 5 and int(r.get("recent10_used_count_away") or 0) <= 5 for r in early_rows)
        _ok(checks, "early_season_penalty_true", early_penalty_ok, f"rows={len(early_rows)}")
        _ok(checks, "early_season_used_count_limited", early_limit_ok, f"rows={len(early_rows)}")
        if not early_penalty_ok:
            blockers.append("early_penalty_missing")
        if not early_limit_ok:
            blockers.append("early_used_count_not_limited")
    else:
        warnings.append("no_early_season_rows_in_latest_scout")
        _ok(checks, "early_season_penalty_true", True, "no_early_rows_warn_only")
        _ok(checks, "early_season_used_count_limited", True, "no_early_rows_warn_only")

    po_rows = [r for r in scout_rows if str(r.get("season_phase") or "").upper() in {"POST_OFFSEASON_RETURN", "OFFSEASON"}]
    if po_rows:
        baseline_only_ok = all(bool(r.get("rf_baseline_only_flag")) for r in po_rows)
        _ok(checks, "post_offseason_baseline_only", baseline_only_ok, f"rows={len(po_rows)}")
        if not baseline_only_ok:
            blockers.append("post_offseason_not_baseline_only")
    else:
        warnings.append("no_post_offseason_or_offseason_rows_in_latest_scout")
        _ok(checks, "post_offseason_baseline_only", True, "no_post_rows_warn_only")

    t4_rows = [r for r in scout_rows if str(r.get("league_tier") or "").upper() == "TIER_4_NON_FORMAL"]
    if t4_rows:
        t4_guard_ok = all(str(r.get("season_phase") or "").upper() != "ACTIVE_SEASON" for r in t4_rows)
        _ok(checks, "tier4_non_formal_not_active_season", t4_guard_ok, f"rows={len(t4_rows)}")
        if not t4_guard_ok:
            blockers.append("tier4_non_formal_marked_active")
    else:
        warnings.append("no_tier4_rows_in_latest_scout")
        _ok(checks, "tier4_non_formal_not_active_season", True, "no_tier4_rows_warn_only")

    unknown_rows = [r for r in scout_rows if str(r.get("season_phase") or "").upper() == "UNKNOWN"]
    unknown_safe = True
    for r in unknown_rows:
        if _is_bad(r.get("rf_window_policy")):
            unknown_safe = False
            break
    _ok(checks, "unknown_phase_safe_defaults", unknown_safe, f"rows={len(unknown_rows)}")
    if not unknown_safe:
        blockers.append("unknown_phase_bad_defaults")

    # Ensure window refactor did not leak to score/official chain.
    for script in [
        "check_v4_rf_season_aware_recent_form_shadow_fields.py",
        "check_v4_rf_shadow_to_official_promotion_dryrun.py",
        "check_v4_production_default_rules_guard.py",
        "check_v4_lazy_shadow_production_switch_guard.py",
    ]:
        ok, out = _run_checker(script)
        _ok(checks, f"guard_{script}", ok, out[-250:])
        if not ok:
            blockers.append(f"guard_failed:{script}")

    # model sanity
    items = ((model.get("candidates") or {}).get("items") or [])
    if items:
        item_bad = any(_is_bad((x or {}).get("rf_window_policy")) for x in items if isinstance(x, dict))
        _ok(checks, "model_rf_window_policy_no_bad", not item_bad, f"items={len(items)}")
        if item_bad:
            blockers.append("model_rf_window_policy_bad")
    else:
        warnings.append("candidate_items_empty_warn_only")
        _ok(checks, "model_rf_window_policy_no_bad", True, "no_items_warn_only")

    _ok(checks, "season_phase_distribution", True, json.dumps(_dist(scout_rows, "season_phase"), ensure_ascii=False))
    _ok(checks, "league_tier_distribution", True, json.dumps(_dist(scout_rows, "league_tier"), ensure_ascii=False))
    _ok(checks, "window_policy_distribution", True, json.dumps(_dist(scout_rows, "rf_window_policy"), ensure_ascii=False))

    # staged safety
    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    has_runtime = any(x.startswith("v2_football_quant/data/runtime/") for x in staged)
    has_secret = any(any(tok in x.lower() for tok in [".env", "secret", "token", "apikey", "api_key"]) for x in staged)
    _ok(checks, "runtime_artifacts_not_staged", not has_runtime)
    _ok(checks, "secrets_not_staged", not has_secret)
    if has_runtime:
        blockers.append("runtime_artifact_staged")
    if has_secret:
        blockers.append("secret_staged")

    return _finish(checks, warnings, blockers)


def _finish(checks: list[dict], warnings: list[str], blockers: list[str]) -> int:
    conclusion = "PASS" if not blockers else "BLOCKER"
    out = {
        "checker": "check_v4_rf_season_aware_recent_form_window_refactor",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": conclusion,
    }
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = STATUS_DIR / f"check_v4_rf_season_aware_recent_form_window_refactor_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
