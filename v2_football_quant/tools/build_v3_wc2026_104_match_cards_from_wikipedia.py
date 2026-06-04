#!/usr/bin/env python3
"""
V3 WC 2026 — 104 Match Card Builder from Wikipedia Snapshot
============================================================
Produces 104 match cards compatible with existing v3_wc_match_cards.json format.
Source: Saved Wikipedia full-page snapshot (post-2025-12-06 draw, all teams & venues final).

SAFETY:
  - observation_only = True
  - no_starting_xi_generated = True
  - no_prediction = True
  - betting_recommendation = False
  - affects_v4 = False
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "../v4-football/reports/v3_wc2026_source_validation/wikipedia_2026_full_page.json"
OUT_DIR = ROOT / "data/manual_sources/v3_worldcup/war_room"
MATCH_CARDS = OUT_DIR / "v3_wc_match_cards.json"
MATCH_SUMMARY = OUT_DIR / "v3_wc_match_card_summary.json"

SAFETY = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_prediction": True,
    "no_injury_judgment": True,
    "betting_recommendation": False,
    "affects_v4": False,
}


def slugify(text: str) -> str:
    cleaned = (
        text.lower()
        .replace("&", "and")
        .replace("'", "")
        .replace("ç", "c")
        .replace("ô", "o")
        .replace("ü", "u")
        .replace("é", "e")
        .replace("í", "i")
    )
    return "_".join(part for part in "".join(ch if ch.isalnum() else " " for ch in cleaned).split() if part)


def html_unescape(s: str) -> str:
    s = s.replace("&#160;", " ")
    s = s.replace("&amp;", "&")
    s = s.replace("&lt;", "<")
    s = s.replace("&gt;", ">")
    s = s.replace("&quot;", '"')
    s = re.sub(r"\s+", " ", s).strip()
    return s


TEAM_CANONICAL = {
    "Mexico national football team": "Mexico",
    "South Africa national soccer team": "South Africa",
    "South Korea national football team": "South Korea",
    "Czech Republic national football team": "Czech Republic",
    "Canada men's national soccer team": "Canada",
    "Bosnia and Herzegovina national football team": "Bosnia and Herzegovina",
    "United States men's national soccer team": "United States",
    "Sweden men's national football team": "Sweden",
    "Cameroon national football team": "Cameroon",
    "Argentina national football team": "Argentina",
    "Paraguay national football team": "Paraguay",
    "Tahiti national football team": "Tahiti",
    "Germany national football team": "Germany",
    "Kazakhstan national football team": "Kazakhstan",
    "Portugal national football team": "Portugal",
    "Mali national football team": "Mali",
    "Brazil national football team": "Brazil",
    "Ivory Coast national football team": "Ivory Coast",
    "Côte D'Ivoire national football team": "Ivory Coast",
    "Côte d'Ivoire national football team": "Ivory Coast",
    "Japan national football team": "Japan",
    "Iran national football team": "Iran",
    "Saudi Arabia national football team": "Saudi Arabia",
    "Qatar national football team": "Qatar",
    "Netherlands national football team": "Netherlands",
    "Colombia national football team": "Colombia",
    "Egypt national football team": "Egypt",
    "Algeria national football team": "Algeria",
    "Austria national football team": "Austria",
    "Croatia national football team": "Croatia",
    "Nigeria national football team": "Nigeria",
    "France national football team": "France",
    "Italy national football team": "Italy",
    "Belgium national football team": "Belgium",
    "Senegal national football team": "Senegal",
    "Hungary national football team": "Hungary",
    "Spain national football team": "Spain",
    "Uruguay national football team": "Uruguay",
    "England national football team": "England",
    "Denmark national football team": "Denmark",
    "Australia men's national soccer team": "Australia",
    "Ghana national football team": "Ghana",
    "Morocco national football team": "Morocco",
    "Poland national football team": "Poland",
    "Türkiye national football team": "Turkey",
    "Turkey national football team": "Turkey",
    "Ecuador national football team": "Ecuador",
    "Venezuela national football team": "Venezuela",
    "Chile national football team": "Chile",
    "Peru national football team": "Peru",
    "Switzerland national football team": "Switzerland",
    "Wales national football team": "Wales",
    "Scotland national football team": "Scotland",
    "Norway national football team": "Norway",
    "Ukraine national football team": "Ukraine",
    "Romania national football team": "Romania",
    "Serbia national football team": "Serbia",
    "Slovenia national football team": "Slovenia",
    "New Zealand men's national football team": "New Zealand",
    "Ireland national football team": "Ireland",
    "Iceland national football team": "Iceland",
    "Greece national football team": "Greece",
    "Finland national football team": "Finland",
    "Slovakia national football team": "Slovakia",
    "Israel national football team": "Israel",
    "North Macedonia national football team": "North Macedonia",
    "Montenegro national football team": "Montenegro",
    "Georgia national football team": "Georgia",
    "Panama national football team": "Panama",
    "Jamaica national football team": "Jamaica",
    "Costa Rica national football team": "Costa Rica",
    "United Arab Emirates national football team": "UAE",
    "Tunisia national football team": "Tunisia",
    "Democratic Republic of the Congo national football team": "Congo DR",
    "Congo DR national football team": "Congo DR",
    "Burkina Faso national football team": "Burkina Faso",
    "Guinea national football team": "Guinea",
    "Equatorial Guinea national football team": "Equatorial Guinea",
    "Zambia national football team": "Zambia",
    "Benin national football team": "Benin",
    "Oman national football team": "Oman",
    "Kuwait national football team": "Kuwait",
    "Indonesia national football team": "Indonesia",
    "China national football team": "China",
    "China PR national football team": "China",
    "Chinese Taipei national football team": "Chinese Taipei",
    "Thailand national football team": "Thailand",
    "Vietnam national football team": "Vietnam",
    "Malaysia national football team": "Malaysia",
    "Singapore national football team": "Singapore",
    "Philippines national football team": "Philippines",
    "India national football team": "India",
    "Pakistan national football team": "Pakistan",
    "Bangladesh national football team": "Bangladesh",
    "Sri Lanka national football team": "Sri Lanka",
    "Nepal national football team": "Nepal",
    "Maldives national football team": "Maldives",
    "Bhutan national football team": "Bhutan",
    "Myanmar national football team": "Myanmar",
    "Cambodia national football team": "Cambodia",
    "Laos national football team": "Laos",
    "Brunei national football team": "Brunei",
    "Timor-Leste national football team": "Timor-Leste",
    "Macau national football team": "Macau",
    "Hong Kong national football team": "Hong Kong",
    "Mongolia national football team": "Mongolia",
    "Afghanistan national football team": "Afghanistan",
    "Turkmenistan national football team": "Turkmenistan",
    "Uzbekistan national football team": "Uzbekistan",
    "Tajikistan national football team": "Tajikistan",
    "Kyrgyzstan national football team": "Kyrgyzstan",
    "North Korea national football team": "North Korea",
    "DPR Korea national football team": "North Korea",
    "Syria national football team": "Syria",
    "Jordan national football team": "Jordan",
    "Iraq national football team": "Iraq",
    "Lebanon national football team": "Lebanon",
    "Bahrain national football team": "Bahrain",
    "Yemen national football team": "Yemen",
    "Palestine national football team": "Palestine",
    "Sudan national football team": "Sudan",
    "South Sudan national football team": "South Sudan",
    "Eritrea national football team": "Eritrea",
    "Ethiopia national football team": "Ethiopia",
    "Djibouti national football team": "Djibouti",
    "Somalia national football team": "Somalia",
    "Kenya national football team": "Kenya",
    "Uganda national football team": "Uganda",
    "Rwanda national football team": "Rwanda",
    "Burundi national football team": "Burundi",
    "Tanzania national football team": "Tanzania",
    "Malawi national football team": "Malawi",
    "Mozambique national football team": "Mozambique",
    "Angola national football team": "Angola",
    "Namibia national football team": "Namibia",
    "Botswana national football team": "Botswana",
    "Zimbabwe national football team": "Zimbabwe",
    "Comoros national football team": "Comoros",
    "Madagascar national football team": "Madagascar",
    "Seychelles national football team": "Seychelles",
    "Mauritius national football team": "Mauritius",
    "Mauritania national football team": "Mauritania",
    "Niger national football team": "Niger",
    "Mali national football team": "Mali",
    "Chad national football team": "Chad",
    "Togo national football team": "Togo",
    "Liberia national football team": "Liberia",
    "Sierra Leone national football team": "Sierra Leone",
    "Guinea-Bissau national football team": "Guinea-Bissau",
    "Gambia national football team": "Gambia",
    "Cape Verde national football team": "Cape Verde",
    "São Tomé and Príncipe national football team": "Sao Tome",
    "Gabon national football team": "Gabon",
    "Central African Republic national football team": "Central African Republic",
    "Congo national football team": "Congo",
    "DR Congo national football team": "Congo DR",
    "Eswatini national football team": "Eswatini",
    "Lesotho national football team": "Lesotho",
    "South Africa national football team": "South Africa",
    "Fiji national football team": "Fiji",
    "New Caledonia national football team": "New Caledonia",
    "Papua New Guinea national football team": "Papua New Guinea",
    "Solomon Islands national football team": "Solomon Islands",
    "Vanuatu national football team": "Vanuatu",
    "Samoa national football team": "Samoa",
    "American Samoa national football team": "American Samoa",
    "Tonga national football team": "Tonga",
    "Cook Islands national football team": "Cook Islands",
    "Niue national football team": "Niue",
    "Tuvalu national football team": "Tuvalu",
    "Kiribati national football team": "Kiribati",
    "Nauru national football team": "Nauru",
    "Marshall Islands national football team": "Marshall Islands",
    "Palau national football team": "Palau",
    "Micronesia national football team": "Micronesia",
    "Bolivia national football team": "Bolivia",
    "Anguilla national football team": "Anguilla",
    "Antigua and Barbuda national football team": "Antigua and Barbuda",
    "Aruba national football team": "Aruba",
    "Bahamas national football team": "Bahamas",
    "Barbados national football team": "Barbados",
    "Belize national football team": "Belize",
    "Bermuda national football team": "Bermuda",
    "Bonaire national football team": "Bonaire",
    "British Virgin Islands national football team": "British Virgin Islands",
    "Cayman Islands national football team": "Cayman Islands",
    "Cuba national football team": "Cuba",
    "Curaçao national football team": "Curacao",
    "Dominica national football team": "Dominica",
    "Dominican Republic national football team": "Dominican Republic",
    "El Salvador national football team": "El Salvador",
    "Grenada national football team": "Grenada",
    "Guadeloupe national football team": "Guadeloupe",
    "Guatemala national football team": "Guatemala",
    "Guyana national football team": "Guyana",
    "Haiti national football team": "Haiti",
    "Honduras national football team": "Honduras",
    "Martinique national football team": "Martinique",
    "Montserrat national football team": "Montserrat",
    "Nicaragua national football team": "Nicaragua",
    "Puerto Rico national football team": "Puerto Rico",
    "Saint Kitts and Nevis national football team": "Saint Kitts and Nevis",
    "Saint Lucia national football team": "Saint Lucia",
    "Saint Martin national football team": "Saint Martin",
    "Saint Vincent and the Grenadines national football team": "Saint Vincent",
    "Sint Maarten national football team": "Sint Maarten",
    "Suriname national football team": "Suriname",
    "Trinidad and Tobago national football team": "Trinidad and Tobago",
    "Turks and Caicos Islands national football team": "Turks and Caicos Islands",
    "United States Virgin Islands national football team": "US Virgin Islands",
    "Albania national football team": "Albania",
    "Armenia national football team": "Armenia",
    "Azerbaijan national football team": "Azerbaijan",
    "Belarus national football team": "Belarus",
    "Bulgaria national football team": "Bulgaria",
    "Cyprus national football team": "Cyprus",
    "Estonia national football team": "Estonia",
    "Faroe Islands national football team": "Faroe Islands",
    "Gibraltar national football team": "Gibraltar",
    "Kosovo national football team": "Kosovo",
    "Latvia national football team": "Latvia",
    "Liechtenstein national football team": "Liechtenstein",
    "Lithuania national football team": "Lithuania",
    "Luxembourg national football team": "Luxembourg",
    "Malta national football team": "Malta",
    "Moldova national football team": "Moldova",
    "Monaco national football team": "Monaco",
    "Netherlands Antilles national football team": "Netherlands Antilles",
    "Northern Ireland national football team": "Northern Ireland",
    "North Macedonia national football team": "North Macedonia",
    "Republic of Ireland national football team": "Ireland",
    "San Marino national football team": "San Marino",
    "Serbia and Montenegro national football team": "Serbia and Montenegro",
    "Soviet Union national football team": "Soviet Union",
    "Czechoslovakia national football team": "Czechoslovakia",
    "East Germany national football team": "East Germany",
    "West Germany national football team": "West Germany",
    "Yugoslavia national football team": "Yugoslavia",
    "Zaire national football team": "Zaire",
    "Catalan national football team": "Catalonia",
    "Basque Country national football team": "Basque Country",
    "Galicia national football team": "Galicia",
    "Saarland national football team": "Saarland",
    "Siam national football team": "Siam",
    "South Vietnam national football team": "South Vietnam",
    "South Yemen national football team": "South Yemen",
    "North Yemen national football team": "North Yemen",
    "Neutral Olympic Athletes": "Neutral Olympic Athletes",
    "Unified Team": "Unified Team",
    "Independent Olympic Athletes": "Independent Olympic Athletes",
    "Refugee Olympic Team": "Refugee Olympic Team",
    "Olympic Athletes from Russia": "Olympic Athletes from Russia",
    "Russia national football team": "Russia",
    "ROC": "ROC",
    "Bohemia national football team": "Bohemia",
    "Great Britain national football team": "Great Britain",
    "Republic of Ireland national football team": "Republic of Ireland",
    "Ireland national football team": "Ireland",
    "Northern Ireland national football team": "Northern Ireland",
    "Scotland national football team": "Scotland",
    "Wales national football team": "Wales",
    "England national football team": "England",
    "Hong Kong national football team": "Hong Kong",
    "North Korea national football team": "North Korea",
    "South Korea national football team": "South Korea",
    "Myanmar national football team": "Myanmar",
    "Philippines national football team": "Philippines",
    "Indonesia national football team": "Indonesia",
    "Timor-Leste national football team": "Timor-Leste",
    "Australia national football team": "Australia",
    "New Zealand national football team": "New Zealand",
    "Fiji national football team": "Fiji",
    "Papua New Guinea national football team": "Papua New Guinea",
    "Solomon Islands national football team": "Solomon Islands",
    "Vanuatu national football team": "Vanuatu",
    "Samoa national football team": "Samoa",
    "Tahiti national football team": "Tahiti",
    "New Caledonia national football team": "New Caledonia",
}

GROUP_ROUND_MAP = {1: 1, 2: 2, 3: 3}  # matchday slot 1/2/3 -> round 1/2/3

KO_ROUND_MAP = {
    "Round of 32": "round_of_32",
    "Round of 16": "round_of_16",
    "Quarter-finals": "quarter_finals",
    "Semi-finals": "semi_finals",
    "Third place": "third_place",
    "Final": "final",
}

KO_ROUND_NUM_MAP = {
    "Round of 32": 32,
    "Round of 16": 16,
    "Quarter-finals": 8,
    "Semi-finals": 4,
    "Third place": 99,
    "Final": 100,
}


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def canonical_team(name: str) -> str:
    return TEAM_CANONICAL.get(name, name)


def extract_team_from_box(box_content: str, side: str) -> str | None:
    """
    Extract team name from a football box for given side (fhome / faway).
    Wikipedia structure:
      <th class="fhome" ...><a ... title="Mexico national football team">Mexico</a></th>
    """
    # Pattern for th with class containing fhome or faway
    pat = rf'class="[^"]*{side}[^"]*"[^>]*>.*?<a[^>]*title="([^"]*)"'
    m = re.search(pat, box_content, re.DOTALL)
    if m:
        return m.group(1)
    return None


def extract_venue_from_box(box_content: str) -> str | None:
    """Extract venue name from football box content."""
    # Location span
    m = re.search(r'class="location"[^>]*>.*?<a[^>]*title="([^"]*)"', box_content, re.DOTALL)
    if m:
        return m.group(1)
    # Direct stadium link
    m = re.search(r'<a[^>]*title="([^"]*(?:Stadium|Estadio|Field|Bowl)[^"]*)"', box_content)
    if m:
        return m.group(1)
    return None


def extract_match_id(box_content: str) -> int | None:
    m = re.search(r">Match\s+(\d+)<", box_content)
    if m:
        return int(m.group(1))
    return None


def extract_date(box_content: str) -> str | None:
    m = re.search(r'fdate">([^<]+)', box_content)
    if m:
        return html_unescape(m.group(1))
    return None


def extract_time(box_content: str) -> str | None:
    m = re.search(r'ftime">([^<]+)', box_content)
    if m:
        return m.group(1).strip()
    return None


def extract_timezone(box_content: str) -> str | None:
    m = re.search(r"UTC[−\-+]\s*\d{1,2}(?::\d{2})?", box_content)
    if m:
        return m.group(0).strip()
    return None


def parse_local_time_to_utc(date_str: str, time_str: str, tz_str: str) -> str | None:
    """Convert Wikipedia local time to UTC ISO string."""
    if not date_str or not time_str:
        return None
    try:
        # Parse date
        date_clean = date_str.replace(",", "").strip()
        # Parse time
        time_clean = time_str.replace("\u00a0", " ").strip()
        # Handle AM/PM
        is_pm = "p.m." in time_clean.lower()
        is_am = "a.m." in time_clean.lower()
        time_clean = time_clean.replace("p.m.", "").replace("a.m.", "").replace("PM", "").replace("AM", "").strip()

        parts = time_clean.split(":")
        hour = int(parts[0])
        minute = int(parts[1].split()[0]) if len(parts) > 1 else 0

        if is_pm and hour != 12:
            hour += 12
        if is_am and hour == 12:
            hour = 0

        # Parse timezone offset
        tz_clean = tz_str.replace("UTC", "").replace("\u2212", "-").replace("−", "-").strip()
        tz_hours = 0
        tz_minutes = 0
        if tz_clean:
            sign = -1 if tz_clean.startswith("-") else 1
            tz_clean = tz_clean.lstrip("+-")
            if ":" in tz_clean:
                tz_parts = tz_clean.split(":")
                tz_hours = int(tz_parts[0])
                tz_minutes = int(tz_parts[1]) if len(tz_parts) > 1 else 0
            else:
                tz_hours = int(tz_clean) if tz_clean else 0
            tz_hours *= sign
            tz_minutes *= sign

        from datetime import timedelta

        local_dt = datetime.strptime(f"{date_clean} {hour}:{minute:02d}", "%B %d %Y %H:%M")
        utc_dt = local_dt - timedelta(hours=tz_hours, minutes=tz_minutes)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except Exception:
        return None


def determine_matchday_group(box_pos: int, html: str, gs_start: int) -> tuple[str | None, int | None]:
    """Determine group letter and matchday (1/2/3) from nearest headings before box."""
    before = html[max(gs_start, box_pos - 50000):box_pos]

    # Find group
    group_m = re.findall(r'id="Group_([A-L])">Group [A-L]<', before)
    group_letter = group_m[-1] if group_m else None

    # Find matchday: Wikipedia shows date ranges per matchday in section 14
    # Matchday 1: June 11-17, Matchday 2: June 18-23, Matchday 3: June 24-27
    # Matchday is implicit from date, not an explicit heading.
    # We'll determine from match index within group (0-1=matchday1, 2-3=matchday2, 4-5=matchday3)

    return group_letter, None  # matchday determined by index within group


def find_all_football_boxes(html: str) -> list[dict[str, Any]]:
    """Extract all 104 football boxes with proper div nesting tracking."""
    boxes = []
    pat = 'class="footballbox"'
    search_from = 0

    while True:
        pos = html.find(pat, search_from)
        if pos == -1:
            break
        opening_gt = html.find(">", pos)
        if opening_gt == -1:
            search_from = pos + len(pat)
            continue

        depth = 1
        scan_from = opening_gt + 1
        content_end = scan_from
        found = False

        while depth > 0 and scan_from < len(html):
            next_open = html.find("<div", scan_from)
            next_close = html.find("</div>", scan_from)
            if next_close == -1:
                break
            if next_open != -1 and next_open < next_close:
                depth += 1
                scan_from = next_open + 4
            else:
                depth -= 1
                if depth == 0:
                    content_end = next_close
                    found = True
                    scan_from = next_close + 6
                else:
                    scan_from = next_close + 6

        if found and content_end > opening_gt:
            box_content = html[opening_gt + 1:content_end]
            boxes.append({"start": pos, "end": content_end, "raw": box_content})
            search_from = scan_from
        else:
            search_from = pos + len(pat)

    return boxes


def main() -> int:
    # Load snapshot
    snapshot_path = str(SNAPSHOT)
    if not SNAPSHOT.exists():
        print(f"ERROR: Snapshot not found: {snapshot_path}")
        return 1

    with open(snapshot_path) as f:
        data = json.load(f)
    html = data.get("parse", {}).get("text", {}).get("*", "")
    if not html:
        print("ERROR: Empty snapshot HTML")
        return 1

    print(f"Snapshot loaded: {len(html):,} chars")

    # Find stage boundaries
    gs_pos = html.find('id="Group_stage"')
    ks_pos = html.find('id="Knockout_stage"')
    print(f"Group stage at: {gs_pos:,}")
    print(f"Knockout stage at: {ks_pos:,}")

    # Build KO round position map
    ko_round_positions = {}
    for rid, label in [
        ("Round_of_32", "Round of 32"),
        ("Round_of_16", "Round of 16"),
        ("Quarterfinals", "Quarter-finals"),
        ("Semifinals", "Semi-finals"),
        ("Match_for_third_place", "Third place"),
        ("Final", "Final"),
    ]:
        p = html.find(f'id="{rid}"')
        if p >= 0:
            ko_round_positions[p] = label
    sorted_ko_positions = sorted(ko_round_positions.keys())

    # Extract all boxes
    all_boxes = find_all_football_boxes(html)
    print(f"Total boxes extracted: {len(all_boxes)}")

    # Group boxes into stages
    group_boxes = [b for b in all_boxes if b["start"] < ks_pos]
    ko_boxes = [b for b in all_boxes if b["start"] >= ks_pos]

    # Track group boxes per group
    # Load group section html to get group positions
    groups_order = list("ABCDEFGHIJKL")
    group_ranges = {}
    last_pos = gs_pos
    for g in groups_order:
        gid_pos = html.find(f'id="Group_{g}"')
        if gid_pos >= 0:
            group_ranges[g] = gid_pos
            last_pos = gid_pos

    # Assign group labels
    def nearest_group(box_pos: int) -> str | None:
        before = html[max(gs_pos, box_pos - 50000):box_pos]
        groups = re.findall(r'id="Group_([A-L])">Group [A-L]<', before)
        return groups[-1] if groups else None

    # Build cards
    cards: list[dict[str, Any]] = []
    teams_covered: set[str] = set()
    venue_missing_list: list[int] = []
    ko_round_counter: dict[str, int] = {}

    group_matchday_counter: dict[str, int] = {}

    for box in all_boxes:
        content = box["raw"]
        mid = extract_match_id(content) or 0
        is_ko = box["start"] >= ks_pos

        # Determine stage
        if is_ko:
            # Find nearest KO round heading
            nearest_round = "Knockout"
            for i, rp in enumerate(sorted_ko_positions):
                if rp <= box["start"]:
                    nearest_round = ko_round_positions[rp]

            group_letter = None
            matchday = None
            round_label = KO_ROUND_MAP.get(nearest_round, nearest_round)
            round_num = KO_ROUND_NUM_MAP.get(nearest_round, None)
        else:
            group_letter = nearest_group(box["start"])
            # Track matchday within group
            if group_letter:
                group_matchday_counter[group_letter] = group_matchday_counter.get(group_letter, 0) + 1
                idx_in_group = group_matchday_counter[group_letter] - 1  # 0-5
                # Matchday 1: first 2 matches, Matchday 2: next 2, Matchday 3: last 2
                matchday = (idx_in_group // 2) + 1 if idx_in_group < 6 else None
            else:
                matchday = None
            round_label = f"Group {group_letter}" if group_letter else "GROUP_STAGE"
            round_num = matchday

        # Extract teams
        home_raw = extract_team_from_box(content, "fhome")
        away_raw = extract_team_from_box(content, "faway")

        # Fallback: look for team links
        if not home_raw or not away_raw:
            all_team_links = re.findall(
                r'<a[^>]*title="([^"]*(?:national\s+(?:football|soccer)\s+team|men\'s\s+(?:football|soccer)\s+team))"',
                content,
            )
            if len(all_team_links) >= 2:
                home_raw = all_team_links[0]
                away_raw = all_team_links[1]

        home = canonical_team(home_raw.strip() if home_raw else f"TEAM_PLACEHOLDER_{mid}")
        away = canonical_team(away_raw.strip() if away_raw else f"TEAM_PLACEHOLDER_{mid}")

        # Extract venue
        venue = extract_venue_from_box(content)
        if venue:
            venue_clean = html_unescape(venue)
        else:
            venue_clean = "PARSE_REQUIRED"
            venue_missing_list.append(mid)

        # Extract date/time
        date_str = extract_date(content)
        time_str = extract_time(content)
        tz_str = extract_timezone(content)

        kickoff_utc = None
        if date_str and time_str and tz_str:
            kickoff_utc = parse_local_time_to_utc(date_str, time_str, tz_str)

        # Build card
        card = {
            "match_id": f"wc_{mid:03d}",
            "group": group_letter or ("KNOCKOUT" if is_ko else "UNKNOWN"),
            "round": round_num if not is_ko else round_num,
            "round_label": round_label,
            "home_team": home,
            "away_team": away,
            "home_team_slug": slugify(home),
            "away_team_slug": slugify(away),
            "api_football_fixture_id": None,
            "wiki_match_number": mid,
            "venue": venue_clean,
            "venue_source": "wikipedia_footballbox" if venue else "PARSE_REQUIRED",
            "kickoff_status": "SCHEDULED",
            "kickoff_time_utc": kickoff_utc,
            "kickoff_local": {
                "date": date_str,
                "time": time_str,
                "timezone": tz_str,
            },
            "data_gaps": [],
            **SAFETY,
        }

        # Data gaps
        if venue_clean == "PARSE_REQUIRED":
            card["data_gaps"].append("venue_parse_required_from_surrounding_html")
        if not kickoff_utc:
            card["data_gaps"].append("kickoff_utc_conversion_pending")

        cards.append(card)
        teams_covered.update([home, away])

    # --- Summary ---
    total = len(cards)
    group_count = sum(1 for c in cards if c["round_label"].startswith("Group "))
    ko_count = total - group_count

    stage_breakdown = {}
    for c in cards:
        label = c["round_label"]
        stage_breakdown[label] = stage_breakdown.get(label, 0) + 1

    match_ids = [c["wiki_match_number"] for c in cards if c.get("wiki_match_number")]
    expected_range = set(range(1, 105))
    actual_range = set(match_ids)
    gaps = sorted(expected_range - actual_range)

    summary = {
        "pack_name": "V3_WC_2026_MATCH_CARD_PACK_WIKIPEDIA_SOURCE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_head": git_head(),
        "data_source": "Wikipedia (2026 FIFA World Cup), post-draw snapshot (2026-06-05)",
        "source_file": str(SNAPSHOT.relative_to(ROOT.parent)),
        "match_count": total,
        "group_match_count": group_count,
        "knockout_match_count": ko_count,
        "expected_total": 104,
        "expected_group": 72,
        "expected_knockout": 32,
        "match_ids_range": f"{min(match_ids)}-{max(match_ids)}" if match_ids else "N/A",
        "match_id_gaps": gaps,
        "teams_covered": sorted(teams_covered),
        "stage_breakdown": stage_breakdown,
        "venue_missing_count": len(venue_missing_list),
        "venue_missing_match_ids": venue_missing_list,
        "safety": SAFETY,
    }

    # Write output
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MATCH_CARDS.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MATCH_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n=== BUILD COMPLETE ===")
    print(f"Total cards: {total}")
    print(f"Group: {group_count}")
    print(f"Knockout: {ko_count}")
    print(f"Match ID range: {min(match_ids)}-{max(match_ids)}")
    print(f"Match ID gaps: {gaps}")
    print(f"Venue missing (PARSE_REQUIRED): {len(venue_missing_list)} -> {venue_missing_list}")
    print(f"Teams covered: {len(teams_covered)}")
    print(f"Cards written: {MATCH_CARDS}")
    print(f"Summary written: {MATCH_SUMMARY}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
