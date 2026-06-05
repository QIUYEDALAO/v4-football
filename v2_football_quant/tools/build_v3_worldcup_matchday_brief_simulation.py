#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_v3_worldcup_matchday_brief_template import SAFETY, build as build_brief_cards, rel

ROOT = Path(__file__).resolve().parents[1]
WAR_ROOM = ROOT / "data/manual_sources/v3_worldcup/war_room"

OUT_JSON = WAR_ROOM / "v3_wc2026_matchday_brief_simulation.json"
OUT_MD = WAR_ROOM / "V3_WC2026_MATCHDAY_BRIEF_SIMULATION.md"
OUT_SUMMARY = WAR_ROOM / "v3_wc2026_matchday_brief_simulation_summary.json"

TIMEPOINTS = ["T-24h", "T-6h", "T-90m", "T-30m"]


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def stable_generated_at() -> str:
    existing = load_json(OUT_SUMMARY, {})
    if isinstance(existing, dict) and existing.get("generated_at"):
        return str(existing["generated_at"])
    return datetime.now(timezone.utc).isoformat()


def mock_odds_timeline() -> list[dict[str, Any]]:
    return [
        {
            "timepoint": "T-24h",
            "snapshot_role": "first_seen_odds",
            "first_seen_odds": {"home": 2.42, "draw": 3.18, "away": 2.96},
            "last_pre_kickoff_odds": None,
            "odds_observation_delta": "BASELINE_MOCK_SNAPSHOT",
        },
        {
            "timepoint": "T-6h",
            "snapshot_role": "odds_observation_delta",
            "first_seen_odds": {"home": 2.42, "draw": 3.18, "away": 2.96},
            "last_pre_kickoff_odds": None,
            "odds_observation_delta": {"home": -0.02, "draw": 0.01, "away": 0.03},
        },
        {
            "timepoint": "T-90m",
            "snapshot_role": "odds_observation_delta",
            "first_seen_odds": {"home": 2.42, "draw": 3.18, "away": 2.96},
            "last_pre_kickoff_odds": None,
            "odds_observation_delta": {"home": -0.04, "draw": 0.02, "away": 0.04},
        },
        {
            "timepoint": "T-30m",
            "snapshot_role": "last_pre_kickoff_odds",
            "first_seen_odds": {"home": 2.42, "draw": 3.18, "away": 2.96},
            "last_pre_kickoff_odds": {"home": 2.38, "draw": 3.2, "away": 3.0},
            "odds_observation_delta": {"home": -0.04, "draw": 0.02, "away": 0.04},
        },
    ]


def format_odds_line(row: dict[str, Any]) -> str:
    first = row.get("first_seen_odds") or {}
    last = row.get("last_pre_kickoff_odds") or {}
    delta = row.get("odds_observation_delta")
    first_text = f"{first.get('home')}/{first.get('draw')}/{first.get('away')}" if first else "N/A"
    last_text = f"{last.get('home')}/{last.get('draw')}/{last.get('away')}" if last else "等待后续快照"
    delta_text = delta if isinstance(delta, str) else f"主{delta.get('home')} / 平{delta.get('draw')} / 客{delta.get('away')}"
    return (
        f"{row['timepoint']}：首见 {first_text}；赛前最后 {last_text}；观察差 {delta_text}"
    )


def render_md(sim: dict[str, Any]) -> str:
    card = sim["brief_card"]
    odds_lines = "｜".join(format_odds_line(row) for row in sim["mock_odds_timeline"])
    return "\n".join(
        [
            "# 世界杯赛前情报卡（手机样例）",
            "",
            "仅观察，不推荐。以下为本地模拟样例，不调用实时接口。",
            "",
            "## 1. 比赛信息",
            "",
            f"{card['match_label']}｜{card['stage_display']}｜{card['kickoff_display']}｜{card['venue_display']}",
            "",
            "## 2. 战备状态",
            "",
            f"Final26 已入库。{card['final26_summary']}",
            "",
            "## 3. 阵容状态",
            "",
            "官方首发未到：WAIT_OFFICIAL_LINEUP。当前不生成预测首发，不做伤停判断。",
            "",
            "## 4. 场馆/环境",
            "",
            card["venue_stress_summary"],
            "",
            "## 5. 赔率观察",
            "",
            odds_lines,
            "",
            "只看首见赔率、赛前最后快照、观察差；原生开盘/收盘缺失，不生成盘口或资金流结论。",
            "",
            "## 6. 当前缺口",
            "",
            " / ".join(card["data_gaps"]),
            "",
            "## 7. 结论：仅观察，不推荐",
            "",
            "这是一张赛前情报卡，不是投注建议；不生成首发、不生成预测、不影响 V4 official。",
            "",
        ]
    )


def build() -> tuple[dict[str, Any], dict[str, Any], str]:
    cards, _, _ = build_brief_cards()
    sample = next(card for card in cards if card.get("card_kind") == "GROUP_STAGE_MATCH")
    timeline = mock_odds_timeline()
    sim = {
        "pack_name": "V3_WC_2026_MATCHDAY_BRIEF_SIMULATION_PACK",
        "generated_at": stable_generated_at(),
        "simulation_mode": "LOCAL_MOCK_ODDS_ONLY",
        "live_api_called": False,
        "timepoints": TIMEPOINTS,
        "sample_match": sample.get("match_label"),
        "brief_card": {
            **sample,
            "odds_status": {
                **(sample.get("odds_status") if isinstance(sample.get("odds_status"), dict) else {}),
                "mock_odds_used": True,
                "allowed_fields": ["first_seen_odds", "last_pre_kickoff_odds", "odds_observation_delta"],
                "has_native_opening": False,
                "has_native_closing": False,
                "no_money_flow_judgment": True,
            },
        },
        "mock_odds_timeline": timeline,
        "mobile_reading": True,
        **SAFETY,
    }
    summary = {
        "pack_name": sim["pack_name"],
        "generated_at": sim["generated_at"],
        "simulation": rel(OUT_JSON),
        "brief_markdown": rel(OUT_MD),
        "sample_match": sim["sample_match"],
        "timepoint_count": len(TIMEPOINTS),
        "timepoints": TIMEPOINTS,
        "live_api_called": False,
        "mock_odds_used": True,
        "lineup_status": sim["brief_card"].get("lineup_status"),
        "allowed_odds_fields": ["first_seen_odds", "last_pre_kickoff_odds", "odds_observation_delta"],
        "native_opening_closing_used": False,
        "money_flow_conclusion_generated": False,
        "mobile_reading": True,
        "safety": SAFETY,
    }
    return sim, summary, render_md(sim)


def main() -> int:
    sim, summary, md = build()
    WAR_ROOM.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(sim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(json.dumps({"conclusion": "PASS", "sample_match": sim["sample_match"], "output": rel(OUT_JSON)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
