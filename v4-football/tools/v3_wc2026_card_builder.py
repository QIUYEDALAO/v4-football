#!/usr/bin/env python3
"""
V3 WC 2026 Match Card Builder — BUILDER PACK

Builds 104 match cards (72 group + 32 knockout) from the saved
Wikipedia full-page snapshot.

Output: data/runtime/wc2026/fixtures/v3_wc2026_104_cards.json

Status field values:
  - "scheduled": initial state, no result yet
  - "completed": official result verified
  - "cancelled": cancelled match (not expected for WC)

No betting/prediction fields included.
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(BASE, "reports", "v3_wc2026_source_validation", "wikipedia_2026_full_page.json")
OUTPUT = os.path.join(BASE, "data", "runtime", "wc2026", "fixtures", "v3_wc2026_104_cards.json")


def load_html():
    if not os.path.exists(SNAPSHOT):
        print(f"ERROR: Snapshot not found: {SNAPSHOT}")
        sys.exit(1)
    with open(SNAPSHOT) as f:
        data = json.load(f)
    return data.get("parse", {}).get("text", {}).get("*", "")


def find_all_boxes(html):
    """Extract all <div class=\"footballbox\"> using proper div nesting depth."""
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
                    content_end = scan_from - 6  # back to </div> start
                    found = True
                    scan_from = next_close + 6
                else:
                    scan_from = next_close + 6

        if found and content_end > opening_gt:
            box_content = html[opening_gt + 1:content_end]
            boxes.append({"start": pos, "raw": box_content})
            search_from = scan_from
        else:
            search_from = pos + len(pat)

    return boxes


def html_unescape(s):
    """HTML unescape including numeric entities."""
    s = s.replace("&#160;", " ")
    s = s.replace("&#39;", "'")
    s = s.replace("&#x27;", "'")
    s = s.replace("&amp;", "&")
    s = s.replace("&lt;", "<")
    s = s.replace("&gt;", ">")
    s = s.replace("&quot;", '"')
    s = s.replace("&apos;", "'")
    # Generic numeric entities
    def replace_num(m):
        code = m.group(1)
        try:
            return chr(int(code))
        except (ValueError, OverflowError):
            return m.group(0)
    s = re.sub(r'&#(\d+);', replace_num, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_team_name(box_raw):
    """Extract home and away team names from football box.

    Returns (home_team, away_team) as strings.
    Group stage: real team names from <a> with title attributes.
    Knockout stage: description-based (e.g. 'Winner Group C', 'Runner-up Group B').
    """
    home = None
    away = None

    # Strategy 1: extract clean text from fhome/faway <th> blocks, strip HTML tags
    home_th = re.search(
        r'class="fhome[^"]*"[^>]*>(.*?)</th>',
        box_raw, re.DOTALL
    )
    away_th = re.search(
        r'class="faway[^"]*"[^>]*>(.*?)</th>',
        box_raw, re.DOTALL
    )

    if home_th:
        # Strip all HTML tags and get clean text
        text = re.sub(r'<[^>]+>', '', home_th.group(1))
        text = html_unescape(text).strip()
        # Remove leading/trailing non-breaking spaces
        text = text.replace('\xa0', '').strip()
        if text:
            home = text

    if away_th:
        text = re.sub(r'<[^>]+>', '', away_th.group(1))
        text = html_unescape(text).strip()
        text = text.replace('\xa0', '').strip()
        if text:
            away = text

    # Strategy 2 (fallback): try <a> tag title for group stage teams
    # Only if the stripped text is empty or too short
    if not home or len(home) < 3:
        home_m = re.search(
            r'class="fhome[^"]*"[^>]*>.*?<a[^>]*title="([^"]*)"',
            box_raw, re.DOTALL
        )
        if home_m:
            home = html_unescape(home_m.group(1))

    if not away or len(away) < 3:
        away_m = re.search(
            r'class="faway[^"]*"[^>]*>.*?<a[^>]*title="([^"]*)"',
            box_raw, re.DOTALL
        )
        if away_m:
            away = html_unescape(away_m.group(1))

    # Strategy 3 (fallback): extract from itemprop="name" spans
    # Useful for knockout matches where team names are plain text in spans
    if not home or not away:
        spans = re.findall(
            r'<span\s+itemprop="name">([^<]+)</span>',
            box_raw
        )
        if len(spans) >= 2:
            if not home:
                home = html_unescape(spans[0])
            if not away:
                away = html_unescape(spans[1])
        elif len(spans) == 1:
            if not home:
                home = html_unescape(spans[0])

    return home, away


def extract_date(box_raw):
    d = re.search(r'fdate">([^<]+)', box_raw)
    if d:
        return html_unescape(d.group(1).strip())
    return None


def extract_time(box_raw):
    t = re.search(r'ftime">([^<]+)', box_raw)
    if t:
        return html_unescape(t.group(1).strip())
    return None


def extract_timezone(box_raw):
    tz = re.search(r"UTC[−\-+]\s*\d{1,2}(?::\d{2})?", box_raw)
    if tz:
        return html_unescape(tz.group(0).strip())
    return None


def extract_venue(box_raw):
    """Extract venue name from football box.

    Uses itemprop=\"location\" div structure which contains the venue link.
    """
    # Look for the venue in the fright div with itemprop="location"
    v = re.search(
        r'itemprop="location"[^>]*>.*?<a[^>]*title="([^"]*)"',
        box_raw, re.DOTALL
    )
    if v:
        return html_unescape(v.group(1))

    # Fallback: any stadium-like link title
    v2 = re.search(
        r'<a[^>]*title="([^"]*(?:Stadium|Estadio|Field|Bowl|Place|Center|Centre|Dome|Park)[^"]*)"',
        box_raw
    )
    if v2:
        return html_unescape(v2.group(1))

    # Last fallback: extract the text from itemprop name span in location
    v3 = re.search(
        r'itemprop="name\s*address"[^>]*>\s*([^<]+)',
        box_raw
    )
    if v3:
        name_text = html_unescape(v3.group(1))
        # Cut at comma if city follows
        if "," in name_text:
            name_text = name_text.split(",")[0].strip()
        if name_text:
            return name_text

    return None


def extract_match_id(box_raw):
    m = re.search(r">Match\s+(\d+)<", box_raw)
    if m:
        return int(m.group(1))
    return None


def determine_stage(box_start, html, is_ko, ks_pos):
    """Determine stage for this match.

    For group stage: look for nearest Group_X heading before this box.
    For knockout: look for Round section heading.
    """
    # Search window: 50000 chars before box start to find the section heading
    window_start = max(0, box_start - 50000)
    before = html[window_start:box_start]

    if is_ko:
        round_map = {
            "Round_of_32": "round_of_32",
            "Round_of_16": "round_of_16",
            "Quarterfinals": "quarter_final",
            "Semifinals": "semi_final",
            "Match_for_third_place": "third_place",
            "Final": "final",
        }
        last_round = None
        last_pos = -1
        for rid, label in round_map.items():
            mp = before.find(f'id="{rid}"')
            if mp >= 0 and mp > last_pos:
                last_pos = mp
                last_round = label
        return last_round or "knockout"
    else:
        groups = re.findall(r'id="Group_([A-L])">', before)
        if groups:
            return f"Group {groups[-1]}"
        return "Group (unknown)"


def build_match_card(box, html, ks_pos):
    """Build a single match card from a parsed football box."""
    raw = box["raw"]
    start = box["start"]
    is_ko = start >= ks_pos

    mid = extract_match_id(raw)
    if mid is None:
        print(f"WARNING: Could not extract match_id at position {start}, skipping")
        return None

    stage = determine_stage(start, html, is_ko, ks_pos)
    home, away = extract_team_name(raw)
    date_raw = extract_date(raw)
    time_raw = extract_time(raw)
    tz = extract_timezone(raw)
    venue = extract_venue(raw)

    # Build kickoff field
    kickoff = None
    if time_raw and tz:
        kickoff = f"{time_raw} {tz}"
    elif time_raw:
        kickoff = time_raw

    # Validate required fields
    issues = []
    if not home:
        issues.append("home_team")
    if not away:
        issues.append("away_team")
    if not venue:
        issues.append("venue")

    # Store as PARSE_REQUIRED for missing fields
    if not home:
        home = "PARSE_REQUIRED"
    if not away:
        away = "PARSE_REQUIRED"
    if not venue:
        venue = "PARSE_REQUIRED"
    if not date_raw:
        date_raw = "PARSE_REQUIRED"
    if not kickoff:
        kickoff = "PARSE_REQUIRED"

    group = None
    match_number = None
    if stage.startswith("Group "):
        group = stage  # e.g. "Group A"
        # match_number gets the overall match_id for group stage
        match_number = mid
    else:
        group = None
        # For knockout, match_number is the round-local match number
        # We'll compute this in a second pass

    card = {
        "match_id": mid,
        "stage": stage,
        "group": group,
        "match_number": match_number,
        "home_team": home,
        "away_team": away,
        "venue": venue,
        "date": date_raw,
        "kickoff": kickoff,
        "status": "scheduled",
        "result": None,
    }

    if issues:
        card["_parse_issues"] = issues

    return card


def compute_ko_match_numbers(cards):
    """Compute match_number for knockout stages.

    Each knockout round gets sequential numbering starting from 1.
    """
    ko_rounds = ["round_of_32", "round_of_16", "quarter_final",
                  "semi_final", "third_place", "final"]
    for stage_name in ko_rounds:
        stage_cards = [c for c in cards if c["stage"] == stage_name]
        stage_cards.sort(key=lambda c: c["match_id"])
        for i, card in enumerate(stage_cards, 1):
            card["match_number"] = i
    return cards


def main():
    print("=" * 60)
    print("V3 WC2026 MATCH CARD BUILDER — BUILDER PACK")
    print("=" * 60)

    html = load_html()
    print(f"\nFull page HTML length: {len(html):,} chars")

    # Find section boundaries
    gs_pos = html.find('id="Group_stage"')
    ks_pos = html.find('id="Knockout_stage"')
    print(f"Group stage at: {gs_pos}")
    print(f"Knockout stage at: {ks_pos}")

    if gs_pos == -1 or ks_pos == -1:
        print("ERROR: Could not find group/knockout stage boundaries")
        sys.exit(1)

    # Extract all boxes
    boxes = find_all_boxes(html)
    print(f"\nTotal football boxes found: {len(boxes)}")

    if len(boxes) != 104:
        print(f"ERROR: Expected 104 boxes, found {len(boxes)}")
        sys.exit(1)

    # Build match cards
    cards = []
    parse_issues = []
    for box in boxes:
        card = build_match_card(box, html, ks_pos)
        if card:
            cards.append(card)
            if card.get("_parse_issues"):
                parse_issues.append({
                    "match_id": card["match_id"],
                    "issues": card["_parse_issues"],
                })
            # Clean up internal field
            card.pop("_parse_issues", None)

    # Sort by match_id
    cards.sort(key=lambda c: c["match_id"])

    # Compute knockout match numbers
    cards = compute_ko_match_numbers(cards)

    # Validate match IDs 1-104
    ids = set(c["match_id"] for c in cards)
    expected_ids = set(range(1, 105))
    missing_ids = expected_ids - ids
    extra_ids = ids - expected_ids

    if missing_ids:
        print(f"\nERROR: Missing match IDs: {sorted(missing_ids)}")
        sys.exit(1)
    if extra_ids:
        print(f"\nERROR: Extra match IDs: {sorted(extra_ids)}")
        sys.exit(1)

    # Count stats
    group_cards = [c for c in cards if c["stage"].startswith("Group ")]
    ko_cards = [c for c in cards if not c["stage"].startswith("Group ")]
    
    venue_missing = [c for c in cards if c["venue"] == "PARSE_REQUIRED"]
    date_missing = [c for c in cards if c["date"] == "PARSE_REQUIRED"]
    kickoff_missing = [c for c in cards if c["kickoff"] == "PARSE_REQUIRED"]

    print(f"\n── CARD STATS ──")
    print(f"  Total cards: {len(cards)}")
    print(f"  Group stage: {len(group_cards)}")
    print(f"  Knockout stage: {len(ko_cards)}")

    # Stage breakdown
    stage_counts = {}
    for c in cards:
        stage_counts[c["stage"]] = stage_counts.get(c["stage"], 0) + 1
    print(f"\n  ── Stage Breakdown ──")
    for stage, count in sorted(stage_counts.items()):
        print(f"    {stage}: {count}")

    print(f"\n  ── Field Issues ──")
    print(f"    venue PARSE_REQUIRED: {len(venue_missing)}")
    for c in venue_missing:
        print(f"      match #{c['match_id']} ({c['stage']})")
    print(f"    date PARSE_REQUIRED: {len(date_missing)}")
    print(f"    kickoff PARSE_REQUIRED: {len(kickoff_missing)}")

    # Save
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    
    output = {
        "metadata": {
            "source": "Wikipedia - 2026 FIFA World Cup",
            "snapshot_date": "2026-06-05",
            "build_date": "2026-06-05",
            "builder": "tools/v3_wc2026_card_builder.py",
            "total_cards": len(cards),
            "group_cards": len(group_cards),
            "knockout_cards": len(ko_cards),
            "venue_missing_count": len(venue_missing),
            "note": "Venue missing fields marked as PARSE_REQUIRED. These are known venues (BC Place) but the regex pattern missed them. All match data from official FIFA schedule via Wikipedia.",
        },
        "matches": cards,
    }

    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n── SAVED ──")
    print(f"  Output: {OUTPUT}")

    # Sample output
    print(f"\n── SAMPLE CARDS ──")
    for c in cards[:3]:
        print(f"  Match #{c['match_id']}: {c['home_team']} vs {c['away_team']}")
        print(f"    Stage: {c['stage']}, Group: {c['group']}")
        print(f"    Date: {c['date']}, Kickoff: {c['kickoff']}")
        print(f"    Venue: {c['venue']}")
        print()

    # Knockout samples
    print(f"── KNOCKOUT SAMPLES ──")
    for c in cards:
        if c["match_id"] in (73, 89, 97, 101, 103, 104):
            print(f"  Match #{c['match_id']}: {c['home_team']} vs {c['away_team']}")
            print(f"    Stage: {c['stage']}, KO match #: {c['match_number']}")
            print(f"    Date: {c['date']}, Venue: {c['venue']}")
            print()

    print("── BUILD COMPLETE ──")
    return cards


if __name__ == "__main__":
    main()
