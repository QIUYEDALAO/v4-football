#!/usr/bin/env python3
"""tools/check_v4_dynamic_league_classifier.py

Check V4 all_eligible dynamic league classifier (_is_non_senior_league) for
false positives and false negatives.

Guard markers:
  NO_AI_KILL_RETRY = true
  FAIL_CLOSED = true
  READ_ONLY = true
  SECURE = true

Usage:
  python3 tools/check_v4_dynamic_league_classifier.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# ── Import the actual function from h2h_engine ──
from engine.data_sources.h2h_engine import _is_non_senior_league

RESULTS = {
    "checker": "tools/check_v4_dynamic_league_classifier.py",
    "generated_at": None,
    "conclusion": "PASS",
    "blockers": [],
    "warnings": [],
    "checks": {},
}


def _check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS["checks"][name] = {"ok": ok, "detail": detail}
    if not ok:
        RESULTS["blockers"].append(f"{name}: {detail}")


def test_senior_eligible() -> None:
    """Senior leagues that MUST return (False, 'senior_league')."""
    cases = [
        ("Meistriliiga", "Estonia top division"),
        ("Esiliiga", "Estonia second division"),
        ("Esiliiga B", "Estonia second division B"),
        ("Liiga", "Generic senior league name"),
        ("Ykkösliiga", "Finland second division"),
        ("Veikkausliiga", "Finland top division"),
        ("III Liga - Group 3", "Poland fifth division"),
        ("III Liga - Group 4", "Poland fifth division"),
        ("Premier League", "Generic top division"),
        ("League One", "English/Chinese third division"),
        ("Serie D", "Italian fourth division"),
        ("Serie B", "Italian second division"),
        ("Regionalliga - Ost", "Austrian regional league"),
        ("Division 2 - Norra Götaland", "Swedish fourth division"),
        ("Primera División", "Top division in Spanish-speaking countries"),
        ("1. Liga Classic - Group 3", "Swiss fourth division"),
        ("Super League", "Top division"),
        ("Prva Liga", "Serbian second division"),
        ("Kakkonen - Lohko B", "Finnish third division"),
        ("Ykkönen", "Finnish second division"),
        ("First NL", "Croatian second division"),
        ("Second NL", "Croatian third division"),
        ("Virsliga", "Latvian top division"),
        ("2. Division", "Danish third division / generic"),
        ("Erovnuli Liga", "Georgian top division"),
        ("Brasileiro Série A", "Brazilian top division"),
        ("National League", "English fifth division"),
        ("Ligue 1", "French top division"),
        ("Ligue 2", "French second division"),
        ("Primera B", "Chilean second division"),
        ("Serie A", "Italian top division"),
        ("Ekstraklasa", "Polish top division"),
        ("Allsvenskan", "Swedish top division"),
        ("Eliteserien", "Norwegian top division"),
        ("Superliga", "Danish top division"),
        ("Bundesliga", "German top division"),
        ("2. Bundesliga", "German second division"),
        ("3. Liga", "German third division"),
        ("La Liga", "Spanish top division"),
        ("Liga Profesional Argentina", "Argentinian top division"),
    ]

    passed = 0
    failed = 0
    for name, desc in cases:
        result, reason = _is_non_senior_league(name)
        if result:
            failed += 1
            _check(
                f"senior_{name.replace(' ', '_')[:40]}",
                False,
                f"FALSE POSITIVE: '{name}' ({desc}) classified as '{reason}'",
            )
        else:
            passed += 1

    RESULTS["checks"]["senior_eligible_count"] = {
        "ok": True,
        "detail": f"{passed}/{passed + failed} passed",
    }
    if failed:
        RESULTS["blockers"].append(
            f"{failed} senior leagues falsely classified as non-senior"
        )


def test_nonsenior_excluded() -> None:
    """Non-senior leagues that MUST return (True, reason)."""
    cases = [
        ("Paulista U20", "youth", "Brazil U20 league"),
        ("Brasileiro U17", "youth", "Brazil U17 league"),
        ("UEFA U17 Championship", "youth", "U17 tournament"),
        ("U19 Bundesliga", "youth", "Germany U19 league"),
        ("U21 Premier League", "youth", "England U21 league"),
        ("Sub-20", "youth", "U20 Spanish naming"),
        ("Sub-17", "youth", "U17 Spanish naming"),
        ("Junior League", "youth", "Youth league"),
        ("Academy League", "youth", "Youth academy leage"),
        ("Youth League", "youth", "Generic youth"),
        ("Juvenil A", "youth", "Spanish youth"),
        ("Friendly", "friendly", "Exhibition match"),
        ("Club Friendly", "friendly", "Club exhibition"),
        ("International Friendly", "friendly", "International exhibition"),
        ("Cup", "cup", "Generic cup"),
        ("FA Cup", "cup", "England domestic cup"),
        ("Copa do Brasil", "cup", "Brazil cup"),
        ("Coppa Italia", "cup", "Italy cup"),
        ("Pokal", "cup", "German cup"),
        ("Play-off", "cup", "Playoff tournament"),
        ("Playoff", "cup", "Playoff tournament"),
        ("Reserve League", "reserve", "Reserve league"),
        ("Reserves", "reserve", "Reserve team league"),
        ("Reserve Team", "reserve", "Reserve team"),
        ("Reserve Division", "reserve", "Reserve division"),
        ("B Team", "reserve", "B team league"),
        ("B Team League", "reserve", "B team league"),
        ("B-Team", "reserve", "B team (hyphenated)"),
        ("II Team", "reserve", "Second team"),
        ("Second Team", "reserve", "Second team"),
        ("2nd Team", "reserve", "2nd team (digit)"),
        ("Women", "women", "Generic women"),
        ("Womens League", "women", "Women's league (no apostrophe)"),
        ("Women's League", "women", "Women's league"),
        ("Feminine Division 1", "women", "French women league"),
        ("Liga Femenina", "women", "Spanish women league"),
        ("Frauenliga", "women", "German women league"),
        ("Damer", "women", "Swedish women league"),
        ("Tournament", "cup", "Generic tournament"),
        ("Trophy", "cup", "Generic trophy"),
        ("UEFA Champions League", "international", "European club cup"),
        ("UEFA Europa League", "international", "European second tier cup"),
        ("Copa Libertadores", "international", "South American club cup"),
        ("Copa Sudamericana", "international", "South American second tier cup"),
        ("FIFA Club World Cup", "international", "Club world cup"),
        ("World Cup Qualification", "international", "WC qualifyer"),
    ]

    passed = 0
    failed = 0
    for name, expected_reason, desc in cases:
        result, reason = _is_non_senior_league(name)
        if not result:
            failed += 1
            _check(
                f"nonsenior_{name.replace(' ', '_')[:40]}",
                False,
                f"MISSED: '{name}' ({desc}) should be '{expected_reason}' but got senior",
            )
        elif reason != expected_reason:
            # Reason mismatch is a warning, not blocker
            RESULTS["warnings"].append(
                f"'{name}' ({desc}): expected reason '{expected_reason}', got '{reason}'"
            )
            passed += 1
        else:
            passed += 1

    RESULTS["checks"]["nonsenior_excluded_count"] = {
        "ok": True,
        "detail": f"{passed}/{passed + failed} passed",
    }
    if failed:
        RESULTS["blockers"].append(
            f"{failed} non-senior leagues missed by classifier"
        )


def test_safety_guards() -> None:
    """Check that no dangerous ops were triggered."""
    from engine.data_sources.h2h_engine import H2H_REFERENCE_MIN_SAMPLES, H2H_STRONG_SAMPLE_SIZE, H2H_STRONG_RATE_MIN

    # H2H thresholds should be unchanged
    _check("H2H_REFERENCE_MIN_SAMPLES", H2H_REFERENCE_MIN_SAMPLES == 4,
           f"value={H2H_REFERENCE_MIN_SAMPLES}")
    _check("H2H_STRONG_SAMPLE_SIZE", H2H_STRONG_SAMPLE_SIZE == 8,
           f"value={H2H_STRONG_SAMPLE_SIZE}")
    _check("H2H_STRONG_RATE_MIN", H2H_STRONG_RATE_MIN == 0.75,
           f"value={H2H_STRONG_RATE_MIN}")


def main() -> None:
    from datetime import datetime

    RESULTS["generated_at"] = datetime.now().isoformat()

    test_senior_eligible()
    test_nonsenior_excluded()
    test_safety_guards()

    # Compute conclusion
    if RESULTS["blockers"]:
        RESULTS["conclusion"] = "BLOCKER"
    elif RESULTS["warnings"]:
        RESULTS["conclusion"] = "WARN_ONLY"
    else:
        RESULTS["conclusion"] = "PASS"

    # Write output
    out_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "status"
        / f"check_v4_dynamic_league_classifier_{datetime.now().strftime('%Y%m%d')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False)

    print(json.dumps(RESULTS, indent=2, ensure_ascii=False))

    if RESULTS["blockers"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
