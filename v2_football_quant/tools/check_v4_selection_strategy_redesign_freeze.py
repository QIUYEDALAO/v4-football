#!/usr/bin/env python3
"""Guard the V4 selection strategy redesign freeze.

This checker is read-only. It confirms that the strategy freeze keeps RF shadow
promotion blocked/observation-only and does not stage runtime or secrets.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/V4_SELECTION_STRATEGY_REDESIGN_FREEZE_20260606.md"
RF_STRICT_CHECKER = ROOT / "tools/check_v4_rf_shadow_promotion_dryrun.py"

EXPECTED_RF_BLOCKERS = {
    "shadow_b_above_official_b",
    "default_replay_distribution_changed",
    "skip_to_b_nonzero",
    "sensitivity_77_SKIP_to_B_count_unsafe:31",
    "sensitivity_73.5_SKIP_to_B_count_unsafe:34",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def run_rf_checker() -> dict:
    proc = subprocess.run(
        [sys.executable, str(RF_STRICT_CHECKER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = proc.stdout.strip()
    try:
        data = json.loads(text[text.find("{"):])
    except Exception:
        data = {}
    return {
        "returncode": proc.returncode,
        "conclusion": data.get("conclusion"),
        "blockers": data.get("blockers", []),
    }


def main() -> int:
    text = read(DOC)
    required = [
        "Strength gap must be explicit",
        "Market/line movement must confirm or at least not conflict",
        "Odds and price quality must be evaluable",
        "Data coverage must be sufficient",
        "H2H is auxiliary context only",
        "Historical matchup probability cannot manufacture A/B",
        "price-aware ROI ledger",
        "closing or last-pre-kickoff odds proxy",
        "market movement timeline",
        "league strength tier",
        "fatigue, travel, injury",
        "drawdown ledger",
        "`SKIP`",
        "`C`",
        "`shadow-only`",
        "`MARKET_NO_DATA`",
        "`MARKET_EXTREME`",
        "`H2H_LOW_SAMPLE`",
        "weak recent form",
        "stale recent form",
        "unknown recent form",
        "price-aware replay ledger",
        "No official A/B: daily report only",
        "does not attempt to increase daily picks",
    ]
    forbidden_profit_claim = re.search(
        r"(?i)(guaranteed profit|must bet|sure win|lock profit|稳赚|稳赢|必下|资金流结论)",
        text,
    )
    rf = run_rf_checker()
    rf_blockers = set(str(x) for x in rf.get("blockers", []))

    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = [
        p for p in staged
        if p.startswith(("v2_football_quant/data/runtime/", "v2_football_quant/data/cache/"))
        or re.search(r"(?i)(secret|token|\\.env|api[_-]?key)", p)
    ]

    checks = {
        "doc_exists": DOC.exists(),
        "required_strategy_terms_present": all(term in text for term in required),
        "no_profit_or_betting_certainty_claim": forbidden_profit_claim is None,
        "rf_strict_checker_remains_blocked": rf.get("conclusion") == "BLOCKER" and rf.get("returncode") != 0,
        "rf_blockers_are_expected_expansion_risks": EXPECTED_RF_BLOCKERS.issubset(rf_blockers),
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_selection_strategy_redesign_freeze_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "rf_shadow_promotion": rf,
        "forbidden_staged": forbidden_staged,
        "official_grade_changed": False,
        "ab_threshold_changed": False,
        "pending_bet_candidates_written": False,
        "validation_recomputed": False,
        "live_bet_modified": False,
        "qq_sent": False,
        "cron_or_launchd_modified": False,
        "runtime_commit_required": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
