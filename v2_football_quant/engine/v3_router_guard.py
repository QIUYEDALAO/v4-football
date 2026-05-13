from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "v3_wc_config.json"


def _load_json_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_v3_wc_config() -> dict[str, Any]:
    return _load_json_config(CONFIG_PATH)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _md1_stats(engine_stats: dict[str, Any]) -> tuple[int, float, float]:
    md1 = engine_stats.get("MD1_stats") or {}
    bets = _to_int(md1.get("bets"), _to_int(engine_stats.get("v3_md1_bets"), 0))
    clv = _to_float(md1.get("avg_true_clv_pct"), _to_float(engine_stats.get("v3_md1_avg_true_clv_pct"), 0.0))
    comp = _to_float(md1.get("data_completeness_pct"), _to_float(engine_stats.get("v3_md1_data_completeness_pct"), 0.0))
    return bets, clv, comp


def _rolling_md2_stats(engine_stats: dict[str, Any]) -> tuple[int, float]:
    roll = engine_stats.get("MD2_rolling_10") or {}
    bets = _to_int(roll.get("bets"), _to_int(engine_stats.get("md2_rolling_10_bets"), 0))
    clv = _to_float(roll.get("avg_true_clv_pct"), _to_float(engine_stats.get("md2_rolling_10_clv"), 0.0))
    return bets, clv


def _gate_md1(md1_bets: int, md1_clv: float, md1_comp: float, cfg: dict[str, Any]) -> bool:
    gate = cfg.get("md1_gate") or {}
    min_bets = _to_int(gate.get("min_bets"), 10)
    min_clv = _to_float(gate.get("min_avg_true_clv_pct"), 0.0)
    min_comp = _to_float(gate.get("min_data_completeness_pct"), 90.0)
    return md1_bets >= min_bets and md1_clv >= min_clv and md1_comp >= min_comp


def _is_true_mismatch(signal: dict[str, Any], cfg: dict[str, Any]) -> bool:
    tr = (cfg.get("thresholds") or {}).get("true_mismatch") or {}
    elo_diff_cap = _to_float(tr.get("elo_diff_max_for_bubble"), 450.0)
    favorite_odds_floor = _to_float(tr.get("favorite_odds_min"), 1.25)
    elo_diff = abs(_to_float(signal.get("elo_diff"), 0.0))
    favorite_odds = _to_float(signal.get("favorite_odds"), 99.0)
    return elo_diff > elo_diff_cap and favorite_odds < favorite_odds_floor


def _is_bubble_aligned_with_market_favorite(signal: dict[str, Any]) -> bool:
    side = str(signal.get("bubble_side") or "").upper()
    market_side = str(signal.get("market_favorite_side") or "").upper()
    if not side or not market_side:
        return True
    if market_side in {"UNKNOWN", "DRAWISH"}:
        return False
    return side == market_side


def _explicit_not_market_favorite(signal: dict[str, Any]) -> bool:
    # Prefer explicit builder flag when present.
    v = signal.get("is_market_favorite")
    if isinstance(v, bool):
        return v is False
    return False


def apply_v3_router_guard(
    signal: dict[str, Any],
    engine_stats: dict[str, Any] | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(signal)
    engine_stats = engine_stats or {}
    cfg = cfg or load_v3_wc_config()
    wc_cfg = cfg.get("world_cup_window") or {}
    thresholds = cfg.get("thresholds") or {}
    medium_gap_min = _to_float(thresholds.get("medium_gap_min"), 0.70)
    extreme_gap_min = _to_float(thresholds.get("extreme_gap_min"), 1.00)

    if not bool(wc_cfg.get("enabled", False)):
        out["action"] = "V3_SKIP_OFF_SEASON"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = "世界杯窗口未开启"
        return out

    stage = str(out.get("wc_stage") or "UNKNOWN_STAGE").upper()
    gap = abs(_to_float(out.get("gap"), 0.0))

    if stage in {"UNKNOWN", "UNKNOWN_STAGE", ""}:
        out["action"] = "V3_BLOCK_STAGE_UNKNOWN"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = "阶段无法识别，阻断信号"
        return out

    if stage == "MD1":
        out["action"] = "V3_MD1_PAPER"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = "MD1仅纸盘校准"
        return out

    if stage == "MD3":
        out["action"] = "V3_BLOCK_MD3"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = "MD3战意污染高，强制跳过"
        return out

    if stage == "KO":
        out["action"] = "V3_BLOCK_KO"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = "KO阶段定价机制不同，策略不交易"
        return out

    if stage != "MD2":
        out["action"] = "V3_BLOCK_STAGE_UNKNOWN"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = f"未知阶段 {stage}"
        return out

    if gap < medium_gap_min:
        out["action"] = "V3_SKIP_LOW_GAP"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = f"Gap={gap:.2f} 低于 {medium_gap_min:.2f}"
        return out

    if _is_true_mismatch(out, cfg):
        out["action"] = "V3_SKIP_TRUE_MISMATCH"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = "Elo实力断层过大，跳过伪泡沫"
        return out

    if _explicit_not_market_favorite(out):
        out["action"] = "V3_MD2_WATCH"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = "泡沫方不是市场热门，降级观察"
        return out

    if not _is_bubble_aligned_with_market_favorite(out):
        out["action"] = "V3_MD2_WATCH"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = "泡沫方与市场热门不一致，降级观察"
        return out

    md2_bets, md2_clv = _rolling_md2_stats(engine_stats)
    if md2_bets >= 10 and md2_clv < 0:
        out["action"] = "V3_KILL_CLV"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = f"MD2 rolling10 CLV={md2_clv:.2f}% < 0，熔断"
        return out

    if gap < extreme_gap_min:
        out["action"] = "V3_MD2_WATCH"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = f"中度泡沫区 {medium_gap_min:.2f}-{extreme_gap_min:.2f}，继续观察"
        return out

    md1_bets, md1_clv, md1_comp = _md1_stats(engine_stats)
    if _gate_md1(md1_bets, md1_clv, md1_comp, cfg):
        out["action"] = "V3_MD2_MICRO"
        out["max_risk_units"] = 0.25
        out["skip_reason"] = "MD1闸门通过，允许MD2微型沙盒"
    else:
        out["action"] = "V3_MD2_WATCH"
        out["max_risk_units"] = 0.0
        out["skip_reason"] = (
            "MD1闸门未通过，继续纸盘"
            f" (bets={md1_bets}, clv={md1_clv:.2f}%, comp={md1_comp:.1f}%)"
        )

    out["gate_md1"] = {
        "bets": md1_bets,
        "avg_true_clv_pct": md1_clv,
        "data_completeness_pct": md1_comp,
    }
    out["gate_md2"] = {"rolling_10_bets": md2_bets, "rolling_10_avg_true_clv_pct": md2_clv}
    return out
