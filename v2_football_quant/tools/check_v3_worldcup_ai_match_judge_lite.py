#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
BUILDER = ROOT / "tools/build_v3_worldcup_ai_match_judge_lite.py"
OUT_JSON = ROOT / "data/v3_worldcup/ai_match_judge_lite/v3_ai_match_judge_lite_20260608.json"
OUT_MD = ROOT / "data/v3_worldcup/ai_match_judge_lite/V3_AI_MATCH_JUDGE_LITE_20260608.md"
SOURCE_LEDGER = ROOT / "data/v3_worldcup/friendly_simulation/v3_friendly_simulation_ledger_20260608.json"

REQUIRED_FIELDS = {
    "match",
    "mode",
    "ai_direction",
    "confidence",
    "top_reasons",
    "top_risks",
    "guard_result",
    "final_decision",
    "ledger_required",
}
ALLOWED_DECISIONS = {"PASS", "WAIT", "OBSERVE"}
FORBIDDEN_TERMS = [
    "推荐下注",
    "投注建议",
    "重仓",
    "梭哈",
    "必中",
    "稳胆",
    "pending_bet",
    "official_grade",
]


def fail(code: str, detail: str | None = None) -> int:
    payload = {"conclusion": "FAIL", "code": code}
    if detail:
        payload["detail"] = detail
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AssertionError(f"json_load_failed:{path}:{exc}") from exc


def git_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"git_diff_cached_failed:{result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def assert_no_forbidden_text(paths: list[Path]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in FORBIDDEN_TERMS:
            if term in text:
                raise AssertionError(f"forbidden_term:{term}:{path}")


def assert_no_runtime_or_secret_staged(staged: list[str]) -> None:
    for path in staged:
        lower = path.lower()
        if any(part in lower for part in ["/runtime/", "/cache/", "/logs/", "/tmp/"]):
            raise AssertionError(f"runtime_cache_log_staged:{path}")
        if any(token in lower for token in [".env", "secret", "token", "apikey", "api_key"]):
            raise AssertionError(f"secret_like_staged:{path}")


def main() -> int:
    try:
        if not BUILDER.exists():
            return fail("builder_missing", str(BUILDER))
        if not SOURCE_LEDGER.exists():
            return fail("source_ledger_missing", str(SOURCE_LEDGER))

        build = subprocess.run(
            [sys.executable, str(BUILDER)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if build.returncode != 0:
            return fail("builder_failed", build.stderr.strip())

        if not OUT_JSON.exists():
            return fail("output_json_missing", str(OUT_JSON))
        if not OUT_MD.exists():
            return fail("output_md_missing", str(OUT_MD))

        payload = load_json(OUT_JSON)
        items = payload.get("items") or []
        if len(items) != 1:
            return fail("item_count_mismatch", str(len(items)))

        record = items[0]
        missing = sorted(REQUIRED_FIELDS - set(record))
        if missing:
            return fail("required_fields_missing", ",".join(missing))

        if record["mode"] != "SIMULATION_ONLY":
            return fail("mode_not_simulation_only", str(record["mode"]))
        if record["final_decision"] not in ALLOWED_DECISIONS:
            return fail("invalid_final_decision", str(record["final_decision"]))
        if record["final_decision"] != "OBSERVE":
            return fail("unexpected_current_decision", str(record["final_decision"]))
        if record["ledger_required"] is not True:
            return fail("ledger_required_not_true")

        guard = record.get("guard_result") or {}
        expected_guard = {
            "lineup_check": "WAIT",
            "odds_handicap_check": "WAIT",
            "mode_check": "PASS",
            "ledger_check": "PASS",
            "overall": "OBSERVE",
        }
        for key, value in expected_guard.items():
            if guard.get(key) != value:
                return fail("guard_mismatch", f"{key}={guard.get(key)}")

        safety = record.get("safety") or {}
        expected_false = ["dashboard_required", "read_model_required", "pending_written", "qq_sent", "affects_v4"]
        for key in expected_false:
            if safety.get(key) is not False:
                return fail("safety_false_mismatch", f"{key}={safety.get(key)}")
        if safety.get("simulation_only") is not True or safety.get("lite_output") is not True:
            return fail("safety_true_mismatch")

        ledger_ref = record.get("ledger_ref")
        if ledger_ref != "data/v3_worldcup/friendly_simulation/v3_friendly_simulation_ledger_20260608.json":
            return fail("ledger_ref_mismatch", str(ledger_ref))

        top_reasons = record.get("top_reasons")
        top_risks = record.get("top_risks")
        if not isinstance(top_reasons, list) or len(top_reasons) < 2:
            return fail("top_reasons_insufficient")
        if not isinstance(top_risks, list) or len(top_risks) < 2:
            return fail("top_risks_insufficient")

        if payload.get("sample_count") != 1 or payload.get("hit_rate") is not None:
            return fail("sample_or_hit_rate_mismatch")
        if payload.get("hit_rate_label") != "N/A":
            return fail("hit_rate_label_mismatch", str(payload.get("hit_rate_label")))

        assert_no_forbidden_text([OUT_JSON, OUT_MD])
        assert_no_runtime_or_secret_staged(git_staged_files())

        print(json.dumps({
            "conclusion": "PASS",
            "match": record["match"],
            "mode": record["mode"],
            "final_decision": record["final_decision"],
            "ledger_required": record["ledger_required"],
            "guard_result": guard,
            "sample_count": payload["sample_count"],
            "hit_rate": "N/A"
        }, ensure_ascii=False, indent=2))
        return 0
    except AssertionError as exc:
        return fail("assertion_failed", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
