"""V4 main-league admission policy for research-pool gating.

This module is deliberately policy-only. It does not grade fixtures, send
notifications, write pending candidates, or call remote APIs.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/v4_main_league_admission_policy.json"

INCLUDE_GROUPS = {"INCLUDE_CURRENT", "INCLUDE_SEASON_AWARE"}


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _league_index(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for group, rows in (policy.get("league_groups") or {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            indexed = {**row, "admission_group": group}
            league_id = row.get("league_id")
            if league_id is not None:
                index[f"id:{league_id}"] = indexed
            for name in [row.get("name"), *(row.get("aliases") or [])]:
                key = _norm(name)
                if key:
                    index[f"name:{key}"] = indexed
    return index


def classify_league(league_id: Any = None, league_name: Any = "", league_type: Any = "") -> dict[str, Any]:
    """Classify a fixture league into include/observe/exclude policy groups."""
    policy = load_policy()
    index = _league_index(policy)
    row = index.get(f"id:{league_id}") if league_id not in (None, "") else None
    if row is None:
        row = index.get(f"name:{_norm(league_name)}")

    type_lower = _norm(league_type)
    name_lower = _norm(league_name)
    if row is not None:
        group = str(row.get("admission_group") or "EXCLUDE_DEFAULT")
        if "friendly" in name_lower or "friendlies" in name_lower or "友谊" in name_lower:
            group = "OBSERVE_ONLY"
        return {
            "admission_group": group,
            "league_policy_name": row.get("name") or league_name,
            "league_policy_reason": "POLICY_MATCH",
            "strategy_pool_allowed": group in INCLUDE_GROUPS,
            "observe_only": group == "OBSERVE_ONLY",
        }

    haystack = f"{name_lower} {type_lower}"
    excluded_keywords = [
        str(x).casefold() for x in (policy.get("exclude_default", {}).get("name_keywords") or [])
    ]
    if type_lower and type_lower != "league":
        return {
            "admission_group": "EXCLUDE_DEFAULT",
            "league_policy_name": str(league_name or "UNKNOWN"),
            "league_policy_reason": f"NON_LEAGUE_TYPE:{league_type}",
            "strategy_pool_allowed": False,
            "observe_only": False,
        }
    for keyword in excluded_keywords:
        if keyword and keyword in haystack:
            return {
                "admission_group": "EXCLUDE_DEFAULT",
                "league_policy_name": str(league_name or "UNKNOWN"),
                "league_policy_reason": f"EXCLUDED_KEYWORD:{keyword}",
                "strategy_pool_allowed": False,
                "observe_only": False,
            }
    return {
        "admission_group": "EXCLUDE_DEFAULT",
        "league_policy_name": str(league_name or "UNKNOWN"),
        "league_policy_reason": "LEAGUE_NOT_IN_MAIN_POLICY",
        "strategy_pool_allowed": False,
        "observe_only": False,
    }


def admission_rule_status(
    *,
    market_families: list[str] | None = None,
    bookmaker_count: int | None = None,
    has_ft_ou_line: bool = False,
    has_handicap_line: bool = False,
    has_standings: bool = False,
    has_team_stats: bool = False,
    has_injuries: bool = False,
    has_lineup: bool = False,
) -> dict[str, Any]:
    """Evaluate information-completeness rules without changing grades."""
    policy = load_policy()
    rules = policy.get("admission_rules") or {}
    families = {str(x).upper() for x in (market_families or []) if x}
    min_market_count = int(rules.get("required_market_family_count") or 3)
    min_bookmakers = int(rules.get("minimum_bookmaker_count") or 5)
    blockers: list[str] = []
    data_gap_tags: list[str] = []
    if len(families.intersection({"1X2", "FT_OU", "AH_OR_HANDICAP", "DOUBLE_CHANCE"})) < min_market_count:
        blockers.append("MARKET_FAMILY_COVERAGE_LT_3")
    if int(bookmaker_count or 0) < min_bookmakers:
        blockers.append("BOOKMAKER_COUNT_LT_5")
    if not (has_ft_ou_line or has_handicap_line):
        blockers.append("LINE_MISSING_FOR_FT_OU_OR_HANDICAP")
    if not (has_standings or has_team_stats):
        blockers.append("STANDINGS_OR_TEAM_STATS_MISSING")
    if not has_injuries:
        data_gap_tags.append(str(rules.get("missing_injuries_tag") or "INJURY_SOURCE_MISSING"))
    if not has_lineup:
        data_gap_tags.append("LINEUP_WAIT_EVENT")
    return {
        "admission_info_complete": not blockers,
        "admission_blockers": blockers,
        "data_gap_tags": data_gap_tags,
        "ht_over_policy": rules.get("ht_over_policy") or "AUXILIARY_ONLY_NO_STANDALONE_AB",
    }
