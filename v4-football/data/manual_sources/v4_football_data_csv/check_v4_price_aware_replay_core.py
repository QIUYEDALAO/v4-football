#!/usr/bin/env python3
"""Check V4 Football-Data price-aware replay core outputs."""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parents[3]
BUILDER = DATA_DIR / "build_v4_price_aware_replay_core.py"
DATASET_CHECKER = DATA_DIR / "check_v4_football_data_replay_dataset.py"
CSV_AUDIT_CHECKER = DATA_DIR / "check_v4_football_data_csv_audit.py"
LEDGER = DATA_DIR / "processed/v4_price_aware_replay_core_ledger.csv"
SUMMARY = DATA_DIR / "processed/v4_price_aware_replay_core_summary.json"
DOC = DATA_DIR / "V4_FOOTBALL_DATA_PRICE_AWARE_REPLAY_CORE.md"

FORBIDDEN_TEXT = re.compile(
    r"推荐|投注建议|下注|实单|必中|稳胆|must bet|betting advice",
    re.IGNORECASE,
)
EXPECTED_MARKETS = {"1X2", "ASIAN_HANDICAP", "DOUBLE_CHANCE_PROXY", "FT_OVER25"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run_py(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True, timeout=240)


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def staged_forbidden(staged: list[str]) -> list[str]:
    bad: list[str] = []
    for path in staged:
        lower = path.lower()
        if re.search(r"(^|/)(runtime|cache|logs?|secrets?)(/|$)", lower):
            bad.append(path)
        if re.search(r"(^|/)(\\.env|.*\\.env|.*\\.key|.*token.*)(/|$)", lower):
            bad.append(path)
    return sorted(set(bad))


def market_metrics(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["market"]: row for row in summary.get("metrics", []) if isinstance(row, dict)}


def ah_unit_tests() -> bool:
    sys.path.insert(0, str(DATA_DIR))
    import build_v4_price_aware_replay_core as core  # noqa: WPS433

    cases = [
        (2, 1, Decimal("-0.75"), Decimal("0.5")),
        (1, 1, Decimal("0"), Decimal("0")),
        (1, 1, Decimal("-0.25"), Decimal("-0.5")),
        (1, 1, Decimal("0.25"), Decimal("0.5")),
        (1, 2, Decimal("0.75"), Decimal("-0.5")),
        (3, 1, Decimal("-1.5"), Decimal("1")),
    ]
    for gf, ga, line, expected in cases:
        status, actual = core.settle_ah(gf, ga, line)
        if status != "SETTLED" or actual != expected:
            return False
    status, actual = core.settle_ah(1, 1, Decimal("0.33"))
    return status == "AH_SETTLEMENT_UNCERTAIN" and actual is None


def main() -> int:
    builder = run_py(BUILDER)
    dataset = run_py(DATASET_CHECKER)
    audit = run_py(CSV_AUDIT_CHECKER)
    summary = load_json(SUMMARY) or {}
    ledger = read_csv(LEDGER)
    metrics = market_metrics(summary)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    text = ""
    for path in [SUMMARY, DOC]:
        if path.exists():
            text += path.read_text(encoding="utf-8")
    seasons = set(summary.get("seasons") or [])
    dc_entries = [row for row in ledger if row.get("market") == "DOUBLE_CHANCE_PROXY"]
    ah_entries = [row for row in ledger if row.get("market") == "ASIAN_HANDICAP"]
    uncertain_ah = [row for row in ah_entries if row.get("settlement_status") == "AH_SETTLEMENT_UNCERTAIN"]
    policy = summary.get("policy_lock") or {}
    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder.returncode == 0,
        "ledger_exists": LEDGER.exists(),
        "summary_exists": SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "dataset_checker_pass": dataset.returncode == 0,
        "csv_audit_checker_pass": audit.returncode == 0,
        "dataset_rows_15448": summary.get("dataset_rows") == 15448,
        "no_2025_26": "2025/26" not in seasons,
        "expected_markets": set(summary.get("markets") or []) == EXPECTED_MARKETS,
        "ledger_row_count": len(ledger) == 15448 * 9,
        "ft_over_settled": metrics.get("FT_OVER25", {}).get("settled_count", 0) > 15000,
        "one_x_two_settled": metrics.get("1X2", {}).get("settled_count", 0) > 45000,
        "double_chance_no_roi": metrics.get("DOUBLE_CHANCE_PROXY", {}).get("roi_proxy_flat_1u") is None
        and metrics.get("DOUBLE_CHANCE_PROXY", {}).get("roi_policy") == "ROI_NOT_COMPUTED_NO_REAL_DC_PRICE"
        and all(row.get("price_status") == "NO_REAL_DOUBLE_CHANCE_ODDS" for row in dc_entries[:100]),
        "ah_unit_tests_pass": ah_unit_tests(),
        "ah_uncertain_excludes_roi": all(row.get("pnl_proxy_flat_1u") == "" for row in uncertain_ah),
        "roi_real_close_only": all(
            row.get("price_status") == "REAL_CLOSE_ODDS"
            for row in ledger
            if row.get("pnl_proxy_flat_1u")
        ),
        "no_forbidden_text": FORBIDDEN_TEXT.search(text) is None,
        "policy_lock": policy.get("api_football_called") is False
        and policy.get("v4_scan_executed") is False
        and policy.get("official_grade_changed") is False
        and policy.get("pending_written") is False
        and policy.get("qq_sent") is False
        and policy.get("cron_or_launchd_modified") is False
        and policy.get("strategy_online") is False
        and policy.get("recommendation_generated") is False,
        "no_runtime_cache_log_secret_staged": not staged_forbidden(staged),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_price_aware_replay_core_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "metrics": summary.get("metrics"),
        "ledger_rows": len(ledger),
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
