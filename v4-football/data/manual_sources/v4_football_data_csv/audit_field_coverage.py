#!/usr/bin/env python3
"""
V4 Football-Data CSV — Manifest & Field Coverage Audit
=======================================================
Outputs:
  1. MANIFEST.md — per-file metadata
  2. FIELD_COVERAGE_MATRIX.md — league×season field coverage
  3. V4_REPLAY_READINESS.md — summary of which leagues/seasons can support price-aware replay
"""

import csv
import hashlib
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# League name mapping
LEAGUE_NAMES = {
    "E0": "English Premier League",
    "SP1": "Spanish La Liga",
    "D1": "German Bundesliga",
    "I1": "Italian Serie A",
    "F1": "French Ligue 1",
    "P1": "Portuguese Primeira Liga",
    "N1": "Dutch Eredivisie",
    "B1": "Belgian Pro League",
    "T1": "Turkish Süper Lig",
}

# Season mapping: season_code -> (label, status)
SEASON_MAP = {
    "2526": ("2025/26", "CURRENT_PARTIAL"),
    "2425": ("2024/25", "COMPLETE"),
    "2324": ("2023/24", "COMPLETE"),
    "2223": ("2022/23", "COMPLETE"),
    "2122": ("2021/22", "COMPLETE"),
    "2021": ("2020/21", "COMPLETE"),
}

# Required fields for V4 price-aware replay
REQUIRED_FIELDS = {
    "1X2": ["B365H", "B365D", "B365A"],
    "FT_O_U_2.5": ["B365>2.5", "B365<2.5"],
    "AH": ["B365AHH", "B365AHA", "B365AH"],
    "opening_odds_1X2": ["PSH", "PSD", "PSA"],
    "closing_odds_1X2": ["PSCH", "PSCD", "PSCA"],
    "avg_odds": ["AvgH", "AvgD", "AvgA"],
    "max_odds": ["MaxH", "MaxD", "MaxA"],
    "basic_stats": ["HS", "AS", "HST", "AST", "HC", "AC", "HY", "AY", "HR", "AR"],
}

# Additional audit fields
AUDIT_FIELDS = [
    "Date", "HomeTeam", "AwayTeam",
    "FTHG", "FTAG", "FTR",
    "HTHG", "HTAG", "HTR",
    "HS", "AS", "HST", "AST", "HC", "AC",
    "HY", "AY", "HR", "AR",
    "B365H", "B365D", "B365A",
    "B365>2.5", "B365<2.5",
    "B365AHH", "B365AHA", "B365AH",
    "PSH", "PSD", "PSA",
    "PSCH", "PSCD", "PSCA",
    "MaxH", "MaxD", "MaxA",
    "AvgH", "AvgD", "AvgA",
    "BbMxH", "BbAvH", "BbMxD", "BbAvD", "BbMxA", "BbAvA",
    "BbMx>2.5", "BbAv>2.5", "BbMx<2.5", "BbAv<2.5",
    "BbAHh", "BbMxAHH", "BbAvAHH", "BbMxAHA", "BbAvAHA",
    "AHh", "MaxAHH", "MaxAHA", "AvgAHH", "AvgAHA",
]


def checksum(filepath):
    """SHA-256 hex digest."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_csv_header(filepath):
    """Return header list and row count. None on error."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            header = [h.strip() for h in header]
            row_count = sum(1 for _ in reader)
            return header, row_count
    except Exception as e:
        return None, str(e)


def field_coverage(header, field_list):
    """Return dict of field -> present (True/False)."""
    header_set = set(header)
    return {f: f in header_set for f in field_list}


def main():
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Collect all files
    all_files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".csv"))

    manifest_rows = []
    coverage_data = {}  # {league: {season: {field_group: {field: bool}}}}

    for fname in all_files:
        filepath = os.path.join(RAW_DIR, fname)
        parts = fname.replace(".csv", "").split("_")
        if len(parts) < 2:
            continue
        # The format is LEAGUE_SEASONCODE.csv (e.g. E0_2122.csv)
        # But we might have different naming conventions
        # Let's try to parse: first part is league code, second part is season code
        league_code = parts[0]
        season_code = parts[1]

        if league_code not in LEAGUE_NAMES or season_code not in SEASON_MAP:
            # Try alternate: for files like B1_2021.csv the second part could be "2021"
            # Already handled if season_code in SEASON_MAP
            continue

        header, row_count = parse_csv_header(filepath)

        if header is None:
            status = "PARSE_ERROR"
            row_count = 0
            col_count = 0
            header_snapshot = []
        else:
            status = "OK"
            col_count = len(header)
            header_snapshot = header

        cksum = checksum(filepath) if status == "OK" else "N/A"
        file_size = os.path.getsize(filepath)

        season_label, season_status = SEASON_MAP[season_code]
        league_name = LEAGUE_NAMES[league_code]
        source_url = f"https://www.football-data.co.uk/mmz4281/{season_code}/{league_code}.csv"

        manifest_rows.append({
            "league_code": league_code,
            "league_name": league_name,
            "season_code": season_code,
            "season_label": season_label,
            "season_status": season_status,
            "source_url": source_url,
            "local_path": f"raw/{fname}",
            "file_exists": "YES" if status == "OK" else "ERROR",
            "row_count": row_count,
            "column_count": col_count,
            "file_size_bytes": file_size,
            "checksum_sha256": cksum,
            "status": status,
        })

        if status == "OK":
            cov = {}
            for group, fields in REQUIRED_FIELDS.items():
                fcov = field_coverage(header, fields)
                cov[group] = fcov
                cov[group + "_all_present"] = all(fcov.values())
            # Also audit basic fields
            cov["audit"] = field_coverage(header, AUDIT_FIELDS)
            if league_code not in coverage_data:
                coverage_data[league_code] = {}
            coverage_data[league_code][season_code] = cov
            coverage_data[league_code]["name"] = league_name

    # ========== WRITE MANIFEST ==========
    manifest_path = os.path.join(OUTPUT_DIR, "MANIFEST.md")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("# V4 Football-Data CSV Manifest\n\n")
        f.write(f"Generated: {now_utc}\n")
        f.write(f"Source: https://www.football-data.co.uk\n")
        f.write(f"Total files: {len(manifest_rows)}\n\n")
        f.write("| # | League | Season | Status | Rows | Cols | Size | Checksum (SHA-256) |\n")
        f.write("|---|--------|--------|--------|------|------|------|--------------------|\n")
        for i, row in enumerate(manifest_rows, 1):
            cksum_short = row["checksum_sha256"][:16] if row["checksum_sha256"] != "N/A" else "N/A"
            f.write(
                f"| {i} | {row['league_code']} {row['league_name']} "
                f"| {row['season_label']} ({row['season_status']}) "
                f"| {row['status']} "
                f"| {row['row_count']} "
                f"| {row['column_count']} "
                f"| {row['file_size_bytes']} "
                f"| {cksum_short} |\n"
            )
        f.write("\n---\n\n### Detailed File List\n\n")
        f.write("| File | Source URL | Status |\n")
        f.write("|------|------------|--------|\n")
        for row in manifest_rows:
            f.write(f"| {row['local_path']} | {row['source_url']} | {row['status']} |\n")

    print(f"[OK] Manifest written: {manifest_path}")

    # ========== WRITE FIELD COVERAGE MATRIX ==========
    matrix_path = os.path.join(OUTPUT_DIR, "FIELD_COVERAGE_MATRIX.md")
    with open(matrix_path, "w", encoding="utf-8") as f:
        f.write("# V4 Football-Data CSV — Field Coverage Matrix\n\n")
        f.write(f"Generated: {now_utc}\n\n")
        f.write("## Legend\n\n")
        f.write("- ✅ = field group fully present\n")
        f.write("- ⚠️ = field group partially present\n")
        f.write("- ❌ = field group absent\n")
        f.write("- `-` = season not available\n\n")

        f.write("## Group Coverage by League × Season\n\n")

        seasons_ordered = ["2021", "2122", "2223", "2324", "2425", "2526"]
        season_labels = {k: f"{v[0]}" for k, v in SEASON_MAP.items()}
        group_order = ["1X2", "FT_O_U_2.5", "AH", "opening_odds_1X2",
                       "closing_odds_1X2", "avg_odds", "max_odds", "basic_stats"]

        group_display = {
            "1X2": "1X2 (B365)",
            "FT_O_U_2.5": "FT O/U 2.5 (B365)",
            "AH": "Asian Handicap (B365)",
            "opening_odds_1X2": "Opening 1X2 (Pinnacle)",
            "closing_odds_1X2": "Closing 1X2 (Pinnacle C)",
            "avg_odds": "Avg 1X2 Odds",
            "max_odds": "Max 1X2 Odds",
            "basic_stats": "Basic Match Stats",
        }

        for league_code in sorted(coverage_data.keys(), key=lambda x: list(LEAGUE_NAMES.keys()).index(x)):
            league_name = coverage_data[league_code]["name"]
            f.write(f"### {league_code} — {league_name}\n\n")
            f.write(f"| Season | " + " | ".join(group_display.values()) + " |\n")
            f.write("|--------|" + "|".join([":---:"] * len(group_order)) + "|\n")

            for sc in seasons_ordered:
                if sc not in coverage_data[league_code]:
                    f.write(f"| {season_labels[sc]} | " + " | ".join(["-"] * len(group_order)) + " |\n")
                    continue
                cov = coverage_data[league_code][sc]
                cells = []
                for g in group_order:
                    key = g + "_all_present"
                    if key in cov:
                        cells.append("✅" if cov[key] else "⚠️")
                    else:
                        cells.append("❌")
                f.write(f"| {season_labels[sc]} | " + " | ".join(cells) + " |\n")
            f.write("\n")

        # Individual field matrix
        f.write("---\n\n## Individual Field Presence (All Leagues × Seasons)\n\n")
        f.write("Fields audited: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, HTHG, HTAG, HTR, ")
        f.write("HS, AS, HST, AST, HC, AC, HY, AY, HR, AR, ")
        f.write("B365H/D/A, B365>2.5/<2.5, B365AHH/AHA/AH, ")
        f.write("PSH/PSD/PSA (opening), PSCH/PSCD/PSCA (closing), ")
        f.write("MaxH/D/A, AvgH/D/A\n\n")

        # Individual fields to show
        show_fields = [
            "Date", "HomeTeam", "AwayTeam",
            "FTHG", "FTAG", "FTR",
            "HTHG", "HTAG", "HTR",
            "HS", "AS", "HST", "AST", "HC", "AC", "HY", "AY", "HR", "AR",
            "B365H", "B365D", "B365A",
            "B365>2.5", "B365<2.5",
            "B365AHH", "B365AHA", "B365AH",
            "PSH", "PSD", "PSA",
            "PSCH", "PSCD", "PSCA",
            "MaxH", "MaxD", "MaxA",
            "AvgH", "AvgD", "AvgA",
            "AHh", "MaxAHH", "MaxAHA", "AvgAHH", "AvgAHA",
        ]

        csv_rows_list = []
        header_row = ["League", "Season"] + show_fields
        csv_rows_list.append(header_row)

        for league_code in sorted(coverage_data.keys(), key=lambda x: list(LEAGUE_NAMES.keys()).index(x)):
            league_name = coverage_data[league_code]["name"]
            for sc in seasons_ordered:
                if sc not in coverage_data[league_code]:
                    row = [league_code, season_labels[sc]] + ["-"] * len(show_fields)
                else:
                    cov = coverage_data[league_code][sc]
                    audit = cov.get("audit", {})
                    row = [league_code, season_labels[sc]]
                    for field in show_fields:
                        if field in audit:
                            row.append("✅" if audit[field] else " ")
                        else:
                            row.append(" ")
                csv_rows_list.append(row)

        # Write as markdown table (fixed width)
        col_widths = [max(len(str(r[i])) for r in csv_rows_list) for i in range(len(header_row))]
        f.write("| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(header_row)) + " |\n")
        f.write("|" + "|".join(["-" * (w + 2) for w in col_widths]) + "|\n")
        for row in csv_rows_list[1:]:
            f.write("| " + " | ".join(str(v).ljust(col_widths[i]) for i, v in enumerate(row)) + " |\n")

        f.write("\n\n*Note: ` ` (blank) = field not present in CSV; `-` = season/league not available*\n")

    print(f"[OK] Field coverage matrix written: {matrix_path}")

    # ========== WRITE V4 REPLAY READINESS REPORT ==========
    replay_path = os.path.join(OUTPUT_DIR, "V4_REPLAY_READINESS.md")
    with open(replay_path, "w", encoding="utf-8") as f:
        f.write("# V4 Price-Aware Replay Readiness Report\n\n")
        f.write(f"Generated: {now_utc}\n\n")
        f.write("## Purpose\n\n")
        f.write("Assess whether football-data.co.uk CSV files can support V4 price-aware replay ")
        f.write("— i.e., backtesting betting strategies that incorporate opening odds, closing odds, ")
        f.write("Asian handicap, and over/under markets alongside match results and basic statistics.\n\n")

        f.write("## Criteria for V4 Replay Readiness\n\n")
        f.write("A league-season is **READY** if it has:\n")
        f.write("1. ✅ Match results: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR\n")
        f.write("2. ✅ 1X2 odds (at least Bet365): B365H, B365D, B365A\n")
        f.write("3. ✅ Opening odds (Pinnacle): PSH, PSD, PSA\n")
        f.write("4. ✅ Closing odds (Pinnacle C): PSCH, PSCD, PSCA\n")
        f.write("5. ✅ Over/Under 2.5 (Bet365): B365>2.5, B365<2.5\n")
        f.write("6. ✅ OR Asian Handicap (Bet365): B365AHH, B365AHA, B365AH\n")
        f.write("7. ✅ Basic match stats: HS, AS, HST, AST, HC, AC\n\n")
        f.write("A league-season is **PARTIAL** if results + some odds are present but some key markets are missing.\n")
        f.write("A league-season is **NOT_READY** if odds are absent or severely limited.\n\n")

        f.write("## Summary\n\n")
        f.write("| League | 2020/21 | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |\n")
        f.write("|--------|---------|---------|---------|---------|---------|---------|\n")

        # Overall readiness for each league-season
        summary_rows = []
        for league_code in sorted(coverage_data.keys(), key=lambda x: list(LEAGUE_NAMES.keys()).index(x)):
            league_name = coverage_data[league_code]["name"]
            cells = [f"{league_code} {league_name}"]
            for sc in seasons_ordered:
                if sc not in coverage_data[league_code]:
                    cells.append("—")
                    continue
                cov = coverage_data[league_code][sc]
                has_results = cov["audit"].get("Date", False) and cov["audit"].get("FTHG", False) and cov["audit"].get("FTR", False)
                has_1x2 = cov["1X2_all_present"]
                has_ou = cov["FT_O_U_2.5_all_present"]
                has_ah = cov["AH_all_present"]
                has_opening = cov["opening_odds_1X2_all_present"]
                has_closing = cov["closing_odds_1X2_all_present"]
                has_stats = cov["basic_stats_all_present"]

                # Decision
                if has_results and has_1x2 and has_ou and (has_ah or True) and has_opening and has_closing and has_stats:
                    cells.append("✅ READY")
                elif has_results and has_1x2:
                    cells.append("⚠️ PARTIAL")
                else:
                    cells.append("❌ NOT_READY")
            f.write("| " + " | ".join(cells) + " |\n")

            # Store summary for detailed section
            summary_rows.append((league_code, league_name, seasons_ordered))

        f.write("\n---\n\n## Detailed League-by-League Breakdown\n\n")

        for league_code in sorted(coverage_data.keys(), key=lambda x: list(LEAGUE_NAMES.keys()).index(x)):
            league_name = coverage_data[league_code]["name"]
            f.write(f"### {league_code} — {league_name}\n\n")

            for sc in seasons_ordered:
                if sc not in coverage_data[league_code]:
                    f.write(f"**{SEASON_MAP[sc][0]}**: Not available\n\n")
                    continue

                cov = coverage_data[league_code][sc]
                season_label = SEASON_MAP[sc][0]
                season_status = SEASON_MAP[sc][1]

                # Check each criterion
                has_results = cov["audit"].get("Date", False) and cov["audit"].get("FTHG", False) and cov["audit"].get("FTR", False)
                has_1x2 = cov["1X2_all_present"]
                has_ou = cov["FT_O_U_2.5_all_present"]
                has_ah = cov["AH_all_present"]
                has_opening = cov["opening_odds_1X2_all_present"]
                has_closing = cov["closing_odds_1X2_all_present"]
                has_stats = cov["basic_stats_all_present"]

                verdict = "READY" if (has_results and has_1x2 and has_ou and has_opening and has_closing and has_stats) else \
                          "PARTIAL" if (has_results and has_1x2) else "NOT_READY"

                f.write(f"**{season_label}** ({season_status}) — **{verdict}**\n\n")
                f.write(f"- Results: {'✅' if has_results else '❌'}\n")
                f.write(f"- 1X2 (B365): {'✅' if has_1x2 else '❌'}\n")
                f.write(f"- O/U 2.5 (B365): {'✅' if has_ou else '❌'}\n")
                f.write(f"- Asian Handicap (B365): {'✅' if has_ah else '❌'}\n")
                f.write(f"- Opening 1X2 (Pinnacle): {'✅' if has_opening else '❌'}\n")
                f.write(f"- Closing 1X2 (Pinnacle C): {'✅' if has_closing else '❌'}\n")
                f.write(f"- Basic Stats: {'✅' if has_stats else '❌'}\n\n")

        # Gap analysis
        f.write("---\n\n## Gap Analysis\n\n")
        missing_groups = set()
        for league_code in coverage_data:
            for sc in seasons_ordered:
                if sc in coverage_data[league_code]:
                    cov = coverage_data[league_code][sc]
                    for g in group_order:
                        key = g + "_all_present"
                        if key in cov and not cov[key]:
                            missing_groups.add(g)

        if missing_groups:
            f.write("### Fields with coverage gaps\n\n")
            for g in sorted(missing_groups):
                f.write(f"- **{group_display.get(g, g)}**: Missing in at least one league-season\n")
        else:
            f.write("### All required field groups present across all audited league-seasons\n")

        f.write("\n---\n\n## Conclusion\n\n")
        ready_count = 0
        partial_count = 0
        not_ready_count = 0
        for league_code in coverage_data:
            for sc in seasons_ordered:
                if sc in coverage_data[league_code]:
                    cov = coverage_data[league_code][sc]
                    has_results = cov["audit"].get("Date", False) and cov["audit"].get("FTHG", False) and cov["audit"].get("FTR", False)
                    has_1x2 = cov["1X2_all_present"]
                    has_ou = cov["FT_O_U_2.5_all_present"]
                    has_opening = cov["opening_odds_1X2_all_present"]
                    has_closing = cov["closing_odds_1X2_all_present"]
                    has_stats = cov["basic_stats_all_present"]

                    if has_results and has_1x2 and has_ou and has_opening and has_closing and has_stats:
                        ready_count += 1
                    elif has_results and has_1x2:
                        partial_count += 1
                    else:
                        not_ready_count += 1

        f.write(f"- **Ready for V4 price-aware replay**: {ready_count} league-season(s)\n")
        f.write(f"- **Partial (results + some odds)**: {partial_count} league-season(s)\n")
        f.write(f"- **Not ready**: {not_ready_count} league-season(s)\n")
        f.write(f"- **Total audited**: {ready_count + partial_count + not_ready_count}\n\n")

        f.write("**Recommendation**:\n\n")
        if ready_count >= 30:
            f.write("✅ Football-data.co.uk CSV data is **sufficient** for V4 price-aware replay development ")
            f.write("for the core 5 leagues (E0/SP1/D1/I1/F1) across all 5 complete seasons.\n")
        elif ready_count >= 10:
            f.write("⚠️ Football-data.co.uk CSV data is **partially sufficient** for V4 price-aware replay. ")
            f.write("Some league-seasons have gaps that may need supplementary data.\n")
        else:
            f.write("❌ Football-data.co.uk CSV data is **insufficient** for V4 price-aware replay. ")
            f.write("Alternative data sources should be evaluated.\n")

    print(f"[OK] Readiness report written: {replay_path}")

    # ========== OUTPUT JSON SUMMARY ==========
    summary = {
        "generated_at": now_utc,
        "source": "https://www.football-data.co.uk",
        "total_files": len(manifest_rows),
        "total_ok": sum(1 for r in manifest_rows if r["status"] == "OK"),
        "total_error": sum(1 for r in manifest_rows if r["status"] != "OK"),
        "leagues": sorted(list(LEAGUE_NAMES.keys())),
        "seasons": sorted(list(SEASON_MAP.keys())),
        "ready_count": ready_count,
        "partial_count": partial_count,
        "not_ready_count": not_ready_count,
    }
    summary_path = os.path.join(OUTPUT_DIR, "audit_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"[OK] JSON summary written: {summary_path}")
    print(f"\n=== AUDIT SUMMARY ===")
    print(f"Total files: {len(manifest_rows)}")
    print(f"OK: {summary['total_ok']}")
    print(f"Error: {summary['total_error']}")
    print(f"READY for replay: {ready_count}")
    print(f"PARTIAL: {partial_count}")
    print(f"NOT_READY: {not_ready_count}")


if __name__ == "__main__":
    main()
