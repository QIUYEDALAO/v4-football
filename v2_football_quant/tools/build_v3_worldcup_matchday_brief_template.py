#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WAR_ROOM = ROOT / "data/manual_sources/v3_worldcup/war_room"
SQUAD_DIR = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
VENUE_STRESS = ROOT / "data/v3_worldcup/venue_stress/v3_worldcup_venue_stress_20260603.json"
ODDS_MOVEMENT_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_movement_eligibility_20260604.json"
ODDS_LIVE_STATUS = ROOT / "data/runtime/status/check_v3_worldcup_odds_snapshot_live_small_batch_20260604.json"

CANONICAL_104 = WAR_ROOM / "v3_wc2026_104_cards_index_bridge.json"
MATCH_CARDS = WAR_ROOM / "v3_wc_match_cards.json"
COVERAGE_RADAR = WAR_ROOM / "v3_wc2026_104_coverage_gap_radar.json"
PROFILE_CARDS = SQUAD_DIR / "v3_wc2026_final_26_squad_profile_team_cards.json"
TEMPLATE = ROOT / "templates/v3_worldcup_matchday_brief_card.md"

OUT_JSON = WAR_ROOM / "v3_wc2026_matchday_brief_cards.json"
OUT_MD = WAR_ROOM / "V3_WC2026_MATCHDAY_BRIEF_CARDS.md"
OUT_SUMMARY = WAR_ROOM / "v3_wc2026_matchday_brief_summary.json"

SAFETY = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_prediction": True,
    "no_injury_judgment": True,
    "betting_recommendation": False,
    "affects_v4": False,
}

TEAM_SLUG_ALIASES = {
    "cote_divoire": "cote_d_ivoire",
}

ROUND_LABELS = {
    "GROUP_STAGE": "小组赛",
    "round_of_32": "32 强淘汰赛",
    "round_of_16": "16 强淘汰赛",
    "quarter_finals": "四分之一决赛",
    "semi_finals": "半决赛",
    "third_place": "三四名决赛",
    "final": "决赛",
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def stable_generated_at() -> str:
    existing = load_json(OUT_SUMMARY, {})
    if isinstance(existing, dict) and existing.get("generated_at"):
        return str(existing["generated_at"])
    return datetime.now(timezone.utc).isoformat()


def slug_text(value: str | None) -> str:
    return str(value or "").strip().lower().replace("&amp;", "and").replace(" ", "_")


def index_by(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(item.get(key)): item for item in items if isinstance(item, dict) and item.get(key) is not None}


def match_ref_id(card: dict[str, Any]) -> str:
    ref = str(card.get("group_stage_view_ref") or card.get("source_card_ref") or "")
    if "#" in ref:
        return ref.rsplit("#", 1)[-1]
    return str(card.get("match_card_id") or "")


def kickoff_display(card: dict[str, Any], source_card: dict[str, Any] | None) -> str:
    if source_card:
        local = source_card.get("kickoff_local")
        if isinstance(local, dict):
            date = html.unescape(str(local.get("date") or "")).strip()
            time = html.unescape(str(local.get("time") or "")).strip()
            zone = html.unescape(str(local.get("timezone") or "")).strip()
            parts = [part for part in [date, time, zone] if part]
            if parts:
                return " ".join(parts)
        if source_card.get("kickoff_time_utc"):
            return str(source_card.get("kickoff_time_utc"))
    return "等待官方开球时间确认"


def stage_display(card: dict[str, Any]) -> str:
    round_key = str(card.get("round") or "")
    label = ROUND_LABELS.get(round_key, round_key or "阶段待确认")
    if round_key == "GROUP_STAGE" and card.get("group"):
        return f"{label} {card.get('group')} 组"
    return label


def team_display(card: dict[str, Any]) -> tuple[str, str]:
    if card.get("card_kind") == "KNOCKOUT_SLOT":
        return "结构占位", "等待真实对阵"
    return str(card.get("home_team") or "UNKNOWN"), str(card.get("away_team") or "UNKNOWN")


def profile_summary(slug: str | None, profiles: dict[str, dict[str, Any]]) -> str:
    if not slug:
        return "STRUCTURAL_PLACEHOLDER"
    normalized_slug = TEAM_SLUG_ALIASES.get(str(slug), str(slug))
    p = profiles.get(normalized_slug)
    if not p:
        return "Final26 摘要缺失"
    pos = p.get("position_distribution") if isinstance(p.get("position_distribution"), dict) else {}
    age = p.get("age_profile") if isinstance(p.get("age_profile"), dict) else {}
    height = p.get("height_profile") if isinstance(p.get("height_profile"), dict) else {}
    return (
        f"{p.get('team')} 26人；GK/DF/MF/FW="
        f"{pos.get('GK', 0)}/{pos.get('DF', 0)}/{pos.get('MF', 0)}/{pos.get('FW', 0)}；"
        f"均龄 {age.get('avg_age', 'N/A')}；均高 {height.get('avg_height_cm', 'N/A')}cm"
    )


def venue_summary(card: dict[str, Any], venues: dict[str, dict[str, Any]]) -> str:
    venue = str(card.get("venue_name") or "VENUE_PENDING")
    info = venues.get(venue) or venues.get(venue.replace("&amp;", "&"))
    if not info:
        return f"{venue}；场馆压力资料待补充"
    tags = " / ".join(info.get("stress_tags") or ["WATCH_ONLY"])
    reason = info.get("stress_reason") or "观察原因未提供"
    quality = info.get("source_quality") or "UNKNOWN_SOURCE_QUALITY"
    return f"{venue}；{tags}；原因：{reason}；来源等级：{quality}"


def odds_status(card: dict[str, Any], coverage: dict[str, Any], movement: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    is_group = card.get("card_kind") == "GROUP_STAGE_MATCH"
    coverage_status = coverage.get("odds_fixture_id_coverage_status") or ("MAPPED" if card.get("odds_fixture_id") else "STRUCTURAL_PLACEHOLDER")
    live_cov = live.get("coverage") if isinstance(live.get("coverage"), dict) else live
    market = live_cov.get("market_coverage") if isinstance(live_cov.get("market_coverage"), dict) else {}
    return {
        "odds_fixture_id": card.get("odds_fixture_id"),
        "odds_fixture_id_status": coverage_status,
        "first_seen_odds": "LOCAL_TIMELINE_FIELD_READY" if is_group and card.get("odds_fixture_id") else "STRUCTURAL_PLACEHOLDER",
        "last_pre_kickoff_odds": "WAIT_LATER_PRE_KICKOFF_SNAPSHOT" if is_group and card.get("odds_fixture_id") else "STRUCTURAL_PLACEHOLDER",
        "odds_observation_delta": movement.get("eligibility_status") or "NOT_AVAILABLE",
        "market_coverage_types": sorted(market.keys()),
        "has_native_opening": False,
        "has_native_closing": False,
        "no_money_flow_judgment": True,
        "display_text": (
            "赔率轮询字段已准备：first_seen_odds / last_pre_kickoff_odds / odds_observation_delta；"
            "原生开盘/收盘缺失；不生成盘口/资金流结论。"
            if is_group
            else "淘汰赛结构占位：等待真实 fixture 后再绑定 odds。"
        ),
    }


def data_gaps(card: dict[str, Any], coverage: dict[str, Any]) -> list[str]:
    if card.get("card_kind") == "KNOCKOUT_SLOT":
        return [
            "KNOCKOUT_STRUCTURAL_PLACEHOLDER_WAIT_OFFICIAL_TEAMS",
            "KNOCKOUT_STRUCTURAL_PLACEHOLDER_WAIT_OFFICIAL_FIXTURE",
            "WAIT_OFFICIAL_LINEUP",
            "NO_NATIVE_OPENING_CLOSING_ODDS",
        ]
    gaps = list(coverage.get("gap_reasons") or [])
    gaps.extend(["WAIT_OFFICIAL_LINEUP", "NO_NATIVE_OPENING_CLOSING_ODDS"])
    return sorted(dict.fromkeys(gaps))


def render_markdown_card(card: dict[str, Any]) -> str:
    lines = [
        f"## {card['match_title']}",
        "",
        f"- 比赛：{card['match_label']}",
        f"- 时间：{card['kickoff_display']}",
        f"- 场馆：{card['venue_display']}",
        f"- 阶段：{card['stage_display']}",
        f"- 双方 Final26 摘要：{card['final26_summary']}",
        f"- venue stress：{card['venue_stress_summary']}",
        f"- lineup status：{card['lineup_status']}",
        f"- odds status：{card['odds_status']['display_text']}",
        f"- data gaps：{' / '.join(card['data_gaps'])}",
        "",
        "安全提示：observation-only；不生成首发、不生成预测、不输出投注建议、不影响 V4。",
        "",
    ]
    return "\n".join(lines)


def build() -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    canonical = load_json(CANONICAL_104, [])
    match_cards = load_json(MATCH_CARDS, [])
    coverage_rows = load_json(COVERAGE_RADAR, [])
    profiles_list = load_json(PROFILE_CARDS, [])
    venue_stress = load_json(VENUE_STRESS, {})
    movement_status = load_json(ODDS_MOVEMENT_STATUS, {})
    live_status = load_json(ODDS_LIVE_STATUS, {})

    source_cards = index_by(match_cards if isinstance(match_cards, list) else [], "match_id")
    coverage = index_by(coverage_rows if isinstance(coverage_rows, list) else [], "canonical_card_id")
    profiles = index_by(profiles_list if isinstance(profiles_list, list) else [], "team_slug")
    venues = index_by((venue_stress.get("venues") or []) if isinstance(venue_stress, dict) else [], "venue")
    movement = movement_status.get("movement_eligibility") if isinstance(movement_status.get("movement_eligibility"), dict) else {}

    cards: list[dict[str, Any]] = []
    for card in canonical if isinstance(canonical, list) else []:
        if not isinstance(card, dict):
            continue
        source = source_cards.get(match_ref_id(card))
        cov = coverage.get(str(card.get("canonical_card_id")), {})
        home, away = team_display(card)
        title = f"{home} vs {away}"
        if card.get("card_kind") == "KNOCKOUT_SLOT":
            title = f"{stage_display(card)} 第 {card.get('slot_number')} 卡位"
        home_profile = profile_summary(card.get("home_team_slug"), profiles)
        away_profile = profile_summary(card.get("away_team_slug"), profiles)
        final26 = "结构占位：等待真实对阵后绑定 Final26"
        if card.get("card_kind") == "GROUP_STAGE_MATCH":
            final26 = f"{home_profile}；{away_profile}"
        brief = {
            "canonical_card_id": card.get("canonical_card_id"),
            "match_card_id": card.get("match_card_id"),
            "card_kind": card.get("card_kind"),
            "match_title": title,
            "match_label": title,
            "kickoff_display": kickoff_display(card, source),
            "venue_display": str(card.get("venue_name") or "场馆待确认"),
            "venue_source_provenance": card.get("source_provenance") or card.get("venue_source_type"),
            "stage_display": stage_display(card),
            "home_team": card.get("home_team"),
            "away_team": card.get("away_team"),
            "home_team_slug": card.get("home_team_slug"),
            "away_team_slug": card.get("away_team_slug"),
            "final26_summary": final26,
            "home_final26_summary": home_profile,
            "away_final26_summary": away_profile,
            "venue_stress_summary": venue_summary(card, venues),
            "lineup_status": "WAIT_OFFICIAL_LINEUP" if card.get("card_kind") == "GROUP_STAGE_MATCH" else "STRUCTURAL_PLACEHOLDER",
            "matchday_lineup_source": "WAIT_OFFICIAL_LINEUP",
            "odds_status": odds_status(card, cov, movement, live_status),
            "data_gaps": data_gaps(card, cov),
            "mobile_reading": True,
            **SAFETY,
        }
        cards.append(brief)

    group_count = sum(1 for card in cards if card.get("card_kind") == "GROUP_STAGE_MATCH")
    knockout_count = sum(1 for card in cards if card.get("card_kind") == "KNOCKOUT_SLOT")
    summary = {
        "pack_name": "V3_WC_2026_MATCHDAY_BRIEF_TEMPLATE_PACK",
        "generated_at": stable_generated_at(),
        "template": rel(TEMPLATE),
        "brief_cards": rel(OUT_JSON),
        "brief_markdown": rel(OUT_MD),
        "canonical_source": rel(CANONICAL_104),
        "match_count": len(cards),
        "group_stage_count": group_count,
        "knockout_slot_count": knockout_count,
        "cards_with_venue": sum(1 for card in cards if card.get("venue_display") and card.get("venue_display") != "场馆待确认"),
        "cards_wait_official_lineup": sum(1 for card in cards if card.get("lineup_status") == "WAIT_OFFICIAL_LINEUP"),
        "knockout_structural_placeholder_count": sum(1 for card in cards if card.get("lineup_status") == "STRUCTURAL_PLACEHOLDER"),
        "odds_fields_allowed": ["first_seen_odds", "last_pre_kickoff_odds", "odds_observation_delta"],
        "native_opening_closing_used": False,
        "money_flow_conclusion_generated": False,
        "mobile_reading": True,
        "safety": SAFETY,
    }
    md = "\n".join(
        [
            "# V3 世界杯赛前情报卡",
            "",
            "observation-only。只做手机阅读情报卡，不生成首发、不生成预测、不输出投注建议、不影响 V4。",
            "",
            f"- 完整赛程：{len(cards)} 场",
            f"- 小组赛：{group_count} 场",
            f"- 淘汰赛结构卡位：{knockout_count} 场",
            "",
            *(render_markdown_card(card) for card in cards),
        ]
    )
    return cards, summary, md


def main() -> int:
    cards, summary, md = build()
    WAR_ROOM.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(json.dumps({"conclusion": "PASS", "cards": len(cards), "summary": rel(OUT_SUMMARY)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
