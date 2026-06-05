#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from build_v3_worldcup_matchday_brief_template import OUT_JSON, OUT_MD, OUT_SUMMARY, TEMPLATE, build

ROOT = Path(__file__).resolve().parents[1]
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_matchday_brief_template_20260605.json"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
DISALLOWED_TEXT = [
    "true opening",
    "true closing",
    "steam",
    "drift",
    "fund_flow",
    "fund flow",
    "money flow",
    "sharp move",
    "predicted xi",
    "starting xi players",
]


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def main() -> int:
    cards, summary, md = build()
    OUT_JSON.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")

    failures: list[str] = []
    for path in [TEMPLATE, OUT_JSON, OUT_SUMMARY, OUT_MD]:
        add(failures, path.exists(), "required_file_missing", str(path.relative_to(ROOT)))
    add(failures, len(cards) == 104, "brief_card_count_unexpected", len(cards))
    add(failures, summary.get("match_count") == 104, "summary_match_count_unexpected", summary.get("match_count"))
    add(failures, summary.get("group_stage_count") == 72, "summary_group_count_unexpected", summary.get("group_stage_count"))
    add(failures, summary.get("knockout_slot_count") == 32, "summary_knockout_count_unexpected", summary.get("knockout_slot_count"))
    add(failures, summary.get("cards_with_venue") == 104, "cards_with_venue_unexpected", summary.get("cards_with_venue"))
    add(failures, summary.get("cards_wait_official_lineup") == 72, "lineup_wait_count_unexpected", summary.get("cards_wait_official_lineup"))
    add(failures, summary.get("knockout_structural_placeholder_count") == 32, "knockout_placeholder_count_unexpected", summary.get("knockout_structural_placeholder_count"))
    add(failures, summary.get("native_opening_closing_used") is False, "native_opening_closing_used_true")
    add(failures, summary.get("money_flow_conclusion_generated") is False, "money_flow_conclusion_generated_true")
    add(failures, summary.get("mobile_reading") is True, "mobile_reading_false")

    group = [card for card in cards if card.get("card_kind") == "GROUP_STAGE_MATCH"]
    knockout = [card for card in cards if card.get("card_kind") == "KNOCKOUT_SLOT"]
    add(failures, len(group) == 72, "group_cards_unexpected", len(group))
    add(failures, len(knockout) == 32, "knockout_cards_unexpected", len(knockout))

    for card in group:
        cid = card.get("canonical_card_id")
        add(failures, " vs " in str(card.get("match_label")), "group_match_label_unexpected", cid)
        add(failures, card.get("lineup_status") == "WAIT_OFFICIAL_LINEUP", "group_lineup_status_unexpected", cid)
        add(failures, "WAIT_OFFICIAL_LINEUP" in card.get("data_gaps", []), "group_lineup_gap_missing", cid)
        add(failures, "NO_NATIVE_OPENING_CLOSING_ODDS" in card.get("data_gaps", []), "group_native_odds_gap_missing", cid)
        add(failures, "Final26" not in str(card.get("final26_summary")) or "缺失" not in str(card.get("final26_summary")), "group_final26_summary_gap", cid)

    for card in knockout:
        cid = card.get("canonical_card_id")
        add(failures, card.get("home_team") is None and card.get("away_team") is None, "knockout_team_generated", cid)
        add(failures, card.get("lineup_status") == "STRUCTURAL_PLACEHOLDER", "knockout_lineup_status_unexpected", cid)
        add(failures, "结构占位" in str(card.get("match_label")) or "卡位" in str(card.get("match_title")), "knockout_placeholder_text_missing", cid)
        add(failures, "KNOCKOUT_STRUCTURAL_PLACEHOLDER_WAIT_OFFICIAL_TEAMS" in card.get("data_gaps", []), "knockout_team_gap_missing", cid)

    for card in cards:
        cid = card.get("canonical_card_id")
        for key, expected in {
            "observation_only": True,
            "no_starting_xi_generated": True,
            "no_prediction": True,
            "no_injury_judgment": True,
            "betting_recommendation": False,
            "affects_v4": False,
        }.items():
            add(failures, card.get(key) is expected, f"safety_{key}_unexpected", cid)
        odds = card.get("odds_status") if isinstance(card.get("odds_status"), dict) else {}
        add(failures, "first_seen_odds" in odds, "first_seen_odds_missing", cid)
        add(failures, "last_pre_kickoff_odds" in odds, "last_pre_kickoff_odds_missing", cid)
        add(failures, "odds_observation_delta" in odds, "odds_observation_delta_missing", cid)
        add(failures, odds.get("has_native_opening") is False, "native_opening_true", cid)
        add(failures, odds.get("has_native_closing") is False, "native_closing_true", cid)
        add(failures, odds.get("no_money_flow_judgment") is True, "money_flow_guard_missing", cid)

    combined = json.dumps({"cards": cards, "summary": summary}, ensure_ascii=False).lower() + "\n" + md.lower()
    for phrase in DISALLOWED_TEXT:
        add(failures, phrase not in combined, "disallowed_text", phrase)
    add(failures, "starting_xi_players" not in combined, "starting_xi_players_generated")

    staged = staged_files()
    runtime_staged = [path for path in staged if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    secrets = secret_hits([TEMPLATE, OUT_JSON, OUT_SUMMARY, OUT_MD, Path(__file__).resolve(), ROOT / "tools/build_v3_worldcup_matchday_brief_template.py"])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "brief_cards": str(OUT_JSON.relative_to(ROOT)),
        "brief_markdown": str(OUT_MD.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
        "match_count": len(cards),
        "group_stage_count": len(group),
        "knockout_slot_count": len(knockout),
        "sample_match": cards[0] if cards else {},
        "runtime_staged": runtime_staged,
        "v4_staged": v4_staged,
        "secret_hits": secrets,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
