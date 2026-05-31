#!/usr/bin/env python3
"""
Phase 3D-F: V4 RF shadow promotion dryrun/replay with field completeness guards.

Read-only only:
- no API calls
- no rescan
- no official mutation
- no pending/QQ/validation/live-bet/cron mutation
"""

from __future__ import annotations

import argparse
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
    if isinstance(v, float) and v != v:
        return default
    s = str(v).strip()
    return s if s else default


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


def _latest_date() -> str:
    files = sorted(SCOUT_DIR.glob("scout_v4_*.json"))
    if not files:
        raise FileNotFoundError("No scout_v4_*.json found")
    return files[-1].stem.split("_")[-1]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_scout(date: str, source_artifact: str | None) -> tuple[list[dict[str, Any]], Path]:
    if source_artifact:
        p = Path(source_artifact)
    else:
        p = SCOUT_DIR / f"scout_v4_{date}.json"
    rows = _load_json(p)
    if not isinstance(rows, list):
        raise ValueError(f"Invalid scout list: {p}")
    return rows, p


def _build_official_map_from_candidate_view(data: dict[str, Any]) -> tuple[dict[int, str], dict[str, Any]]:
    m: dict[int, str] = {}

    for item in (data.get("A_candidates") or []):
        if isinstance(item, dict) and isinstance(item.get("fixture_id"), int):
            m[item["fixture_id"]] = "A"
    for item in (data.get("B_candidates") or []):
        if isinstance(item, dict) and isinstance(item.get("fixture_id"), int):
            m[item["fixture_id"]] = "B"
    for item in (data.get("C_candidates") or []):
        if isinstance(item, dict) and isinstance(item.get("fixture_id"), int):
            m[item["fixture_id"]] = "C"

    dist = {
        "A": int(data.get("A_count") or 0),
        "B": int(data.get("B_count") or 0),
        "C": int(data.get("C_count") or 0),
        "SKIP": int(data.get("SKIP_count") or 0),
    }
    return m, dist


def _resolve_official_artifact(date: str, official_artifact: str | None) -> dict[str, Any]:
    candidates: list[Path] = []
    if official_artifact:
        candidates.append(Path(official_artifact))
    candidates.append(STATUS_DIR / f"v3v4_dashboard_candidate_view_{date}.json")

    for p in candidates:
        if p.exists():
            try:
                d = _load_json(p)
                if isinstance(d, dict):
                    m, dist = _build_official_map_from_candidate_view(d)
                    return {
                        "status": "FOUND",
                        "path": str(p),
                        "map": m,
                        "distribution": dist,
                        "artifact": d,
                    }
            except Exception:
                pass

    return {
        "status": "MISSING",
        "path": "NOT_AVAILABLE",
        "map": {},
        "distribution": "NOT_AVAILABLE",
        "artifact": {},
    }


def _is_market_no_data(row: dict[str, Any]) -> bool:
    s = str(row.get("opening_market_support_status") or "").upper()
    ds = str(row.get("opening_market_data_status") or "").upper()
    return s == "MARKET_NO_DATA" or ds in {"NO_DATA", "API_HAS_ODDS_BUT_NO_HT_OU"}


def _is_no_market(row: dict[str, Any]) -> bool:
    s = str(row.get("opening_market_support_status") or "").upper()
    ds = str(row.get("opening_market_data_status") or "").upper()
    return s == "MARKET_NO_MARKET" or ds == "NO_MARKET" or _safe_bool(row.get("no_market_excluded"), False)


def _is_extreme_veto(row: dict[str, Any]) -> bool:
    c1 = str(row.get("opening_market_conflict_level") or "").upper()
    c2 = str(row.get("opening_market_support_status") or "").upper()
    return c1 == "MARKET_EXTREME_VETO" or c2 == "MARKET_EXTREME_VETO"


def _dryrun_grade(row: dict[str, Any]) -> tuple[str, str, str, bool]:
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
    return source_grade, ("market_adjusted_shadow_grade" if market_grade else "rf_shadow_grade"), "NORMAL_SHADOW_REPLAY", allowed


def _official_shadow_delta(official: str, shadow: str, official_status: str) -> tuple[str, str]:
    o = _norm_grade(official)
    s = _norm_grade(shadow)

    if official_status != "FOUND" and s:
        return "OFFICIAL_MISSING_SHADOW_ONLY", f"official_missing, shadow={s}"
    if official_status != "FOUND" and not s:
        return "OFFICIAL_MISSING_SHADOW_ONLY", "official_missing, shadow_missing"

    if not o and s:
        return "TRUE_SHADOW_ONLY", f"official_empty, shadow={s}"
    if o and not s:
        return "OFFICIAL_TO_SHADOW_DOWNGRADE", f"official={o}, shadow_missing"
    if not o and not s:
        return "OFFICIAL_UNCHANGED", "both_empty"

    ro, rs = GRADE_RANK.get(o, 0), GRADE_RANK.get(s, 0)
    if ro == rs:
        return "OFFICIAL_UNCHANGED", f"official={o}, shadow={s}"
    if rs > ro:
        return "OFFICIAL_TO_SHADOW_UPGRADE", f"official={o}, shadow={s}"
    return "OFFICIAL_TO_SHADOW_DOWNGRADE", f"official={o}, shadow={s}"


def _clamp_count_from_rate(rate: Any, base: int = 5) -> int | None:
    if rate is None:
        return None
    r = _safe_num(rate, -1)
    if r < 0:
        return None
    if r > 1.0 and r <= 5.0:
        c = int(round(r))
    else:
        c = int(round(r * base))
    return max(0, min(base, c))


def _recent10_count(row: dict[str, Any]) -> int | None:
    c10r = row.get("combined_recent10_fh_involved_rate")
    if c10r is not None:
        c = _clamp_count_from_rate(c10r, 10)
        if c is not None:
            return c
    gate = str(row.get("rf_recent10_gate_status") or "")
    if "PASS_7_OF_10" in gate:
        return 7
    if "BREAK_6_OF_10" in gate:
        return 6
    if "OBSERVE_5_OF_10" in gate:
        return 5
    if "BLOCK_LE_4_OF_10" in gate:
        return 4
    return None


def _reconstruct_recent5_gate(row: dict[str, Any]) -> dict[str, Any]:
    # prefer runtime fields
    gate = row.get("recent5_bilateral_gate")
    mode = row.get("recent5_bilateral_gate_mode")
    reason = row.get("recent5_bilateral_gate_reason")
    cap = row.get("recent5_bilateral_gate_cap_action")
    ex = row.get("recent5_bilateral_gate_exception_used")

    if gate is not None:
        return {
            "available": True,
            "reconstructed": False,
            "gate": str(gate).upper(),
            "mode": str(mode or "NOT_AVAILABLE").upper(),
            "reason": _safe_text(reason),
            "cap_action": str(cap or "NONE").upper(),
            "exception_used": _safe_bool(ex, False),
            "missing_fields": [],
            "home_count": _safe_num(row.get("home_recent5_pass_count"), 0),
            "away_count": _safe_num(row.get("away_recent5_pass_count"), 0),
        }

    missing: list[str] = []
    h5 = _clamp_count_from_rate(row.get("home_recent5_fh_involved_rate"), 5)
    a5 = _clamp_count_from_rate(row.get("away_recent5_fh_involved_rate"), 5)
    c10 = _recent10_count(row)

    if h5 is None:
        missing.append("home_recent5_fh_involved_rate")
    if a5 is None:
        missing.append("away_recent5_fh_involved_rate")
    if c10 is None:
        missing.append("combined_recent10_fh_involved_rate/rf_recent10_gate_status")

    if missing:
        return {
            "available": False,
            "reconstructed": False,
            "gate": "UNKNOWN",
            "mode": "NOT_AVAILABLE",
            "reason": "RECENT5_GATE_FIELDS_MISSING",
            "cap_action": "NONE",
            "exception_used": False,
            "missing_fields": missing,
            "home_count": None,
            "away_count": None,
        }

    if c10 < 7:
        return {
            "available": True,
            "reconstructed": True,
            "gate": "UNKNOWN",
            "mode": "NOT_APPLICABLE",
            "reason": "RECENT10_BELOW_GATE_OR_MISSING",
            "cap_action": "NONE",
            "exception_used": False,
            "missing_fields": [],
            "home_count": h5,
            "away_count": a5,
        }

    mode_a_home = h5 == 5 and a5 >= 3
    mode_a_away = a5 == 5 and h5 >= 3
    mode_b = h5 >= 4 and a5 >= 4

    if mode_a_home or mode_a_away:
        return {
            "available": True,
            "reconstructed": True,
            "gate": "PASS",
            "mode": "HOT_ANCHOR_PASS",
            "reason": f"RECENT5_BILATERAL_HEAT_PASS:HOT_ANCHOR_PASS:home={h5},away={a5}",
            "cap_action": "NONE",
            "exception_used": False,
            "missing_fields": [],
            "home_count": h5,
            "away_count": a5,
        }
    if mode_b:
        return {
            "available": True,
            "reconstructed": True,
            "gate": "PASS",
            "mode": "DUAL_HEAT_PASS",
            "reason": f"RECENT5_BILATERAL_HEAT_PASS:DUAL_HEAT_PASS:home={h5},away={a5}",
            "cap_action": "NONE",
            "exception_used": False,
            "missing_fields": [],
            "home_count": h5,
            "away_count": a5,
        }
    return {
        "available": True,
        "reconstructed": True,
        "gate": "FAIL",
        "mode": "RECENT5_BILATERAL_HEAT_FAIL",
        "reason": f"RECENT5_BILATERAL_HEAT_FAIL:home={h5},away={a5}",
        "cap_action": "CAP_TO_C",
        "exception_used": False,
        "missing_fields": [],
        "home_count": h5,
        "away_count": a5,
    }


def _bfloor_reconstructable(row: dict[str, Any], r5: dict[str, Any]) -> tuple[bool, list[str], bool]:
    required = {
        "rf_shadow_score": row.get("rf_shadow_score"),
        "rf_recent10_gate_status": row.get("rf_recent10_gate_status"),
        "rf_balance_driver_level": row.get("rf_balance_driver_level"),
        "rf_balance_status": row.get("rf_balance_status"),
        "opening_market_support_status": row.get("opening_market_support_status"),
        "season_phase": row.get("season_phase"),
        "league_tier": row.get("league_tier"),
        "opening_market_conflict_level": row.get("opening_market_conflict_level"),
        "rf_baseline_only_flag": row.get("rf_baseline_only_flag"),
    }
    miss = [k for k, v in required.items() if v is None or (isinstance(v, str) and not v.strip())]
    if not r5.get("available"):
        miss.append("recent5_bilateral_gate")

    if miss:
        return False, sorted(set(miss)), False

    gate = str(r5.get("gate") or "").upper()
    if gate != "FAIL":
        return True, [], False

    score = _safe_num(row.get("rf_shadow_score"), 0.0)
    r10 = str(row.get("rf_recent10_gate_status") or "")
    bal_lvl = str(row.get("rf_balance_driver_level") or "").upper()
    bal_status = str(row.get("rf_balance_status") or "").upper()
    market = str(row.get("opening_market_support_status") or "").upper()
    phase = str(row.get("season_phase") or "").upper()
    tier = str(row.get("league_tier") or "").upper()
    conflict = str(row.get("opening_market_conflict_level") or "").upper()
    baseline_only = _safe_bool(row.get("rf_baseline_only_flag"), False)

    cond = (
        score >= 73
        and ("PASS_7_OF_10" in r10 or "BREAK_6_OF_10" in r10 or "ENTRY_PASS_10G7" in str(row.get("rf_entry_rule") or ""))
        and (bal_lvl in {"HOT_DRIVER", "STRONG_DRIVER"} or bal_status in {"HOT_DRIVER_ACCEPTABLE", "STRONG_DRIVER_ACCEPTABLE"})
        and market in {"MARKET_CONFIRM", "MARKET_WEAK_CONFIRM", "MARKET_STRONG_CONFIRM"}
        and phase == "ACTIVE_SEASON"
        and tier != "TIER_4_NON_FORMAL"
        and conflict != "MARKET_EXTREME_VETO"
        and market != "MARKET_NO_DATA"
        and not baseline_only
        and phase != "POST_OFFSEASON_RETURN"
    )
    return True, [], cond


def _apply_recent5_bfloor_rescue(
    row: dict[str, Any],
    before_grade: str,
    current_official_grade: str,
    r5: dict[str, Any],
    rescue_threshold: float,
) -> dict[str, Any]:
    out = {
        "after_grade": before_grade,
        "recent5_rescue_to_B": False,
        "recent5_rescue_reason": "NONE",
        "recent5_rescue_block_reason": "NONE",
        "bfloor_rescue_to_B": False,
        "bfloor_rescue_block_reason": "NONE",
        "rescue_to_A": False,
        "blocked_tier4": False,
        "blocked_extreme_veto": False,
        "blocked_baseline_only": False,
        "blocked_market_no_data_a": False,
        "blocked_not_b_baseline": False,
    }

    gate = str(r5.get("gate") or "UNKNOWN").upper()
    if gate != "FAIL":
        out["recent5_rescue_block_reason"] = "RECENT5_GATE_NOT_FAIL"
        out["bfloor_rescue_block_reason"] = "RECENT5_GATE_NOT_FAIL"
        return out

    score = _safe_num(row.get("rf_shadow_score"), 0.0)
    recent10_pass = (_recent10_count(row) or 0) >= 7
    bal_lvl = str(row.get("rf_balance_driver_level") or "").upper()
    bal_status = str(row.get("rf_balance_status") or "").upper()
    balance_ok = bal_lvl in {"HOT_DRIVER", "STRONG_DRIVER"} or bal_status in {"HOT_DRIVER_ACCEPTABLE", "STRONG_DRIVER_ACCEPTABLE"}
    market = str(row.get("opening_market_support_status") or "").upper()
    conflict = str(row.get("opening_market_conflict_level") or "").upper()
    phase = str(row.get("season_phase") or "").upper()
    tier = str(row.get("league_tier") or "").upper()
    baseline_only = _safe_bool(row.get("rf_baseline_only_flag"), False) or phase == "POST_OFFSEASON_RETURN"
    pre_cap_shadow_b = str(row.get("season_aware_shadow_grade_before") or "").upper() == "B"
    r5_status = str(row.get("rf_recent5_grade_status") or "").upper()
    pre_base_shadow_b = (
        recent10_pass
        and ("RECENT5_B_BASE_4_OF_5" in r5_status or "RECENT5_A_BASE_5_OF_5" in r5_status)
    )
    official_b = current_official_grade == "B"
    eligible_base = official_b or pre_cap_shadow_b or pre_base_shadow_b

    if not eligible_base:
        out["recent5_rescue_block_reason"] = "NOT_B_BASELINE"
        out["bfloor_rescue_block_reason"] = "NOT_B_BASELINE"
        out["blocked_not_b_baseline"] = True
        return out

    if tier == "TIER_4_NON_FORMAL":
        out["recent5_rescue_block_reason"] = "TIER4_BLOCKED"
        out["bfloor_rescue_block_reason"] = "TIER4_BLOCKED"
        out["blocked_tier4"] = True
        return out

    if conflict == "MARKET_EXTREME_VETO":
        out["recent5_rescue_block_reason"] = "MARKET_EXTREME_VETO_BLOCKED"
        out["bfloor_rescue_block_reason"] = "MARKET_EXTREME_VETO_BLOCKED"
        out["blocked_extreme_veto"] = True
        return out

    if baseline_only:
        out["recent5_rescue_block_reason"] = "BASELINE_ONLY_BLOCKED"
        out["bfloor_rescue_block_reason"] = "BASELINE_ONLY_BLOCKED"
        out["blocked_baseline_only"] = True
        return out

    if market == "MARKET_NO_DATA":
        out["recent5_rescue_block_reason"] = "MARKET_NO_DATA_BLOCKED"
        out["bfloor_rescue_block_reason"] = "MARKET_NO_DATA_BLOCKED"
        out["blocked_market_no_data_a"] = True
        return out

    if phase != "ACTIVE_SEASON":
        out["recent5_rescue_block_reason"] = "SEASON_NOT_ACTIVE"
        out["bfloor_rescue_block_reason"] = "SEASON_NOT_ACTIVE"
        return out

    if before_grade == "SKIP" and not pre_cap_shadow_b:
        out["recent5_rescue_block_reason"] = "SKIP_NOT_PRECAP_B"
        out["bfloor_rescue_block_reason"] = "SKIP_NOT_PRECAP_B"
        return out

    market_confirm = market in {"MARKET_STRONG_CONFIRM", "MARKET_CONFIRM"}
    if score >= rescue_threshold and recent10_pass and market_confirm and balance_ok and before_grade == "C":
        out["after_grade"] = "B"
        out["recent5_rescue_to_B"] = True
        out["bfloor_rescue_to_B"] = True
        out["recent5_rescue_reason"] = "RECENT5_BILATERAL_GATE_FAIL_BUT_RF_STRONG_CONFIRMED_RESCUE"
        out["recent5_rescue_block_reason"] = "NONE"
        out["bfloor_rescue_block_reason"] = "NONE"
        return out

    if score >= 80.0 and market == "MARKET_STRONG_CONFIRM" and recent10_pass and before_grade == "C":
        out["after_grade"] = "B"
        out["recent5_rescue_to_B"] = True
        out["bfloor_rescue_to_B"] = True
        out["recent5_rescue_reason"] = "RECENT5_FAIL_HIGH_RF_STRONG_MARKET_RESCUE_TO_B"
        out["recent5_rescue_block_reason"] = "NONE"
        out["bfloor_rescue_block_reason"] = "NONE"
        return out

    if score < rescue_threshold:
        threshold_tag = str(rescue_threshold).rstrip("0").rstrip(".")
        out["recent5_rescue_block_reason"] = f"RF_SCORE_BELOW_{threshold_tag}"
        out["bfloor_rescue_block_reason"] = f"RF_SCORE_BELOW_{threshold_tag}"
    elif not recent10_pass:
        out["recent5_rescue_block_reason"] = "RECENT10_NOT_PASS"
        out["bfloor_rescue_block_reason"] = "RECENT10_NOT_PASS"
    elif not market_confirm:
        out["recent5_rescue_block_reason"] = "MARKET_NOT_CONFIRM"
        out["bfloor_rescue_block_reason"] = "MARKET_NOT_CONFIRM"
    elif not balance_ok:
        out["recent5_rescue_block_reason"] = "BALANCE_NOT_STRONG"
        out["bfloor_rescue_block_reason"] = "BALANCE_NOT_STRONG"
    elif before_grade != "C":
        out["recent5_rescue_block_reason"] = "NO_C_TO_B_PATH"
        out["bfloor_rescue_block_reason"] = "NO_C_TO_B_PATH"
    else:
        out["recent5_rescue_block_reason"] = "RESCUE_CONDITION_NOT_MET"
        out["bfloor_rescue_block_reason"] = "RESCUE_CONDITION_NOT_MET"

    if out["after_grade"] == "A":
        out["after_grade"] = "B"
        out["rescue_to_A"] = True
    return out


def _coverage_status(available: int, unknown: int) -> str:
    if available <= 0 and unknown > 0:
        return "MISSING"
    if available > 0 and unknown > 0:
        return "PARTIAL"
    return "COMPLETE"


def build_report(
    date: str,
    source_artifact: str | None,
    official_artifact: str | None,
    strict_field_coverage: bool,
    rescue_threshold: float = 77.0,
) -> dict[str, Any]:
    scout, scout_path = _load_scout(date, source_artifact)
    official = _resolve_official_artifact(date, official_artifact)

    pending_ids: set[int] = set()
    if official["status"] == "FOUND":
        for item in (official.get("artifact", {}).get("pending_bet_candidates") or []):
            if isinstance(item, dict) and isinstance(item.get("fixture_id"), int):
                pending_ids.add(item["fixture_id"])

    off_map: dict[int, str] = official["map"]
    off_dist = official["distribution"]

    rows_out: list[dict[str, Any]] = []
    shadow_before_dist = {"A": 0, "B": 0, "C": 0, "SKIP": 0}
    shadow_after_dist = {"A": 0, "B": 0, "C": 0, "SKIP": 0}
    delta_dist: dict[str, int] = {}

    # recent5 coverage counters
    recent5_available = 0
    recent5_unknown = 0
    recent5_missing_fields: set[str] = set()

    recent5_pass = 0
    hot_anchor = 0
    dual_heat = 0
    recent5_fail = 0
    fail_cap_to_c = 0

    # b-floor coverage counters
    bfloor_available = 0
    bfloor_unknown = 0
    bfloor_missing_fields: set[str] = set()
    bfloor_exception_cnt = 0
    exception_to_b = 0
    exception_to_a = 0
    tier4_exception_block = 0
    extreme_exception_block = 0
    market_no_data_a_block = 0
    bfloor_detected_noop_count = 0
    bfloor_detected_blocked_count = 0
    bfloor_detected_rescued_count = 0

    recent5_rescue_to_b_count = 0
    rescue_to_a_count = 0
    rescue_blocked_tier4_count = 0
    rescue_blocked_extreme_veto_count = 0
    rescue_blocked_baseline_only_count = 0
    rescue_blocked_market_no_data_a_count = 0
    bfloor_rescue_to_b_count = 0

    # safety counters
    market_unknown = h2h_unknown = events_unknown = cpl_unknown = 0
    safety_missing_fields: set[str] = set()

    market_no_data_a_found = 0
    market_extreme_veto_non_skip_found = 0
    market_assisted_rescue_to_b_count = 0
    market_assisted_rescue_to_b_list: list[int] = []
    market_alone_manufactured_ab_count = 0
    market_alone_manufactured_ab_list: list[int] = []
    market_hard_veto_old_behavior_restored = 0
    h2h_downgrade_found = 0
    h2h_manufactured_ab_found = 0
    events_manufactured_ab_found = 0
    cpl_changed_official_found = 0
    cpl_touched_live_bet_found = 0
    cpl_touched_validation_found = 0

    official_missing_count = 0

    official_fixture_ids = set(off_map.keys()) if official["status"] == "FOUND" else set()
    official_ab_fixture_ids = {k for k, v in off_map.items() if v in {"A", "B"}} if official["status"] == "FOUND" else set()
    scout_fixture_ids = {r.get("fixture_id") for r in scout if isinstance(r.get("fixture_id"), int)}

    for row in scout:
        fid = row.get("fixture_id")

        if official["status"] == "FOUND":
            if isinstance(fid, int) and fid in off_map:
                current_official = off_map[fid]
            else:
                # candidate_view lists A/B/C explicitly; others are treated as SKIP in official candidate universe.
                current_official = "SKIP"
        else:
            current_official = "NOT_AVAILABLE"
            official_missing_count += 1

        dry_grade_before, dry_source, dry_code, allowed_before = _dryrun_grade(row)
        shadow_before_dist[dry_grade_before] += 1

        # recent5 gate coverage/reconstruction
        r5 = _reconstruct_recent5_gate(row)
        if r5["available"]:
            recent5_available += 1
        else:
            recent5_unknown += 1
            recent5_missing_fields.update(r5.get("missing_fields") or [])

        gate = str(r5["gate"] or "UNKNOWN").upper()
        mode = str(r5["mode"] or "NOT_AVAILABLE").upper()
        cap = str(r5["cap_action"] or "NONE").upper()

        if gate == "PASS":
            recent5_pass += 1
        if mode == "HOT_ANCHOR_PASS":
            hot_anchor += 1
        if mode == "DUAL_HEAT_PASS":
            dual_heat += 1
        if gate == "FAIL":
            recent5_fail += 1
        if gate == "FAIL" and cap.startswith("CAP_TO_C"):
            fail_cap_to_c += 1

        # b-floor coverage
        bf_ok, bf_miss, bf_exception = _bfloor_reconstructable(row, r5)
        if bf_ok:
            bfloor_available += 1
        else:
            bfloor_unknown += 1
            bfloor_missing_fields.update(bf_miss)

        if bf_exception:
            bfloor_exception_cnt += 1

        # apply shadow-only tuning rescue
        rescue = _apply_recent5_bfloor_rescue(
            row=row,
            before_grade=dry_grade_before,
            current_official_grade=current_official,
            r5=r5,
            rescue_threshold=rescue_threshold,
        )
        dry_grade = str(rescue["after_grade"])
        allowed = dry_grade in {"A", "B"}
        shadow_after_dist[dry_grade] += 1

        if rescue["recent5_rescue_to_B"]:
            recent5_rescue_to_b_count += 1
        if rescue["bfloor_rescue_to_B"]:
            bfloor_rescue_to_b_count += 1
        if rescue["rescue_to_A"]:
            rescue_to_a_count += 1
        if rescue["blocked_tier4"]:
            rescue_blocked_tier4_count += 1
        if rescue["blocked_extreme_veto"]:
            rescue_blocked_extreme_veto_count += 1
        if rescue["blocked_baseline_only"]:
            rescue_blocked_baseline_only_count += 1
        if rescue["blocked_market_no_data_a"]:
            rescue_blocked_market_no_data_a_count += 1

        if bf_exception:
            if rescue["bfloor_rescue_to_B"]:
                exception_to_b += 1
                bfloor_detected_rescued_count += 1
            elif rescue["bfloor_rescue_block_reason"] not in {"NONE", "RECENT5_GATE_NOT_FAIL"}:
                bfloor_detected_blocked_count += 1
            else:
                bfloor_detected_noop_count += 1

        if dry_grade == "A" and rescue["recent5_rescue_to_B"]:
            exception_to_a += 1

        delta, delta_reason = _official_shadow_delta(current_official, dry_grade, official["status"])
        delta_dist[delta] = delta_dist.get(delta, 0) + 1

        # explicit blocks
        if str(row.get("league_tier") or "").upper() == "TIER_4_NON_FORMAL" and gate == "FAIL" and dry_grade not in {"A", "B"}:
            tier4_exception_block += 1
        if _is_extreme_veto(row) and gate == "FAIL" and dry_grade == "SKIP":
            extreme_exception_block += 1
        if _is_market_no_data(row) and _norm_grade(row.get("market_adjusted_shadow_grade")) == "A" and dry_grade != "A":
            market_no_data_a_block += 1

        # safety coverage status per row
        market_required = ["opening_market_support_status", "opening_market_data_status", "opening_market_conflict_level"]
        h2h_required = ["h2h_recent5_support_status"]
        events_required = ["events_required", "events_collected"]
        cpl_required = ["cpl_required", "cpl_collected"]

        def _row_missing(fields: list[str]) -> list[str]:
            miss = []
            for f in fields:
                v = row.get(f)
                if v is None or (isinstance(v, str) and not v.strip()):
                    miss.append(f)
            return miss

        mm = _row_missing(market_required)
        hm = _row_missing(h2h_required)
        em = _row_missing(events_required)
        cm = _row_missing(cpl_required)
        if mm:
            market_unknown += 1
            safety_missing_fields.update(mm)
        if hm:
            h2h_unknown += 1
            safety_missing_fields.update(hm)
        if em:
            events_unknown += 1
            safety_missing_fields.update(em)
        if cm:
            cpl_unknown += 1
            safety_missing_fields.update(cm)

        # safety behavior counters
        source_grade = _norm_grade(row.get("market_adjusted_shadow_grade") or row.get("rf_shadow_grade")) or "SKIP"

        if _is_market_no_data(row) and dry_grade == "A":
            market_no_data_a_found += 1
        if _is_extreme_veto(row) and dry_grade != "SKIP":
            market_extreme_veto_non_skip_found += 1
        if source_grade not in {"A", "B"} and dry_grade in {"A", "B"}:
            # Split legal market-assisted rescue (C->B under RF-strong boundaries)
            # from illegal market-alone manufactured A/B.
            is_legal_market_assisted_rescue = bool(rescue["recent5_rescue_to_B"]) and dry_grade == "B"
            if is_legal_market_assisted_rescue:
                market_assisted_rescue_to_b_count += 1
                if isinstance(fid, int):
                    market_assisted_rescue_to_b_list.append(fid)
            else:
                market_alone_manufactured_ab_count += 1
                if isinstance(fid, int):
                    market_alone_manufactured_ab_list.append(fid)
        if str(row.get("opening_market_support_status") or "").upper() == "MARKET_HARD_VETO" and dry_grade == "SKIP":
            market_hard_veto_old_behavior_restored += 1

        h2h_status = str(row.get("h2h_recent5_support_status") or "").upper()
        if h2h_status in {"H2H_NO_BONUS", "H2H_LOW_SAMPLE"} and GRADE_RANK.get(dry_grade, 0) < GRADE_RANK.get(source_grade, 0):
            h2h_downgrade_found += 1
        if (
            h2h_status in {"H2H_STRONG_BONUS", "H2H_LIGHT_BONUS"}
            and source_grade not in {"A", "B"}
            and dry_grade in {"A", "B"}
            and not rescue["recent5_rescue_to_B"]
        ):
            h2h_manufactured_ab_found += 1

        if (
            _safe_bool(row.get("events_collected"), False)
            and source_grade not in {"A", "B"}
            and dry_grade in {"A", "B"}
            and not rescue["recent5_rescue_to_B"]
        ):
            events_manufactured_ab_found += 1

        if _safe_bool(row.get("cpl_collected"), False) and _norm_grade(current_official) != _norm_grade(current_official):
            cpl_changed_official_found += 1
        if _safe_bool(row.get("cpl_collected"), False) and _safe_bool(row.get("live_bet_touched"), False):
            cpl_touched_live_bet_found += 1
        if _safe_bool(row.get("cpl_collected"), False) and _safe_bool(row.get("validation_touched"), False):
            cpl_touched_validation_found += 1

        is_shadow_only = (official["status"] == "FOUND" and current_official in {"", "NONE", "NOT_AVAILABLE"} and dry_grade in {"A", "B", "C"})
        in_pending = isinstance(fid, int) and fid in pending_ids

        rows_out.append({
            "fixture_id": fid,
            "home": _safe_text(row.get("home"), ""),
            "away": _safe_text(row.get("away"), ""),
            "current_official_grade": current_official,
            "shadow_dryrun_grade": dry_grade,
            "shadow_dryrun_grade_before_tuning": dry_grade_before,
            "shadow_dryrun_grade_after_tuning": dry_grade,
            "shadow_dryrun_score": _safe_num(row.get("rf_shadow_score"), 0.0),
            "shadow_dryrun_reason": _safe_text(row.get("rf_shadow_reason")),
            "shadow_dryrun_reason_code": dry_code,
            "shadow_dryrun_source": dry_source,
            "official_vs_shadow_delta": delta,
            "promotion_delta_reason": delta_reason,
            "dryrun_allowed_to_promote": bool(allowed),
            "dryrun_block_reason": "NONE" if allowed else dry_code,
            "recent5_bilateral_gate": gate,
            "recent5_bilateral_gate_mode": mode,
            "recent5_bilateral_gate_reason": _safe_text(r5.get("reason")),
            "recent5_bilateral_gate_cap_action": cap,
            "recent5_bilateral_gate_exception_used": bool(r5.get("exception_used")),
            "recent5_rescue_to_B": bool(rescue["recent5_rescue_to_B"]),
            "recent5_rescue_reason": str(rescue["recent5_rescue_reason"]),
            "recent5_rescue_block_reason": str(rescue["recent5_rescue_block_reason"]),
            "bfloor_rescue_to_B": bool(rescue["bfloor_rescue_to_B"]),
            "bfloor_rescue_block_reason": str(rescue["bfloor_rescue_block_reason"]),
            "is_shadow_only_row": bool(is_shadow_only),
            "is_pending_bet_candidate": in_pending,
        })

    shadow_only_pending = sum(1 for r in rows_out if r["is_shadow_only_row"] and r["is_pending_bet_candidate"])

    def _transition_count(official_g: str, shadow_g: str, field: str) -> int:
        return sum(
            1
            for r in rows_out
            if str(r.get("current_official_grade") or "").upper() == official_g
            and str(r.get(field) or "").upper() == shadow_g
        )

    b_to_c_before = _transition_count("B", "C", "shadow_dryrun_grade_before_tuning")
    b_to_c_after = _transition_count("B", "C", "shadow_dryrun_grade_after_tuning")
    b_to_b_before = _transition_count("B", "B", "shadow_dryrun_grade_before_tuning")
    b_to_b_after = _transition_count("B", "B", "shadow_dryrun_grade_after_tuning")
    skip_to_b_after = _transition_count("SKIP", "B", "shadow_dryrun_grade_after_tuning")
    skip_to_c_after = _transition_count("SKIP", "C", "shadow_dryrun_grade_after_tuning")

    safety_violations_count = (
        market_no_data_a_found
        + market_extreme_veto_non_skip_found
        + market_alone_manufactured_ab_count
        + h2h_manufactured_ab_found
        + events_manufactured_ab_found
        + cpl_changed_official_found
        + cpl_touched_live_bet_found
        + cpl_touched_validation_found
        + rescue_to_a_count
    )

    market_rescue_safety_status = "CLEAN" if market_alone_manufactured_ab_count == 0 else "VIOLATION"
    market_rescue_naming_status = "RENAMED_SPLIT_ACTIVE"
    market_manufactured_ab_found_legacy_alias = market_assisted_rescue_to_b_count

    recent5_cov_status = _coverage_status(recent5_available, recent5_unknown)
    bfloor_cov_status = _coverage_status(bfloor_available, bfloor_unknown)

    market_cov_status = _coverage_status(len(scout) - market_unknown, market_unknown)
    h2h_cov_status = _coverage_status(len(scout) - h2h_unknown, h2h_unknown)
    events_cov_status = _coverage_status(len(scout) - events_unknown, events_unknown)
    cpl_cov_status = _coverage_status(len(scout) - cpl_unknown, cpl_unknown)

    safety_unknown_count = market_unknown + h2h_unknown + events_unknown + cpl_unknown
    safety_cov_status = "COMPLETE" if all(x == "COMPLETE" for x in [market_cov_status, h2h_cov_status, events_cov_status, cpl_cov_status]) else "PARTIAL"

    official_cov_status = "COMPLETE" if official["status"] == "FOUND" else "MISSING"

    source_row_count = len(scout)
    sample_sufficient = source_row_count >= 50

    if not sample_sufficient:
        final_conclusion = "FAIL_NEED_CODE_REVIEW"
    elif official["status"] != "FOUND":
        final_conclusion = "OFFICIAL_ARTIFACT_MISSING_BLOCKER"
    elif recent5_cov_status != "COMPLETE":
        final_conclusion = "RECENT5_GATE_COVERAGE_INCOMPLETE_BLOCKER" if strict_field_coverage else "SUFFICIENT_SAMPLE_BUT_FIELD_COVERAGE_INCOMPLETE"
    elif bfloor_cov_status != "COMPLETE" or safety_cov_status != "COMPLETE":
        final_conclusion = "SUFFICIENT_SAMPLE_BUT_FIELD_COVERAGE_INCOMPLETE"
    else:
        final_conclusion = "SUFFICIENT_SAMPLE_REPLAY_BASELINE_READY"

    report = {
        "schema_version": "v4_rf_shadow_promotion_dryrun_replay.v2",
        "phase": "Phase 3D-F - V4_RF_SHADOW_PROMOTION_REPLAY_FIELD_COMPLETENESS_FIX",
        "generated_at": datetime.now().isoformat(),
        "scan_date": date,
        "strict_field_coverage": bool(strict_field_coverage),
        "rescue_threshold": rescue_threshold,
        "source": {
            "scout_path": str(scout_path),
            "source_row_count": source_row_count,
            "sample_status": "SAMPLE_SUFFICIENT" if sample_sufficient else "SAMPLE_INSUFFICIENT",
        },
        "official_artifact": {
            "official_artifact_path": official["path"],
            "official_artifact_status": official["status"],
            "official_field_coverage_status": official_cov_status,
            "official_missing_count": official_missing_count,
            "current_official_grade_distribution": off_dist,
        },
        "distribution": {
            "shadow_dryrun_grade_before_tuning": shadow_before_dist,
            "shadow_dryrun_grade_after_tuning": shadow_after_dist,
            "shadow_dryrun_grade": shadow_after_dist,
            "official_vs_shadow_delta": delta_dist,
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
        "recent5_coverage": {
            "recent5_gate_field_coverage_status": recent5_cov_status,
            "recent5_gate_reconstructable": recent5_unknown == 0,
            "recent5_gate_available_count": recent5_available,
            "recent5_gate_unknown_count": recent5_unknown,
            "recent5_gate_missing_fields": sorted(recent5_missing_fields),
        },
        "recent5_bilateral_gate_stats": {
            "recent5_bilateral_gate_pass_count": recent5_pass,
            "hot_anchor_pass_count": hot_anchor,
            "dual_heat_pass_count": dual_heat,
            "recent5_bilateral_gate_fail_count": recent5_fail,
            "recent5_fail_cap_to_C_count": fail_cap_to_c,
            "recent5_rescue_to_B_count": recent5_rescue_to_b_count,
            "recent5_rescue_blocked_tier4_count": rescue_blocked_tier4_count,
            "recent5_rescue_blocked_extreme_veto_count": rescue_blocked_extreme_veto_count,
            "recent5_rescue_blocked_baseline_only_count": rescue_blocked_baseline_only_count,
            "recent5_rescue_blocked_market_no_data_A_count": rescue_blocked_market_no_data_a_count,
        },
        "bfloor_coverage": {
            "bfloor_exception_field_coverage_status": bfloor_cov_status,
            "bfloor_exception_available_count": bfloor_available,
            "bfloor_exception_unknown_count": bfloor_unknown,
            "bfloor_exception_missing_fields": sorted(bfloor_missing_fields),
        },
        "bfloor_stats": {
            "rf_strong_confirmed_b_floor_exception_count": bfloor_exception_cnt,
            "exception_to_B_count": exception_to_b,
            "exception_to_A_count": exception_to_a,
            "tier4_exception_block_count": tier4_exception_block,
            "extreme_veto_exception_block_count": extreme_exception_block,
            "market_no_data_A_block_count": market_no_data_a_block,
            "bfloor_rescue_to_B_count": bfloor_rescue_to_b_count,
            "bfloor_detected_but_noop_count": bfloor_detected_noop_count,
            "bfloor_detected_blocked_count": bfloor_detected_blocked_count,
            "bfloor_detected_rescued_count": bfloor_detected_rescued_count,
            "rescue_to_A_count": rescue_to_a_count,
        },
        "safety_coverage": {
            "safety_field_coverage_status": safety_cov_status,
            "market_safety_coverage_status": market_cov_status,
            "h2h_safety_coverage_status": h2h_cov_status,
            "events_safety_coverage_status": events_cov_status,
            "cpl_safety_coverage_status": cpl_cov_status,
            "safety_unknown_count": safety_unknown_count,
            "safety_missing_fields": sorted(safety_missing_fields),
        },
        "safety_market_h2h_events_cpl": {
            "market_no_data_A_found": market_no_data_a_found,
            "market_extreme_veto_non_skip_found": market_extreme_veto_non_skip_found,
            "market_assisted_rescue_to_B_count": market_assisted_rescue_to_b_count,
            "market_assisted_rescue_to_B_list": sorted(market_assisted_rescue_to_b_list),
            "market_alone_manufactured_AB_count": market_alone_manufactured_ab_count,
            "market_alone_manufactured_AB_list": sorted(market_alone_manufactured_ab_list),
            "market_rescue_safety_status": market_rescue_safety_status,
            "market_rescue_naming_status": market_rescue_naming_status,
            "market_manufactured_AB_found": market_manufactured_ab_found_legacy_alias,
            "market_manufactured_AB_found_deprecated": True,
            "market_hard_veto_old_behavior_restored": market_hard_veto_old_behavior_restored,
            "h2h_downgrade_found": h2h_downgrade_found,
            "h2h_manufactured_AB_found": h2h_manufactured_ab_found,
            "events_manufactured_AB_found": events_manufactured_ab_found,
            "cpl_changed_official_found": cpl_changed_official_found,
            "cpl_touched_live_bet_found": cpl_touched_live_bet_found,
            "cpl_touched_validation_found": cpl_touched_validation_found,
        },
        "coverage": {
            "official_fixture_count": len(official_fixture_ids),
            "official_fixture_covered_by_scout_count": len(official_fixture_ids & scout_fixture_ids),
            "official_fixture_coverage_ok": len(official_fixture_ids & scout_fixture_ids) == len(official_fixture_ids) if official["status"] == "FOUND" else False,
            "official_ab_fixture_count": len(official_ab_fixture_ids),
            "official_ab_fixture_covered_by_scout_count": len(official_ab_fixture_ids & scout_fixture_ids),
            "official_ab_fixture_coverage_ok": len(official_ab_fixture_ids & scout_fixture_ids) == len(official_ab_fixture_ids) if official["status"] == "FOUND" else False,
            "shadow_only_rows_entered_pending_count": shadow_only_pending,
            "b_to_c_before": b_to_c_before,
            "b_to_c_after": b_to_c_after,
            "b_to_b_before": b_to_b_before,
            "b_to_b_after": b_to_b_after,
            "skip_to_b_after": skip_to_b_after,
            "skip_to_c_after": skip_to_c_after,
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
        "final_replay_conclusion": final_conclusion,
        "tuning_summary": {
            "official_ab_cap": int(off_dist["A"]) + int(off_dist["B"]) if isinstance(off_dist, dict) else "NOT_AVAILABLE",
            "shadow_ab_before": shadow_before_dist["A"] + shadow_before_dist["B"],
            "shadow_ab_after": shadow_after_dist["A"] + shadow_after_dist["B"],
            "shadow_a_before": shadow_before_dist["A"],
            "shadow_a_after": shadow_after_dist["A"],
            "safety_violations_count": safety_violations_count,
            "market_assisted_rescue_to_B_count": market_assisted_rescue_to_b_count,
            "market_alone_manufactured_AB_count": market_alone_manufactured_ab_count,
        },
        "rows": rows_out,
        "disclaimer": "DRYRUN/REPLAY ONLY. No official/pending/QQ mutation.",
    }
    return report


def _threshold_tag(v: float) -> str:
    return str(v).rstrip("0").rstrip(".")


def _threshold_summary(report: dict[str, Any]) -> dict[str, Any]:
    off_dist = report.get("official_artifact", {}).get("current_official_grade_distribution", {})
    after = report.get("distribution", {}).get("shadow_dryrun_grade_after_tuning", {})
    cov = report.get("coverage", {})
    bfs = report.get("bfloor_stats", {})
    s5s = report.get("recent5_bilateral_gate_stats", {})
    safety = report.get("safety_market_h2h_events_cpl", {})

    rescued_rows = [
        {
            "fixture_id": r.get("fixture_id"),
            "home": r.get("home"),
            "away": r.get("away"),
            "shadow_dryrun_grade_after_tuning": r.get("shadow_dryrun_grade_after_tuning"),
            "recent5_rescue_reason": r.get("recent5_rescue_reason"),
            "bfloor_rescue_block_reason": r.get("bfloor_rescue_block_reason"),
        }
        for r in (report.get("rows") or [])
        if isinstance(r, dict) and bool(r.get("recent5_rescue_to_B"))
    ]

    return {
        "official_A_B_C_SKIP": {
            "A": int((off_dist or {}).get("A", 0)) if isinstance(off_dist, dict) else 0,
            "B": int((off_dist or {}).get("B", 0)) if isinstance(off_dist, dict) else 0,
            "C": int((off_dist or {}).get("C", 0)) if isinstance(off_dist, dict) else 0,
            "SKIP": int((off_dist or {}).get("SKIP", 0)) if isinstance(off_dist, dict) else 0,
        },
        "shadow_A_B_C_SKIP": {
            "A": int((after or {}).get("A", 0)),
            "B": int((after or {}).get("B", 0)),
            "C": int((after or {}).get("C", 0)),
            "SKIP": int((after or {}).get("SKIP", 0)),
        },
        "B_to_C": int(cov.get("b_to_c_after") or 0),
        "B_to_B": int(cov.get("b_to_b_after") or 0),
        "rescue_to_B_count": int(s5s.get("recent5_rescue_to_B_count") or 0),
        "rescue_to_A_count": int(bfs.get("rescue_to_A_count") or 0),
        "SKIP_to_B_count": int(cov.get("skip_to_b_after") or 0),
        "market_assisted_rescue_to_B_count": int(safety.get("market_assisted_rescue_to_B_count") or 0),
        "market_alone_manufactured_AB_count": int(safety.get("market_alone_manufactured_AB_count") or 0),
        "safety_violations_count": int(report.get("tuning_summary", {}).get("safety_violations_count") or 0),
        "rescued_fixture_list": rescued_rows,
        "market_alone_manufactured_AB_list": list(safety.get("market_alone_manufactured_AB_list") or []),
    }


def build_sensitivity_report(
    date: str,
    source_artifact: str | None,
    official_artifact: str | None,
    strict_field_coverage: bool,
    thresholds: list[float],
) -> dict[str, Any]:
    uniq_thresholds: list[float] = []
    for t in thresholds:
        if t not in uniq_thresholds:
            uniq_thresholds.append(t)
    if 77.0 not in uniq_thresholds:
        uniq_thresholds.insert(0, 77.0)

    threshold_results: dict[str, dict[str, Any]] = {}
    default_tag = _threshold_tag(77.0)

    for t in uniq_thresholds:
        tag = _threshold_tag(t)
        rep = build_report(
            date=date,
            source_artifact=source_artifact,
            official_artifact=official_artifact,
            strict_field_coverage=strict_field_coverage,
            rescue_threshold=float(t),
        )
        threshold_results[tag] = {
            "rescue_threshold": float(t),
            "summary": _threshold_summary(rep),
            "final_replay_conclusion": rep.get("final_replay_conclusion"),
            "official_vs_shadow_delta": rep.get("distribution", {}).get("official_vs_shadow_delta", {}),
            "safety_checks": rep.get("safety_checks", {}),
        }

    default_rescue_ids = {
        int(x.get("fixture_id"))
        for x in threshold_results[default_tag]["summary"]["rescued_fixture_list"]
        if isinstance(x, dict) and isinstance(x.get("fixture_id"), int)
    }

    for tag, item in threshold_results.items():
        cur_ids = {
            int(x.get("fixture_id"))
            for x in item["summary"]["rescued_fixture_list"]
            if isinstance(x, dict) and isinstance(x.get("fixture_id"), int)
        }
        new_ids = sorted(cur_ids - default_rescue_ids)
        new_rows = [
            r for r in item["summary"]["rescued_fixture_list"]
            if isinstance(r, dict) and isinstance(r.get("fixture_id"), int) and int(r["fixture_id"]) in new_ids
        ]
        risk_flags = []
        if item["summary"]["rescue_to_A_count"] > 0:
            risk_flags.append("RESCUE_TO_A_NONZERO")
        if item["summary"]["SKIP_to_B_count"] > 0:
            risk_flags.append("SKIP_TO_B_NONZERO")
        if item["summary"]["market_alone_manufactured_AB_count"] > 0:
            risk_flags.append("MARKET_ALONE_MANUFACTURED_AB_NONZERO")
        if item["summary"]["safety_violations_count"] > 0:
            risk_flags.append("SAFETY_VIOLATIONS_NONZERO")
        item["new_rescues_vs_default"] = new_rows
        item["new_risk_fixture_list"] = list(item["summary"]["market_alone_manufactured_AB_list"])
        item["risk_flags"] = risk_flags

    return {
        "schema_version": "v4_rf_shadow_promotion_dryrun_replay.sensitivity.v1",
        "phase": "Phase 3H - V4_RESCUE_THRESHOLD_SENSITIVITY_REPLAY_SHADOW_ONLY",
        "generated_at": datetime.now().isoformat(),
        "scan_date": date,
        "strict_field_coverage": bool(strict_field_coverage),
        "default_rescue_threshold": 77.0,
        "sensitivity_thresholds": [float(t) for t in uniq_thresholds],
        "threshold_results": threshold_results,
        "disclaimer": "SENSITIVITY REPLAY ONLY. No official/pending/QQ mutation.",
    }


def write_outputs(report: dict[str, Any], date: str, sensitivity: bool = False) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if sensitivity:
        json_path = OUT_DIR / f"v4_rf_shadow_promotion_dryrun_replay_sensitivity_{date}.json"
        md_path = OUT_DIR / f"v4_rf_shadow_promotion_dryrun_replay_sensitivity_{date}.md"
    else:
        json_path = OUT_DIR / f"v4_rf_shadow_promotion_dryrun_replay_{date}.json"
        md_path = OUT_DIR / f"v4_rf_shadow_promotion_dryrun_replay_{date}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if sensitivity:
        lines = [
            f"# V4 RF Shadow Promotion Sensitivity Replay ({date})",
            "",
            "> shadow-only threshold sensitivity。不是 official promotion，不写 pending，不推 QQ。",
            "",
            f"- default_rescue_threshold: {report.get('default_rescue_threshold')}",
            f"- thresholds: {', '.join(str(x) for x in report.get('sensitivity_thresholds', []))}",
            "",
            "## per-threshold summary",
        ]
        for tag, item in (report.get("threshold_results") or {}).items():
            s = item.get("summary") or {}
            sh = s.get("shadow_A_B_C_SKIP") or {}
            off = s.get("official_A_B_C_SKIP") or {}
            lines.extend([
                f"- threshold={tag}:",
                f"  - official A/B/C/SKIP = {off.get('A',0)}/{off.get('B',0)}/{off.get('C',0)}/{off.get('SKIP',0)}",
                f"  - shadow  A/B/C/SKIP = {sh.get('A',0)}/{sh.get('B',0)}/{sh.get('C',0)}/{sh.get('SKIP',0)}",
                f"  - B->C={s.get('B_to_C',0)} | B->B={s.get('B_to_B',0)}",
                f"  - rescue_to_B={s.get('rescue_to_B_count',0)} | rescue_to_A={s.get('rescue_to_A_count',0)}",
                f"  - SKIP_to_B={s.get('SKIP_to_B_count',0)} | market_alone={s.get('market_alone_manufactured_AB_count',0)} | safety={s.get('safety_violations_count',0)}",
                f"  - new_rescues_vs_default={len(item.get('new_rescues_vs_default') or [])}",
                f"  - risk_flags={','.join(item.get('risk_flags') or []) or 'NONE'}",
            ])
        md_path.write_text("\n".join(lines), encoding="utf-8")
        return json_path, md_path

    off = report["official_artifact"]
    dist_before = report["distribution"]["shadow_dryrun_grade_before_tuning"]
    dist_after = report["distribution"]["shadow_dryrun_grade_after_tuning"]
    s5c = report["recent5_coverage"]
    s5s = report["recent5_bilateral_gate_stats"]
    bfc = report["bfloor_coverage"]
    bfs = report["bfloor_stats"]
    sfc = report["safety_coverage"]
    cov = report["coverage"]

    lines = [
        f"# V4 RF Shadow Promotion Dryrun Replay ({date})",
        "",
        "> dryrun-only。不是 official promotion，不写 pending，不推 QQ。",
        "",
        f"- sample_status: {report['source']['sample_status']}",
        f"- official_artifact_status: {off['official_artifact_status']}",
        f"- final_replay_conclusion: {report['final_replay_conclusion']}",
        "",
        "## shadow dryrun（before -> after）",
        f"- A/B/C/SKIP before = {dist_before['A']}/{dist_before['B']}/{dist_before['C']}/{dist_before['SKIP']}",
        f"- A/B/C/SKIP after  = {dist_after['A']}/{dist_after['B']}/{dist_after['C']}/{dist_after['SKIP']}",
        f"- B->C before/after = {cov['b_to_c_before']} / {cov['b_to_c_after']}",
        f"- B->B before/after = {cov['b_to_b_before']} / {cov['b_to_b_after']}",
        f"- recent5 rescue_to_B = {s5s['recent5_rescue_to_B_count']}",
        f"- bfloor rescue_to_B  = {bfs['bfloor_rescue_to_B_count']}",
        f"- market assisted rescue_to_B = {report['safety_market_h2h_events_cpl']['market_assisted_rescue_to_B_count']}",
        f"- market alone manufactured A/B = {report['safety_market_h2h_events_cpl']['market_alone_manufactured_AB_count']}",
        "",
        "## coverage",
        f"- recent5_gate: {s5c['recent5_gate_field_coverage_status']} (available={s5c['recent5_gate_available_count']}, unknown={s5c['recent5_gate_unknown_count']})",
        f"- bfloor: {bfc['bfloor_exception_field_coverage_status']} (available={bfc['bfloor_exception_available_count']}, unknown={bfc['bfloor_exception_unknown_count']})",
        f"- safety: {sfc['safety_field_coverage_status']} (unknown={sfc['safety_unknown_count']})",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="YYYYMMDD")
    ap.add_argument("--source-artifact", default="", help="optional scout artifact path")
    ap.add_argument("--official-artifact", default="", help="optional official candidate_view artifact path")
    ap.add_argument("--strict-field-coverage", action="store_true", help="block baseline-ready when coverage incomplete")
    ap.add_argument("--rescue-threshold", type=float, default=77.0, help="single rescue threshold for shadow replay (default=77)")
    ap.add_argument("--rescue-thresholds", default="77,75,73.5", help="comma-separated thresholds for --sensitivity mode")
    ap.add_argument("--sensitivity", action="store_true", help="run shadow-only multi-threshold sensitivity replay")
    args = ap.parse_args()

    date = args.date.strip() or _latest_date()
    if args.sensitivity:
        thresholds: list[float] = []
        for raw in str(args.rescue_thresholds or "").split(","):
            raw = raw.strip()
            if not raw:
                continue
            thresholds.append(float(raw))
        report = build_sensitivity_report(
            date=date,
            source_artifact=args.source_artifact.strip() or None,
            official_artifact=args.official_artifact.strip() or None,
            strict_field_coverage=bool(args.strict_field_coverage),
            thresholds=thresholds or [77.0, 75.0, 73.5],
        )
        jp, mp = write_outputs(report, date, sensitivity=True)
    else:
        report = build_report(
            date=date,
            source_artifact=args.source_artifact.strip() or None,
            official_artifact=args.official_artifact.strip() or None,
            strict_field_coverage=bool(args.strict_field_coverage),
            rescue_threshold=float(args.rescue_threshold),
        )
        jp, mp = write_outputs(report, date, sensitivity=False)

    print(json.dumps({
        "status": "PASS",
        "scan_date": date,
        "sensitivity": bool(args.sensitivity),
        "json": str(jp),
        "md": str(mp),
        "source_row_count": report.get("source", {}).get("source_row_count"),
        "official_artifact_status": report.get("official_artifact", {}).get("official_artifact_status"),
        "final_replay_conclusion": report.get("final_replay_conclusion"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
