#!/usr/bin/env python3
"""Check V4 price-aware replay ledger artifacts."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/manual_sources/v4/price_aware_replay/v4_official_ab_price_aware_replay_ledger_20260606.json"
SUMMARY = ROOT / "data/manual_sources/v4/price_aware_replay/v4_official_ab_price_aware_replay_summary_20260606.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def main() -> int:
    ledger = load(LEDGER) if LEDGER.exists() else {}
    summary = load(SUMMARY) if SUMMARY.exists() else {}
    records = ledger.get("records", []) if isinstance(ledger, dict) else []
    required_fields = {
        "event_id",
        "fixture_id",
        "date",
        "official_grade",
        "result_hit",
        "odds_proxy",
        "implied_break_even",
        "pnl_proxy",
        "cumulative_pnl_proxy",
        "drawdown_proxy",
        "market_conflict",
        "league_tier",
        "season_phase",
        "sample_warning",
    }
    a_settled = [r for r in records if r.get("official_grade") == "A" and r.get("result_hit") in (True, False)]
    b_settled = [r for r in records if r.get("official_grade") == "B" and r.get("result_hit") in (True, False)]
    ab_settled = a_settled + b_settled
    a_hit = sum(1 for r in a_settled if r.get("result_hit") is True)
    b_hit = sum(1 for r in b_settled if r.get("result_hit") is True)
    ab_hit = a_hit + b_hit
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    forbidden_staged = [
        p for p in staged
        if p.startswith(("v2_football_quant/data/runtime/", "v2_football_quant/data/cache/"))
        or re.search(r"(?i)(secret|token|\\.env|api[_-]?key)", p)
    ]
    checks = {
        "ledger_exists": LEDGER.exists(),
        "summary_exists": SUMMARY.exists(),
        "records_present": len(records) >= 144,
        "all_required_fields": all(required_fields.issubset(set(r)) for r in records),
        "official_A_matches_boss": (a_hit, len(a_settled)) == (30, 49),
        "official_B_matches_boss": (b_hit, len(b_settled)) == (54, 95),
        "official_AB_matches_boss": (ab_hit, len(ab_settled)) == (84, 144),
        "has_aggregate_reconciliation_warning": any(r.get("sample_warning") == "AGGREGATE_RECONCILIATION_NO_EVENT_SOURCE" for r in records),
        "bucket_stats_present": all(k in summary.get("bucket_stats", {}) for k in ["official_grade", "AB", "market_conflict", "league_tier", "season_phase"]),
        "risk_policy_keeps_B_paused": summary.get("risk_conclusion", {}).get("B") == "PAUSE_REALTIME_REMINDER",
        "risk_policy_keeps_AB_daily_only": summary.get("risk_conclusion", {}).get("AB") == "DAILY_REPORT_ONLY",
        "safety_fields": all(summary.get("safety", {}).get(k) is v for k, v in {
            "observation_only": True,
            "betting_recommendation": False,
            "official_grade_changed": False,
            "pending_bet_candidates_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "rf_shadow_promotion_released": False,
            "runtime_output": False,
        }.items()),
        "no_runtime_or_secret_staged": not forbidden_staged,
    }
    blockers = [k for k, v in checks.items() if not v]
    result = {
        "schema_version": "v4_price_aware_replay_ledger_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "official_record": {
            "A": f"{a_hit}/{len(a_settled)}",
            "B": f"{b_hit}/{len(b_settled)}",
            "AB": f"{ab_hit}/{len(ab_settled)}",
        },
        "aggregate_reconciliation_rows": summary.get("aggregate_reconciliation_rows"),
        "risk_conclusion": summary.get("risk_conclusion"),
        "forbidden_staged": forbidden_staged,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
