from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "v3_wc2026"
MASTER_FALLBACK = BASE_DIR / "engine" / "v3_config" / "intl_big4_master.json"
sys.path.insert(0, str(BASE_DIR))

from engine.v3_wc_stage_resolver import build_group_schedule_index, resolve_wc_stage_with_source
from engine.v3_router_guard import apply_v3_router_guard, load_v3_wc_config


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _fixture_id(row: dict[str, Any]) -> str:
    return str(
        row.get("fixture_id")
        or row.get("match_id")
        or ((row.get("fixture") or {}).get("id") or "")
    )


def _get(row: dict[str, Any], *keys, default=None):
    cur = row
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _home_away(row: dict[str, Any]) -> tuple[str, str]:
    home = row.get("home_team") or _get(row, "teams", "home", "name") or row.get("home") or ""
    away = row.get("away_team") or _get(row, "teams", "away", "name") or row.get("away") or ""
    return str(home), str(away)


def _kickoff(row: dict[str, Any]) -> str:
    return str(
        row.get("kickoff_utc")
        or row.get("date")
        or _get(row, "fixture", "date")
        or ""
    )


def _derive_odds(row: dict[str, Any]) -> tuple[float, float, float]:
    h = _to_float(row.get("psch_open"), 0.0) or _to_float(row.get("psch"), 0.0)
    d = _to_float(row.get("pscd_open"), 0.0) or _to_float(row.get("pscd"), 0.0)
    a = _to_float(row.get("psca_open"), 0.0) or _to_float(row.get("psca"), 0.0)
    return h, d, a


def _derive_elo_values(row: dict[str, Any], team_master: dict[str, Any]) -> tuple[float, float, float, float]:
    home, away = _home_away(row)
    elo_h = _to_float(row.get("elo_home"), 0.0)
    elo_a = _to_float(row.get("elo_away"), 0.0)
    val_h = _to_float(row.get("squad_value_home"), 0.0)
    val_a = _to_float(row.get("squad_value_away"), 0.0)

    if home and isinstance(team_master.get(home), dict):
        tm = team_master[home]
        elo_h = elo_h or _to_float(tm.get("elo"), 0.0)
        val_h = val_h or _to_float(tm.get("squad_value_m"), 0.0)
    if away and isinstance(team_master.get(away), dict):
        tm = team_master[away]
        elo_a = elo_a or _to_float(tm.get("elo"), 0.0)
        val_a = val_a or _to_float(tm.get("squad_value_m"), 0.0)
    return elo_h, elo_a, val_h, val_a


def _calc_gap(elo_h: float, elo_a: float, val_h: float, val_a: float) -> float:
    if min(elo_h, elo_a, val_h, val_a) <= 0:
        return 0.0
    return round(math.log(val_h / val_a) - math.log(elo_h / elo_a), 4)


def _bubble_level(gap_abs: float) -> str:
    if gap_abs >= 1.6:
        return "EXTREME_PLUS"
    if gap_abs >= 1.3:
        return "EXTREME"
    if gap_abs >= 1.0:
        return "HIGH"
    if gap_abs >= 0.7:
        return "MEDIUM"
    if gap_abs >= 0.5:
        return "LOW"
    return "NONE"


def _market_favorite_side(psch: float, pscd: float, psca: float) -> str:
    vals = []
    if psch > 0:
        vals.append(("HOME", psch))
    if psca > 0:
        vals.append(("AWAY", psca))
    if pscd > 0:
        vals.append(("DRAW", pscd))
    if not vals:
        return "UNKNOWN"
    vals.sort(key=lambda x: x[1])
    side, _ = vals[0]
    if side == "DRAW":
        return "DRAWISH"
    return side


def _build_signal(row: dict[str, Any], team_master: dict[str, Any], group_idx) -> dict[str, Any]:
    home, away = _home_away(row)
    fid = _fixture_id(row)
    kickoff_utc = _kickoff(row)
    psch, pscd, psca = _derive_odds(row)
    elo_h, elo_a, val_h, val_a = _derive_elo_values(row, team_master)
    gap = _calc_gap(elo_h, elo_a, val_h, val_a)
    stage, stage_source = resolve_wc_stage_with_source(row, group_idx)

    if gap >= 0:
        bubble_side = "HOME"
        bubble_team = home
        opposite_team = away
        target_market = "X2"
        target_action = f"{away}_OR_DRAW" if away else "AWAY_OR_DRAW"
        favorite_odds = psch if psch > 0 else 99.0
    else:
        bubble_side = "AWAY"
        bubble_team = away
        opposite_team = home
        target_market = "1X"
        target_action = f"{home}_OR_DRAW" if home else "HOME_OR_DRAW"
        favorite_odds = psca if psca > 0 else 99.0

    if favorite_odds >= 99.0 and psch > 0 and psca > 0:
        favorite_odds = min(psch, psca)
    market_favorite_side = _market_favorite_side(psch, pscd, psca)
    is_market_favorite = market_favorite_side not in {"UNKNOWN", "DRAWISH"} and market_favorite_side == bubble_side

    elo_diff = abs(elo_h - elo_a)
    val_ratio = (max(val_h, 0.0) / max(val_a, 1e-9)) if val_a > 0 else 0.0
    if gap < 0 and val_h > 0:
        val_ratio = max(val_a, 0.0) / max(val_h, 1e-9)

    gp_home = row.get("group_points_before_match_home")
    gp_away = row.get("group_points_before_match_away")
    must_win_home = bool(row.get("must_win_home", False))
    must_win_away = bool(row.get("must_win_away", False))
    draw_ok_home = bool(row.get("can_accept_draw_home", False))
    draw_ok_away = bool(row.get("can_accept_draw_away", False))
    eliminated_home = bool(row.get("already_eliminated_home", False))
    eliminated_away = bool(row.get("already_eliminated_away", False))

    favorite_side = "HOME" if bubble_side == "HOME" else "AWAY"
    motivation_tags = []
    if favorite_side == "HOME" and must_win_home:
        motivation_tags.append("MUST_WIN_FAVORITE")
    if favorite_side == "AWAY" and must_win_away:
        motivation_tags.append("MUST_WIN_FAVORITE")
    if bubble_side == "HOME" and draw_ok_away:
        motivation_tags.append("DRAW_OK_UNDERDOG")
    if bubble_side == "AWAY" and draw_ok_home:
        motivation_tags.append("DRAW_OK_UNDERDOG")
    if eliminated_home or eliminated_away:
        motivation_tags.append("ELIMINATION_PRESSURE")

    underdog_gk_ok = row.get("underdog_goalkeeper_available")
    underdog_cb_ok = row.get("underdog_centerbacks_available")
    favorite_core_ok = row.get("favorite_core_available")
    if underdog_gk_ok is False or underdog_cb_ok is False:
        motivation_tags.append("UNDERDOG_DEFENSE_RISK")
    if favorite_core_ok is False:
        motivation_tags.append("FAVORITE_CORE_MISSING")

    return {
        "strategy_id": "V3_WC_BUBBLE",
        "fixture_id": fid,
        "kickoff_utc": kickoff_utc,
        "home": home,
        "away": away,
        "stage": str(row.get("stage") or ""),
        "wc_stage": stage,
        "stage_source": stage_source,
        "bubble_side": bubble_side,
        "bubble_team": bubble_team,
        "opposite_team": opposite_team,
        "target_market": target_market,
        "target_action": target_action,
        "target_market_family": "double_chance",
        "market_plan": {
            "conservative": target_market,
            "neutral": "AH +0.5",
            "aggressive": "DRAW",
        },
        "action_before_router": "V3_CANDIDATE",
        "gap": round(gap, 4),
        "gap_abs": round(abs(gap), 4),
        "bubble_level": _bubble_level(abs(gap)),
        "elo_diff": round(elo_diff, 1),
        "favorite_odds": round(favorite_odds, 3) if favorite_odds < 90 else None,
        "market_favorite_side": market_favorite_side,
        "is_market_favorite": is_market_favorite,
        "odds_open": {"psch": psch or None, "pscd": pscd or None, "psca": psca or None},
        "elo_home": elo_h or None,
        "elo_away": elo_a or None,
        "squad_value_home_m": val_h or None,
        "squad_value_away_m": val_a or None,
        "squad_value_ratio": round(val_ratio, 4) if val_ratio else None,
        "group_points_before_match": {
            "home": gp_home,
            "away": gp_away,
        },
        "qualification_pressure": {
            "must_win_home": must_win_home,
            "must_win_away": must_win_away,
            "can_accept_draw_home": draw_ok_home,
            "can_accept_draw_away": draw_ok_away,
            "already_eliminated_home": eliminated_home,
            "already_eliminated_away": eliminated_away,
        },
        "lineup_risk": {
            "favorite_core_available": favorite_core_ok,
            "underdog_goalkeeper_available": underdog_gk_ok,
            "underdog_centerbacks_available": underdog_cb_ok,
        },
        "risk_tags": motivation_tags,
        "built_at_utc": datetime.utcnow().isoformat() + "Z",
    }


def _date_key(v: str) -> str:
    return v.replace("-", "")


def ensure_v3_data_layout() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 如果 WC2026 数据已锁定，跳过自动播种
    lock_file = DATA_DIR / ".wc2026_locked"
    if lock_file.exists():
        return
    for name in [
        "teams_master.json",
        "group_schedule.json",
        "elo_snapshots.json",
        "squad_values.json",
        "odds_open_close.json",
        "v3_paper_results.jsonl",
    ]:
        p = DATA_DIR / name
        if p.exists():
            continue
        if name.endswith(".json"):
            _save_json(p, [] if name != "teams_master.json" else {})
        else:
            p.write_text("", encoding="utf-8")

    teams_master_path = DATA_DIR / "teams_master.json"
    if teams_master_path.exists():
        try:
            payload = _load_json(teams_master_path, {})
            if isinstance(payload, dict) and payload:
                return
        except Exception:
            pass

    # Bootstrap minimal V3 data assets from historical intl master when empty.
    rows = _load_json(MASTER_FALLBACK, [])
    teams = {}
    odds_rows = []
    elo_rows = []
    value_rows = []
    group_rows = []
    for r in rows:
        home = str(r.get("home_team") or "")
        away = str(r.get("away_team") or "")
        if home and home not in teams:
            teams[home] = {
                "team": home,
                "group": r.get("group") or None,
                "elo": r.get("elo_home"),
                "squad_value_m": r.get("squad_value_home"),
            }
        if away and away not in teams:
            teams[away] = {
                "team": away,
                "group": r.get("group") or None,
                "elo": r.get("elo_away"),
                "squad_value_m": r.get("squad_value_away"),
            }
        odds_rows.append(
            {
                "fixture_id": r.get("match_id"),
                "home": home,
                "away": away,
                "stage": r.get("stage"),
                "psch_open": r.get("psch"),
                "pscd_open": r.get("pscd"),
                "psca_open": r.get("psca"),
            }
        )
        elo_rows.append({"team": home, "elo": r.get("elo_home")})
        elo_rows.append({"team": away, "elo": r.get("elo_away")})
        value_rows.append({"team": home, "squad_value_m": r.get("squad_value_home")})
        value_rows.append({"team": away, "squad_value_m": r.get("squad_value_away")})
        group_rows.append(
            {
                "fixture_id": r.get("match_id"),
                "date": r.get("date"),
                "stage": r.get("stage"),
                "home_team": home,
                "away_team": away,
            }
        )
    _save_json(teams_master_path, teams)
    _save_json(DATA_DIR / "odds_open_close.json", odds_rows)
    _save_json(DATA_DIR / "elo_snapshots.json", elo_rows)
    _save_json(DATA_DIR / "squad_values.json", value_rows)
    _save_json(DATA_DIR / "group_schedule.json", group_rows)


def build_signals(date_str: str, source_path: Path | None = None) -> dict[str, Any]:
    ensure_v3_data_layout()
    team_master_raw = _load_json(DATA_DIR / "teams_master.json", {})
    elo_data = _load_json(DATA_DIR / "elo_snapshots.json", [])
    squad_data = _load_json(DATA_DIR / "squad_values.json", [])
    # 兼容新旧格式：list → dict，并注入 Elo/身价
    if isinstance(team_master_raw, list):
        team_master = {}
        elo_map = {e["team"]: e.get("elo", 1400) for e in elo_data}
        sq_map = {s["team"]: s.get("squad_value_m", 50) for s in squad_data}
        for t in team_master_raw:
            if isinstance(t, dict) and t.get("name"):
                name = t["name"]
                team_master[name] = {**t, "elo": elo_map.get(name, 1400), "squad_value_m": sq_map.get(name, 50)}
    else:
        team_master = team_master_raw
    cfg = load_v3_wc_config()

    if source_path and source_path.exists():
        if source_path.suffix.lower() == ".jsonl":
            matches = _load_jsonl(source_path)
        else:
            matches = _load_json(source_path, [])
    else:
        # WC2026 模式：从独立数据文件组装比赛记录
        schedule = _load_json(DATA_DIR / "group_schedule.json", [])
        elo_list = _load_json(DATA_DIR / "elo_snapshots.json", [])
        squad_list = _load_json(DATA_DIR / "squad_values.json", [])
        odds_list = _load_json(DATA_DIR / "odds_open_close.json", [])
        
        elo_map = {e["team"]: e.get("elo", 1400) for e in elo_list}
        squad_map = {s["team"]: s.get("squad_value_m", 50) for s in squad_list}
        odds_map = {}
        for o in odds_list:
            fid = o.get("fixture_id", "")
            if fid:
                odds_map[fid] = o
        
        matches = []
        for m in schedule:
            home = m.get("home_team", "")
            away = m.get("away_team", "")
            fid = str(m.get("fixture_id", ""))
            odds = odds_map.get(fid, {})
            matches.append({
                "match_id": fid,
                "fixture_id": fid,
                "tournament": "WC2026",
                "date": m.get("date", ""),
                "stage": m.get("stage", "group"),
                "home_team": home,
                "away_team": away,
                "elo_home": elo_map.get(home, 1400),
                "elo_away": elo_map.get(away, 1400),
                "squad_value_home": squad_map.get(home, 50),
                "squad_value_away": squad_map.get(away, 50),
                "psch": odds.get("psch_open") or odds.get("psch"),
                "pscd": odds.get("pscd_open") or odds.get("pscd"),
                "psca": odds.get("psca_open") or odds.get("psca"),
                "home_bubble": False,
                "away_bubble": False,
            })
        if not matches:
            matches = _load_json(MASTER_FALLBACK, [])

    group_idx = build_group_schedule_index(matches)
    signals = []
    for row in matches:
        sig = _build_signal(row, team_master, group_idx)
        # Preview routed action using default empty engine_stats.
        sig = apply_v3_router_guard(sig, engine_stats={}, cfg=cfg)
        signals.append(sig)
    key = _date_key(date_str)
    out_path = DATA_DIR / f"v3_signals_{key}.jsonl"
    _save_jsonl(out_path, signals)

    by_stage = {}
    by_source = {}
    by_level = {}
    for s in signals:
        by_stage[s["wc_stage"]] = by_stage.get(s["wc_stage"], 0) + 1
        by_source[s["stage_source"]] = by_source.get(s["stage_source"], 0) + 1
        by_level[s["bubble_level"]] = by_level.get(s["bubble_level"], 0) + 1
    stage_audit = {
        "date": key,
        "signals": len(signals),
        "by_stage": dict(sorted(by_stage.items())),
        "by_stage_source": dict(sorted(by_source.items())),
        "by_bubble_level": dict(sorted(by_level.items())),
        "output_path": str(out_path),
    }
    _save_json(DATA_DIR / "v3_stage_audit.json", stage_audit)
    return stage_audit


def main() -> None:
    ap = argparse.ArgumentParser(description="Build V3 WC bubble signals.")
    ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    ap.add_argument("--source", default="", help="Optional source json/jsonl file")
    args = ap.parse_args()

    src = Path(args.source) if args.source else None
    summary = build_signals(args.date, src)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
