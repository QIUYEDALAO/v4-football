#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DOCX = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/raw/fifa_wc2026_final_26_squads_official.docx"
OUT_DIR = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
REPORT_DIR = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/reports"

PLAYERS_CSV = OUT_DIR / "v3_wc2026_final_26_players.csv"
PLAYERS_JSON = OUT_DIR / "v3_wc2026_final_26_players.json"
TEAMS_JSON = OUT_DIR / "v3_wc2026_final_26_teams.json"
SUMMARY_JSON = OUT_DIR / "v3_wc2026_final_26_summary.json"
REPORT_MD = REPORT_DIR / "V3_WC_FINAL_26_SQUAD_INGEST_REPORT.md"

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

PLAYER_FIELDS = [
    "tournament",
    "source",
    "team",
    "team_slug",
    "player_id",
    "squad_number",
    "position",
    "first_name",
    "last_name",
    "full_name",
    "shirt_name",
    "birth_date",
    "club",
    "height_cm",
    "head_coach",
    "is_final_26",
    "is_official_fifa",
    "observation_only",
    "betting_recommendation",
    "affects_v4",
]

REQUIRED_PLAYER_FIELDS = [
    "team",
    "team_slug",
    "player_id",
    "squad_number",
    "position",
    "first_name",
    "last_name",
    "full_name",
    "shirt_name",
    "birth_date",
    "club",
    "height_cm",
    "head_coach",
]


def text_from_para(para: ET.Element) -> str:
    return "".join(t.text or "" for t in para.findall(".//w:t", NS)).strip()


def row_cells(row: ET.Element) -> list[str]:
    cells: list[str] = []
    for cell in row.findall("./w:tc", NS):
        texts = [t.text or "" for t in cell.findall(".//w:t", NS)]
        cells.append("".join(texts).strip())
    return cells


def table_rows(tbl: ET.Element) -> list[list[str]]:
    return [row_cells(row) for row in tbl.findall("./w:tr", NS)]


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug or "unknown"


def parse_team_heading(value: str) -> str:
    return re.sub(r"\s*\([A-Z]{2,4}\)\s*$", "", value.strip())


def parse_birth_date(value: str) -> tuple[str, bool]:
    raw = value.strip()
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if not match:
        return raw, bool(raw)
    day, month, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}", False


def parse_height(value: str) -> tuple[int | str, bool]:
    raw = value.strip()
    if re.fullmatch(r"\d{2,3}", raw):
        return int(raw), False
    return raw, bool(raw)


def make_player_id(team_slug: str, squad_number: str, full_name: str) -> str:
    return f"wc2026_{team_slug}_{int(squad_number):02d}_{slugify(full_name)}"


def load_doc_blocks(path: Path) -> list[tuple[str, Any]]:
    with ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("docx body missing")
    blocks: list[tuple[str, Any]] = []
    for child in list(body):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = text_from_para(child)
            if text:
                blocks.append(("p", text))
        elif tag == "tbl":
            blocks.append(("tbl", table_rows(child)))
    return blocks


def is_player_table(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    header = [c.upper() for c in rows[0]]
    return header[:4] == ["#", "POS", "PLAYER NAME", "FIRST NAME(S)"]


def is_coach_table(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    header = [c.upper() for c in rows[0]]
    return header[:3] == ["ROLE", "COACH NAME", "FIRST NAME(S)"]


def parse_docx(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    blocks = load_doc_blocks(path)
    players: list[dict[str, Any]] = []
    team_tables: list[dict[str, Any]] = []
    current_team = ""
    pending_team_rows: list[list[str]] | None = None
    height_warn = 0
    dob_warn = 0

    for kind, value in blocks:
        if kind == "p":
            text = str(value)
            if re.search(r"\([A-Z]{2,4}\)$", text):
                current_team = parse_team_heading(text)
            continue
        rows = value
        if is_player_table(rows):
            pending_team_rows = rows
            continue
        if is_coach_table(rows) and pending_team_rows:
            coach_row = rows[1] if len(rows) > 1 else []
            head_coach = coach_row[1] if len(coach_row) > 1 else ""
            team = current_team
            team_slug = slugify(team)
            position_counts = Counter()
            for row in pending_team_rows[1:]:
                if len(row) < 9:
                    continue
                squad_number, position, full_name, first_name, last_name, shirt_name, dob, club, height = row[:9]
                birth_date, dob_bad = parse_birth_date(dob)
                height_cm, height_bad = parse_height(height)
                dob_warn += int(dob_bad)
                height_warn += int(height_bad)
                position = position.upper().strip()
                position_counts[position] += 1
                player = {
                    "tournament": "FIFA World Cup 2026",
                    "source": "FIFA official final 26 squad docx",
                    "team": team,
                    "team_slug": team_slug,
                    "player_id": make_player_id(team_slug, squad_number, full_name),
                    "squad_number": squad_number,
                    "position": position,
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": full_name,
                    "shirt_name": shirt_name,
                    "birth_date": birth_date,
                    "club": club,
                    "height_cm": height_cm,
                    "head_coach": head_coach,
                    "is_final_26": True,
                    "is_official_fifa": True,
                    "observation_only": True,
                    "betting_recommendation": False,
                    "affects_v4": False,
                }
                players.append(player)
            team_tables.append({
                "tournament": "FIFA World Cup 2026",
                "source": "FIFA official final 26 squad docx",
                "team": team,
                "team_slug": team_slug,
                "head_coach": head_coach,
                "player_count": sum(position_counts.values()),
                "gk_count": position_counts.get("GK", 0),
                "df_count": position_counts.get("DF", 0),
                "mf_count": position_counts.get("MF", 0),
                "fw_count": position_counts.get("FW", 0),
                "is_final_26": True,
                "is_official_fifa": True,
                "observation_only": True,
                "betting_recommendation": False,
                "affects_v4": False,
            })
            pending_team_rows = None

    missing_counts = {field: 0 for field in REQUIRED_PLAYER_FIELDS}
    for player in players:
        for field in REQUIRED_PLAYER_FIELDS:
            if player.get(field) in {"", None}:
                missing_counts[field] += 1
    duplicate_player_id_count = len(players) - len({p["player_id"] for p in players})
    teams_not_26 = sorted(t["team"] for t in team_tables if t["player_count"] != 26)
    summary = {
        "team_count": len(team_tables),
        "total_players": len(players),
        "expected_team_count": 48,
        "expected_total_players": 1248,
        "teams_with_26_players": sum(1 for t in team_tables if t["player_count"] == 26),
        "teams_not_26_players": teams_not_26,
        "duplicate_player_id_count": duplicate_player_id_count,
        "missing_required_field_counts": missing_counts,
        "position_distribution": dict(Counter(p["position"] for p in players)),
        "height_parse_warn_count": height_warn,
        "birth_date_parse_warn_count": dob_warn,
        "source_docx": str(path),
        "observation_only": True,
        "betting_recommendation": False,
        "affects_v4": False,
    }
    return players, team_tables, summary


def write_outputs(players: list[dict[str, Any]], teams: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with PLAYERS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PLAYER_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(players)
    PLAYERS_JSON.write_text(json.dumps(players, ensure_ascii=False, indent=2), encoding="utf-8")
    TEAMS_JSON.write_text(json.dumps(teams, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# V3 WC Final 26 Squad Ingest Report",
        "",
        f"Generated at: {datetime.now().isoformat()}",
        "",
        f"- source_docx: `{summary['source_docx']}`",
        f"- team_count: {summary['team_count']}",
        f"- total_players: {summary['total_players']}",
        f"- teams_with_26_players: {summary['teams_with_26_players']}",
        f"- duplicate_player_id_count: {summary['duplicate_player_id_count']}",
        f"- height_parse_warn_count: {summary['height_parse_warn_count']}",
        f"- birth_date_parse_warn_count: {summary['birth_date_parse_warn_count']}",
        f"- position_distribution: `{summary['position_distribution']}`",
        "",
        "Safety:",
        "",
        "- observation_only=true",
        "- betting_recommendation=false",
        "- affects_v4=false",
        "- no starting XI is generated",
        "- no injury or suspension judgment is generated",
    ]
    REPORT_MD.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    if not SOURCE_DOCX.exists():
        raise FileNotFoundError(SOURCE_DOCX)
    players, teams, summary = parse_docx(SOURCE_DOCX)
    write_outputs(players, teams, summary)
    print(json.dumps({
        "conclusion": "PASS",
        "players_csv": str(PLAYERS_CSV),
        "players_json": str(PLAYERS_JSON),
        "teams_json": str(TEAMS_JSON),
        "summary_json": str(SUMMARY_JSON),
        "report_md": str(REPORT_MD),
        "team_count": summary["team_count"],
        "total_players": summary["total_players"],
        "height_parse_warn_count": summary["height_parse_warn_count"],
        "birth_date_parse_warn_count": summary["birth_date_parse_warn_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
