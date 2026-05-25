#!/usr/bin/env python3
"""
V3 World Cup Roster Schema
Author: ClawOps
Date: 2026-05-25
Purpose: Structured schema for World Cup 2026 team rosters.
         All fields are V3-specific; no V2/V4 coupling.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

CST = timezone(timedelta(hours=8))

# ── Roster Schema Definition ──────────────────────────────────────────
ROSTER_SCHEMA = {
    "version": "3.0.0",
    "schema_date": "2026-05-25",
    "purpose": "V3 World Cup Perception Gap Roster Intelligence Baseline",
    "player_fields": {
        "required": [
            "team",           # 球队名 (e.g. "Argentina")
            "player_name",    # 球员名 (e.g. "Lionel Messi")
            "position",       # 位置 (GK/DEF/MID/FWD)
            "age",            # 年龄
            "club",           # 所属俱乐部
            "league",         # 联赛
            "caps",           # 国家队出场
            "goals",          # 国家队进球
            "season_minutes", # 赛季出场时间(分钟)
            "injury_status",  # 伤病状态 (FIT/DOUBT/OUT)
            "role_tag",       # 角色标签 (STARTER/SQUAD/FRINGE)
            "is_projected_starter", # 是否预计首发
            "is_core_player",      # 核心球员
            "is_newcomer",         # 新人/首次入选
            "is_surprise_pick",    # 意外入选
            "is_key_absence",      # 关键缺席(该位置缺人)
            "source",              # 数据来源
            "source_date",         # 来源日期
            "confidence"           # 置信度 (HIGH/MEDIUM/LOW)
        ],
        "optional": [
            "shirt_number",
            "height_cm",
            "weight_kg",
            "foot",
            "market_value_eur",
            "position_detail",
            "alternate_positions",
            "youth_national_team",
            "notes"
        ]
    },
    "team_roster_structure": {
        "goalkeepers": "list[player]",
        "defenders": "list[player]",
        "midfielders": "list[player]",
        "forwards": "list[player]",
        "staff_notes": "string | null",
        "missing_key_players": "list[str]",
        "injury_watch": "list[dict]"
    },
    "roster_delta_fields": {
        "required": [
            "team",
            "core_stability_score",     # 0-100 核心阵容稳定度
            "spine_change_score",       # 0-100 中轴线变化度(越高越不稳)
            "age_risk_score",           # 0-100 年龄风险
            "injury_risk_score",        # 0-100 伤病风险
            "depth_score",              # 0-100 替补深度(越高越好)
            "key_absence_score",        # 0-100 关键缺阵影响
            "newcomer_impact_score"     # 0-100 新人影响度
        ]
    },
    "team_profile_fields": {
        "required": [
            "team",
            "attack_profile",           # 进攻画像
            "defense_profile",          # 防守画像
            "transition_profile",       # 转换画像
            "set_piece_profile",        # 定位球画像
            "midfield_control",         # 中场控制力
            "goalkeeper_reliability",   # 门将可靠性
            "bench_depth",              # 替补深度
            "tactical_risk",            # 战术风险
            "public_narrative",         # 公众叙事
            "hidden_strength",          # 隐藏优势
            "hidden_weakness"           # 隐藏弱点
        ]
    },
    "perception_gap_fields": {
        "required": [
            "team",
            "public_expectation",       # 公众期望
            "roster_reality",           # 阵容现实
            "gap_direction",            # OVERRATED / UNDERRATED / ALIGNED
            "gap_level",                # PG_HIGH / PG_MEDIUM / PG_LOW / WATCHLIST / SKIP
            "reason",                   # 原因
            "confidence",               # 置信度
            "next_required_data"        # 下一步需补数据
        ]
    }
}

# ── Position Classification ───────────────────────────────────────────
POSITION_MAP = {
    "GK": "goalkeepers",
    "DEF": "defenders",
    "CB": "defenders",
    "LB": "defenders",
    "RB": "defenders",
    "MID": "midfielders",
    "CDM": "midfielders",
    "CM": "midfielders",
    "CAM": "midfielders",
    "LW": "forwards",
    "RW": "forwards",
    "FWD": "forwards",
    "CF": "forwards",
    "ST": "forwards"
}

# ── Validation ────────────────────────────────────────────────────────
def validate_player(player: Dict[str, Any]) -> List[str]:
    """Validate a single player record against schema. Returns list of missing fields."""
    errors = []
    for field in ROSTER_SCHEMA["player_fields"]["required"]:
        if field not in player or player[field] is None:
            errors.append(f"MISSING_REQUIRED:{field}")
    return errors

def validate_team_roster(team_name: str, roster: Dict[str, Any]) -> List[str]:
    """Validate a full team roster. Returns list of errors/warnings."""
    errors = []
    squad_keys = ["goalkeepers", "defenders", "midfielders", "forwards"]
    for key in squad_keys:
        if key not in roster:
            errors.append(f"MISSING_SQUAD_BLOCK:{team_name}:{key}")
        elif not isinstance(roster[key], list):
            errors.append(f"BAD_TYPE:{team_name}:{key}:expected_list")
        elif len(roster[key]) == 0:
            errors.append(f"EMPTY_SQUAD_BLOCK:{team_name}:{key}:WARN_ONLY")

    total_players = sum(len(roster.get(k, [])) for k in squad_keys)
    if total_players == 0:
        errors.append(f"EMPTY_ROSTER:{team_name}:BLOCKER")
    elif total_players < 18:
        errors.append(f"LOW_PLAYER_COUNT:{team_name}:{total_players}:WARN_ONLY")

    return errors

if __name__ == "__main__":
    print(json.dumps({
        "schema": "V3_WORLDCUP_ROSTER_SCHEMA",
        "version": ROSTER_SCHEMA["version"],
        "schema_date": ROSTER_SCHEMA["schema_date"],
        "player_required_fields": len(ROSTER_SCHEMA["player_fields"]["required"]),
        "player_optional_fields": len(ROSTER_SCHEMA["player_fields"]["optional"]),
        "status": "SCHEMA_DEFINED"
    }, ensure_ascii=False, indent=2))
