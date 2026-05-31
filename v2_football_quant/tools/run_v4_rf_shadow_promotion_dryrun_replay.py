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


def _coverage_status(available: int, unknown: int) -> str:
    if available <= 0 and unknown > 0:
        return "MISSING"
    if available > 0 and unknown > 0:
        return "PARTIAL"
    return "COMPLETE"


def build_report(date: str, source_artifact: str | None, official_artifact: str | None, strict_field_coverage: bool) -> dict[str, Any]:
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
    shadow_dist = {"A": 0, "B": 0, "C": 0, "SKIP": 0}
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

    # safety counters
    market_unknown = h2h_unknown = events_unknown = cpl_unknown = 0
    safety_missing_fields: set[str] = set()

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

        dry_grade, dry_source, dry_code, allowed = _dryrun_grade(row)
        shadow_dist[dry_grade] += 1

        delta, delta_reason = _official_shadow_delta(current_official, dry_grade, official["status"])
        delta_dist[delta] = delta_dist.get(delta, 0) + 1

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
            if dry_grade == "B":
                exception_to_b += 1
            if dry_grade == "A":
                exception_to_a += 1

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
            market_manufactured_ab_found += 1
        if str(row.get("opening_market_support_status") or "").upper() == "MARKET_HARD_VETO" and dry_grade == "SKIP":
            market_hard_veto_old_behavior_restored += 1

        h2h_status = str(row.get("h2h_recent5_support_status") or "").upper()
        if h2h_status in {"H2H_NO_BONUS", "H2H_LOW_SAMPLE"} and GRADE_RANK.get(dry_grade, 0) < GRADE_RANK.get(source_grade, 0):
            h2h_downgrade_found += 1
        if h2h_status in {"H2H_STRONG_BONUS", "H2H_LIGHT_BONUS"} and source_grade not in {"A", "B"} and dry_grade in {"A", "B"}:
            h2h_manufactured_ab_found += 1

        if _safe_bool(row.get("events_collected"), False) and source_grade not in {"A", "B"} and dry_grade in {"A", "B"}:
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
            "is_shadow_only_row": bool(is_shadow_only),
            "is_pending_bet_candidate": in_pending,
        })

    shadow_only_pending = sum(1 for r in rows_out if r["is_shadow_only_row"] and r["is_pending_bet_candidate"])

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
            "shadow_dryrun_grade": shadow_dist,
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
            "official_fixture_count": len(official_fixture_ids),
            "official_fixture_covered_by_scout_count": len(official_fixture_ids & scout_fixture_ids),
            "official_fixture_coverage_ok": len(official_fixture_ids & scout_fixture_ids) == len(official_fixture_ids) if official["status"] == "FOUND" else False,
            "official_ab_fixture_count": len(official_ab_fixture_ids),
            "official_ab_fixture_covered_by_scout_count": len(official_ab_fixture_ids & scout_fixture_ids),
            "official_ab_fixture_coverage_ok": len(official_ab_fixture_ids & scout_fixture_ids) == len(official_ab_fixture_ids) if official["status"] == "FOUND" else False,
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
        "final_replay_conclusion": final_conclusion,
        "rows": rows_out,
        "disclaimer": "DRYRUN/REPLAY ONLY. No official/pending/QQ mutation.",
    }
    return report


def write_outputs(report: dict[str, Any], date: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"v4_rf_shadow_promotion_dryrun_replay_{date}.json"
    md_path = OUT_DIR / f"v4_rf_shadow_promotion_dryrun_replay_{date}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    off = report["official_artifact"]
    dist = report["distribution"]["shadow_dryrun_grade"]
    s5c = report["recent5_coverage"]
    bfc = report["bfloor_coverage"]
    sfc = report["safety_coverage"]

    lines = [
        f"# V4 RF Shadow Promotion Dryrun Replay ({date})",
        "",
        "> dryrun-only。不是 official promotion，不写 pending，不推 QQ。",
        "",
        f"- sample_status: {report['source']['sample_status']}",
        f"- official_artifact_status: {off['official_artifact_status']}",
        f"- final_replay_conclusion: {report['final_replay_conclusion']}",
        "",
        "## shadow dryrun",
        f"- A/B/C/SKIP = {dist['A']}/{dist['B']}/{dist['C']}/{dist['SKIP']}",
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
    args = ap.parse_args()

    date = args.date.strip() or _latest_date()
    report = build_report(
        date=date,
        source_artifact=args.source_artifact.strip() or None,
        official_artifact=args.official_artifact.strip() or None,
        strict_field_coverage=bool(args.strict_field_coverage),
    )
    jp, mp = write_outputs(report, date)

    print(json.dumps({
        "status": "PASS",
        "scan_date": date,
        "json": str(jp),
        "md": str(mp),
        "source_row_count": report["source"]["source_row_count"],
        "official_artifact_status": report["official_artifact"]["official_artifact_status"],
        "final_replay_conclusion": report["final_replay_conclusion"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
