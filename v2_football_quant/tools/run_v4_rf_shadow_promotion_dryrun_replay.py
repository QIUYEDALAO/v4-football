#!/usr/bin/env python3
"""
Phase 3C: V4 RF shadow promotion dryrun/replay.

Read-only simulation:
- compare current official grade vs shadow dryrun grade
- collect recent5 bilateral gate and B-floor exception stats
- enforce no-official/no-pending/no-QQ behavior

No API calls, no rescans, no pending writes, no QQ push.
"""

from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCOUT_DIR = ROOT / "data" / "daily_reports"
STATUS_DIR = ROOT / "data" / "runtime" / "status"
OUT_DIR = ROOT / "data" / "runtime" / "acceptance"

GRADE_RANK = {"A": 4, "B": 3, "C": 2, "SKIP": 1, "": 0, "NONE": 0}


def _norm_grade(v: Any) -> str:
    g = str(v or "").strip().upper()
    return g if g in {"A", "B", "C", "SKIP"} else ""


def _safe_text(v: Any, default: str = "NOT_AVAILABLE") -> str:
    if v is None:
        return default
    if isinstance(v, float):
        if v != v:
            return default
    s = str(v).strip()
    return s if s else default


def _safe_num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        n = float(v)
        if n != n:
            return default
        return n
    except Exception:
        return default


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        t = v.strip().lower()
        if t in {"1", "true", "yes", "on"}:
            return True
        if t in {"0", "false", "no", "off", ""}:
            return False
    return default


def _latest_date() -> str:
    files = sorted(SCOUT_DIR.glob("scout_v4_*.json"))
    if not files:
        raise FileNotFoundError("No scout_v4_*.json found")
    return files[-1].stem.split("_")[-1]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_scout(date: str) -> list[dict[str, Any]]:
    path = SCOUT_DIR / f"scout_v4_{date}.json"
    rows = _load_json(path)
    if not isinstance(rows, list):
        raise ValueError(f"Invalid scout list: {path}")
    return rows


def _load_candidate_view(date: str) -> dict[str, Any]:
    path = STATUS_DIR / f"v3v4_dashboard_candidate_view_{date}.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid candidate view dict: {path}")
    return data


def _is_market_no_data(row: dict[str, Any]) -> bool:
    status = str(row.get("opening_market_support_status") or "").upper()
    ds = str(row.get("opening_market_data_status") or "").upper()
    return status == "MARKET_NO_DATA" or ds in {"NO_DATA", "API_HAS_ODDS_BUT_NO_HT_OU"}


def _is_no_market(row: dict[str, Any]) -> bool:
    status = str(row.get("opening_market_support_status") or "").upper()
    ds = str(row.get("opening_market_data_status") or "").upper()
    return status == "MARKET_NO_MARKET" or ds == "NO_MARKET" or _safe_bool(row.get("no_market_excluded"), False)


def _is_extreme_veto(row: dict[str, Any]) -> bool:
    c1 = str(row.get("opening_market_conflict_level") or "").upper()
    c2 = str(row.get("opening_market_support_status") or "").upper()
    return c1 == "MARKET_EXTREME_VETO" or c2 == "MARKET_EXTREME_VETO"


def _dryrun_grade(row: dict[str, Any]) -> tuple[str, str, str, bool]:
    # returns: grade, source, reason_code, allowed_to_promote
    market_grade = _norm_grade(row.get("market_adjusted_shadow_grade"))
    rf_grade = _norm_grade(row.get("rf_shadow_grade"))
    source_grade = market_grade or rf_grade or "SKIP"

    if _is_extreme_veto(row):
        return "SKIP", "market_adjusted_shadow_grade", "MARKET_EXTREME_VETO_BLOCK", False

    if _is_no_market(row):
        return "SKIP", "market_adjusted_shadow_grade", "NO_MARKET_BLOCK", False

    if _is_market_no_data(row) and source_grade == "A":
        return "B", "market_adjusted_shadow_grade", "MARKET_NO_DATA_A_BLOCK_TO_B", True

    allowed = source_grade in {"A", "B"}
    return source_grade, "market_adjusted_shadow_grade" if market_grade else "rf_shadow_grade", "NORMAL_SHADOW_REPLAY", allowed


def _delta(official: str, shadow: str) -> tuple[str, str]:
    o = _norm_grade(official)
    s = _norm_grade(shadow)
    if not o and not s:
        return "DATA_MISSING", "official and shadow both missing"
    if o and not s:
        return "OFFICIAL_ONLY", f"official={o}, shadow missing"
    if not o and s:
        return "SHADOW_ONLY", f"official missing, shadow={s}"
    ro = GRADE_RANK[o]
    rs = GRADE_RANK[s]
    if ro == rs:
        return "SAME", f"official={o}, shadow={s}"
    if rs > ro:
        return "SHADOW_HIGHER", f"official={o}, shadow={s}"
    return "SHADOW_LOWER", f"official={o}, shadow={s}"


def _exception_intent(row: dict[str, Any]) -> bool:
    gate = str(row.get("recent5_bilateral_gate") or "").upper()
    score = _safe_num(row.get("rf_shadow_score"), 0.0)
    r10 = str(row.get("rf_recent10_gate_status") or "")
    balance_lvl = str(row.get("rf_balance_driver_level") or "").upper()
    balance_status = str(row.get("rf_balance_status") or "").upper()
    market_status = str(row.get("opening_market_support_status") or "").upper()
    season_phase = str(row.get("season_phase") or "").upper()
    tier = str(row.get("league_tier") or "").upper()
    if gate != "FAIL":
        return False
    if score < 73:
        return False
    if "PASS_7_OF_10" not in r10 and "BREAK_6_OF_10" not in r10 and "ENTRY_PASS_10G7" not in str(row.get("rf_entry_rule") or ""):
        return False
    if not (
        balance_lvl in {"HOT_DRIVER", "STRONG_DRIVER"}
        or balance_status in {"HOT_DRIVER_ACCEPTABLE", "STRONG_DRIVER_ACCEPTABLE"}
    ):
        return False
    if market_status not in {"MARKET_CONFIRM", "MARKET_WEAK_CONFIRM", "MARKET_STRONG_CONFIRM"}:
        return False
    if season_phase != "ACTIVE_SEASON":
        return False
    if tier == "TIER_4_NON_FORMAL":
        return False
    if _is_extreme_veto(row):
        return False
    if _is_market_no_data(row):
        return False
    if str(row.get("season_phase") or "").upper() == "POST_OFFSEASON_RETURN":
        return False
    if _safe_bool(row.get("rf_baseline_only_flag"), False):
        return False
    return True


def _pending_fixture_ids(cv: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    for item in cv.get("pending_bet_candidates") or []:
        fid = item.get("fixture_id")
        if isinstance(fid, int):
            out.add(fid)
    return out


def build_report(date: str) -> dict[str, Any]:
    scout = _load_scout(date)
    cv = _load_candidate_view(date)

    pending_ids = _pending_fixture_ids(cv)
    official_ids = set()
    official_ab_ids = set()

    for arr in (cv.get("A_candidates") or [], cv.get("B_candidates") or [], cv.get("C_candidates") or []):
        if isinstance(arr, dict):
            continue
    for item in cv.get("A_candidates") or []:
        fid = item.get("fixture_id")
        if isinstance(fid, int):
            official_ids.add(fid)
            official_ab_ids.add(fid)
    for item in cv.get("B_candidates") or []:
        fid = item.get("fixture_id")
        if isinstance(fid, int):
            official_ids.add(fid)
            official_ab_ids.add(fid)
    for item in cv.get("C_candidates") or []:
        fid = item.get("fixture_id")
        if isinstance(fid, int):
            official_ids.add(fid)

    per_row: list[dict[str, Any]] = []
    dry_dist = {"A": 0, "B": 0, "C": 0, "SKIP": 0}

    recent5_pass = 0
    hot_anchor = 0
    dual_heat = 0
    recent5_fail = 0
    fail_cap_to_c = 0
    exception_cnt = 0
    exception_to_b = 0
    exception_to_a = 0
    tier4_exception_block = 0
    extreme_exception_block = 0
    market_no_data_a_block = 0

    market_no_data_a_found = 0
    market_extreme_veto_non_skip_found = 0
    market_manufactured_ab_found = 0
    market_hard_veto_old_behavior_restored = 0
    h2h_downgrade_found = 0
    h2h_manufactured_ab_found = 0
    events_manufactured_ab_found = 0
    cpl_changed_official_found = 0
    cpl_touched_live_bet_found = 0
    cpl_touched_validation_found = 0

    common_mismatch = 0
    official_ids_by_scout = set()
    official_ab_ids_by_scout = set()

    for row in scout:
        fid = row.get("fixture_id")
        if isinstance(fid, int) and fid in official_ids:
            official_ids_by_scout.add(fid)
        if isinstance(fid, int) and fid in official_ab_ids:
            official_ab_ids_by_scout.add(fid)

        official = _norm_grade(row.get("official_grade") or row.get("grade")) or "NONE"
        dry_grade, dry_source, reason_code, allowed = _dryrun_grade(row)
        dry_dist[dry_grade] += 1

        delta, delta_reason = _delta(official, dry_grade)

        gate = str(row.get("recent5_bilateral_gate") or "UNKNOWN").upper()
        mode = str(row.get("recent5_bilateral_gate_mode") or "NOT_AVAILABLE").upper()
        gate_cap = str(row.get("recent5_bilateral_gate_cap_action") or "NONE").upper()
        ex_used = _safe_bool(row.get("recent5_bilateral_gate_exception_used"), False)

        if gate == "PASS":
            recent5_pass += 1
        if mode == "HOT_ANCHOR_PASS":
            hot_anchor += 1
        if mode == "DUAL_HEAT_PASS":
            dual_heat += 1
        if gate == "FAIL":
            recent5_fail += 1
        if gate == "FAIL" and gate_cap.startswith("CAP_TO_C"):
            fail_cap_to_c += 1
        if ex_used:
            exception_cnt += 1
            if dry_grade == "B":
                exception_to_b += 1
            if dry_grade == "A":
                exception_to_a += 1

        # explicit block counters
        if _is_market_no_data(row) and _norm_grade(row.get("market_adjusted_shadow_grade")) == "A" and dry_grade != "A":
            market_no_data_a_block += 1

        # exception blocked cases
        if str(row.get("league_tier") or "").upper() == "TIER_4_NON_FORMAL" and gate == "FAIL":
            if dry_grade not in {"A", "B"}:
                tier4_exception_block += 1
        if _is_extreme_veto(row) and gate == "FAIL" and dry_grade == "SKIP":
            extreme_exception_block += 1

        # market safety
        if _is_market_no_data(row) and dry_grade == "A":
            market_no_data_a_found += 1
        if _is_extreme_veto(row) and dry_grade != "SKIP":
            market_extreme_veto_non_skip_found += 1

        source_grade = _norm_grade(row.get("market_adjusted_shadow_grade") or row.get("rf_shadow_grade")) or "SKIP"
        if source_grade not in {"A", "B"} and dry_grade in {"A", "B"}:
            market_manufactured_ab_found += 1

        if str(row.get("opening_market_support_status") or "").upper() == "MARKET_HARD_VETO" and dry_grade == "SKIP":
            market_hard_veto_old_behavior_restored += 1

        # no H2H/Events/CPL-driven promotions in this replay logic
        h2h_status = str(row.get("h2h_recent5_support_status") or "").upper()
        if h2h_status in {"H2H_NO_BONUS", "H2H_LOW_SAMPLE"} and GRADE_RANK.get(dry_grade, 0) < GRADE_RANK.get(source_grade, 0):
            h2h_downgrade_found += 1
        if h2h_status in {"H2H_STRONG_BONUS", "H2H_LIGHT_BONUS"} and source_grade not in {"A", "B"} and dry_grade in {"A", "B"}:
            h2h_manufactured_ab_found += 1

        if _safe_bool(row.get("events_collected"), False) and source_grade not in {"A", "B"} and dry_grade in {"A", "B"}:
            events_manufactured_ab_found += 1

        if _safe_bool(row.get("cpl_collected"), False) and official != (_norm_grade(row.get("official_grade") or row.get("grade")) or "NONE"):
            cpl_changed_official_found += 1

        if _safe_bool(row.get("cpl_collected"), False) and _safe_bool(row.get("live_bet_touched"), False):
            cpl_touched_live_bet_found += 1
        if _safe_bool(row.get("cpl_collected"), False) and _safe_bool(row.get("validation_touched"), False):
            cpl_touched_validation_found += 1

        # common official/shadow mismatch statistics
        if isinstance(fid, int) and fid in official_ids:
            cv_grade = ""
            for bucket, g in ((cv.get("A_candidates") or [], "A"), (cv.get("B_candidates") or [], "B"), (cv.get("C_candidates") or [], "C")):
                if any((x.get("fixture_id") == fid) for x in bucket if isinstance(x, dict)):
                    cv_grade = g
                    break
            if cv_grade and official in {"A", "B", "C"} and cv_grade != official:
                common_mismatch += 1

        in_pending = isinstance(fid, int) and fid in pending_ids

        per_row.append({
            "fixture_id": fid,
            "home": _safe_text(row.get("home"), ""),
            "away": _safe_text(row.get("away"), ""),
            "current_official_grade": official,
            "shadow_dryrun_grade": dry_grade,
            "shadow_dryrun_score": _safe_num(row.get("rf_shadow_score"), 0.0),
            "shadow_dryrun_reason": _safe_text(row.get("rf_shadow_reason")),
            "shadow_dryrun_reason_code": reason_code,
            "shadow_dryrun_source": dry_source,
            "official_vs_shadow_delta": delta,
            "promotion_delta_reason": delta_reason,
            "dryrun_allowed_to_promote": bool(allowed),
            "dryrun_block_reason": "NONE" if allowed else reason_code,
            "recent5_bilateral_gate": gate,
            "recent5_bilateral_gate_mode": mode,
            "recent5_bilateral_gate_reason": _safe_text(row.get("recent5_bilateral_gate_reason")),
            "recent5_bilateral_gate_cap_action": gate_cap,
            "recent5_bilateral_gate_exception_used": ex_used,
            "opening_market_support_status": _safe_text(row.get("opening_market_support_status")),
            "opening_market_conflict_level": _safe_text(row.get("opening_market_conflict_level")),
            "opening_market_data_status": _safe_text(row.get("opening_market_data_status")),
            "h2h_recent5_support_status": _safe_text(row.get("h2h_recent5_support_status")),
            "events_required": _safe_bool(row.get("events_required"), False),
            "events_collected": _safe_bool(row.get("events_collected"), False),
            "cpl_required": _safe_bool(row.get("cpl_required"), False),
            "cpl_collected": _safe_bool(row.get("cpl_collected"), False),
            "is_shadow_only_row": bool(_norm_grade(official) == "" and _norm_grade(dry_grade) in {"A", "B", "C"}),
            "is_pending_bet_candidate": in_pending,
        })

    shadow_only_pending = sum(1 for r in per_row if r["is_shadow_only_row"] and r["is_pending_bet_candidate"])

    official_covered = len(official_ids_by_scout) == len(official_ids)
    official_ab_covered = len(official_ab_ids_by_scout) == len(official_ab_ids)

    report = {
        "schema_version": "v4_rf_shadow_promotion_dryrun_replay.v1",
        "phase": "Phase 3C - V4_RF_SHADOW_PROMOTION_DRYRUN_REPLAY",
        "generated_at": datetime.now().isoformat(),
        "scan_date": date,
        "source": {
            "scout_path": str(SCOUT_DIR / f"scout_v4_{date}.json"),
            "candidate_view_path": str(STATUS_DIR / f"v3v4_dashboard_candidate_view_{date}.json"),
            "source_row_count": len(scout),
        },
        "disclaimer": "DRYRUN/REPLAY ONLY. Not official recommendation. No pending/QQ/cron/validation/live-bet mutation.",
        "distribution": {
            "official_grade": {
                "A": sum(1 for r in per_row if r["current_official_grade"] == "A"),
                "B": sum(1 for r in per_row if r["current_official_grade"] == "B"),
                "C": sum(1 for r in per_row if r["current_official_grade"] == "C"),
                "SKIP": sum(1 for r in per_row if r["current_official_grade"] == "SKIP"),
                "NONE": sum(1 for r in per_row if r["current_official_grade"] == "NONE"),
            },
            "shadow_dryrun_grade": dry_dist,
        },
        "replay_fields_presence": {
            "shadow_dryrun_grade": True,
            "shadow_dryrun_score": True,
            "shadow_dryrun_reason": True,
            "shadow_dryrun_reason_code": True,
            "shadow_dryrun_source": True,
            "current_official_grade": True,
            "official_vs_shadow_delta": True,
            "promotion_delta_reason": True,
            "dryrun_allowed_to_promote": True,
            "dryrun_block_reason": True,
        },
        "recent5_bilateral_gate_stats": {
            "recent5_bilateral_gate_pass_count": recent5_pass,
            "hot_anchor_pass_count": hot_anchor,
            "dual_heat_pass_count": dual_heat,
            "recent5_bilateral_gate_fail_count": recent5_fail,
            "recent5_fail_cap_to_C_count": fail_cap_to_c,
            "rf_strong_confirmed_b_floor_exception_count": exception_cnt,
            "exception_to_B_count": exception_to_b,
            "exception_to_A_count": exception_to_a,
            "tier4_exception_block_count": tier4_exception_block,
            "extreme_veto_exception_block_count": extreme_exception_block,
            "market_no_data_A_block_count": market_no_data_a_block,
        },
        "safety_market_h2h_events_cpl": {
            "market_no_data_A_found": market_no_data_a_found,
            "market_extreme_veto_non_skip_found": market_extreme_veto_non_skip_found,
            "market_manufactured_AB_found": market_manufactured_ab_found,
            "market_hard_veto_old_behavior_restored": market_hard_veto_old_behavior_restored,
            "h2h_downgrade_found": h2h_downgrade_found,
            "h2h_manufactured_AB_found": h2h_manufactured_ab_found,
            "events_manufactured_AB_found": events_manufactured_ab_found,
            "cpl_changed_official_found": cpl_changed_official_found,
            "cpl_touched_live_bet_found": cpl_touched_live_bet_found,
            "cpl_touched_validation_found": cpl_touched_validation_found,
        },
        "coverage": {
            "official_fixture_count": len(official_ids),
            "official_fixture_covered_by_scout_count": len(official_ids_by_scout),
            "official_fixture_coverage_ok": official_covered,
            "official_ab_fixture_count": len(official_ab_ids),
            "official_ab_fixture_covered_by_scout_count": len(official_ab_ids_by_scout),
            "official_ab_fixture_coverage_ok": official_ab_covered,
            "common_fixtures_official_grade_mismatch_count": common_mismatch,
            "shadow_only_rows_entered_pending_count": shadow_only_pending,
        },
        "safety_checks": {
            "official_grade_changed": False,
            "production_grade_mode_changed": False,
            "pending_logic_changed": False,
            "qq_pushed": False,
            "validation_touched": False,
            "live_bet_touched": False,
            "cron_modified": False,
            "api_called": False,
            "full_rescan_executed": False,
        },
        "rows": per_row,
    }
    return report


def write_outputs(report: dict[str, Any], date: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"v4_rf_shadow_promotion_dryrun_replay_{date}.json"
    md_path = OUT_DIR / f"v4_rf_shadow_promotion_dryrun_replay_{date}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    d_off = report["distribution"]["official_grade"]
    d_dry = report["distribution"]["shadow_dryrun_grade"]
    s5 = report["recent5_bilateral_gate_stats"]
    cov = report["coverage"]
    safe = report["safety_market_h2h_events_cpl"]

    lines = [
        f"# V4 RF Shadow Promotion Dryrun Replay ({date})",
        "",
        "> 仅 dryrun/replay 观察，不改变 official，不写 pending，不推 QQ。",
        "",
        "## 总览",
        f"- official: A/B/C/SKIP/NONE = {d_off['A']}/{d_off['B']}/{d_off['C']}/{d_off['SKIP']}/{d_off['NONE']}",
        f"- shadow_dryrun: A/B/C/SKIP = {d_dry['A']}/{d_dry['B']}/{d_dry['C']}/{d_dry['SKIP']}",
        f"- official grade mismatch(common fixtures): {cov['common_fixtures_official_grade_mismatch_count']}",
        "",
        "## recent5 bilateral gate",
        f"- PASS: {s5['recent5_bilateral_gate_pass_count']}",
        f"- HOT_ANCHOR_PASS: {s5['hot_anchor_pass_count']}",
        f"- DUAL_HEAT_PASS: {s5['dual_heat_pass_count']}",
        f"- FAIL: {s5['recent5_bilateral_gate_fail_count']}",
        f"- FAIL cap_to_C: {s5['recent5_fail_cap_to_C_count']}",
        f"- B-floor exception count: {s5['rf_strong_confirmed_b_floor_exception_count']}",
        f"- exception_to_B: {s5['exception_to_B_count']}",
        f"- exception_to_A: {s5['exception_to_A_count']}",
        "",
        "## 风险守卫",
        f"- MARKET_NO_DATA A found: {safe['market_no_data_A_found']}",
        f"- MARKET_EXTREME_VETO non-skip found: {safe['market_extreme_veto_non_skip_found']}",
        f"- market manufactured A/B found: {safe['market_manufactured_AB_found']}",
        f"- H2H manufactured A/B found: {safe['h2h_manufactured_AB_found']}",
        f"- Events manufactured A/B found: {safe['events_manufactured_AB_found']}",
        f"- CPL changed official found: {safe['cpl_changed_official_found']}",
        "",
        "## 覆盖",
        f"- official fixtures covered: {cov['official_fixture_covered_by_scout_count']}/{cov['official_fixture_count']} (ok={cov['official_fixture_coverage_ok']})",
        f"- official A/B covered: {cov['official_ab_fixture_covered_by_scout_count']}/{cov['official_ab_fixture_count']} (ok={cov['official_ab_fixture_coverage_ok']})",
        f"- shadow-only rows entered pending: {cov['shadow_only_rows_entered_pending_count']}",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="YYYYMMDD; default latest scout date")
    args = ap.parse_args()

    date = args.date.strip() or _latest_date()
    report = build_report(date)
    jp, mp = write_outputs(report, date)

    out = {
        "status": "PASS",
        "scan_date": date,
        "json": str(jp),
        "md": str(mp),
        "source_row_count": report["source"]["source_row_count"],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
