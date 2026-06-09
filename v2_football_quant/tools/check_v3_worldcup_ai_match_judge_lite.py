#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from v3_ai_match_judge_lite_decision_engine import DecisionInput, deterministic_decision

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
BUILDER = ROOT / "tools/build_v3_worldcup_ai_match_judge_lite.py"
DECISION_ENGINE = ROOT / "tools/v3_ai_match_judge_lite_decision_engine.py"
OUT_JSON = ROOT / "data/v3_worldcup/ai_match_judge_lite/v3_ai_match_judge_lite_20260608.json"
OUT_MD = ROOT / "data/v3_worldcup/ai_match_judge_lite/V3_AI_MATCH_JUDGE_LITE_20260608.md"
SCHEMA_PATH = ROOT / "data/v3_worldcup/ai_match_judge_lite/v3_ai_match_judge_lite_schema.json"
PROMPT_TEMPLATE_PATH = ROOT / "data/v3_worldcup/ai_match_judge_lite/V3_AI_MATCH_JUDGE_LITE_PROMPT_TEMPLATE.md"
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


def assert_deterministic_decision() -> dict:
    decision_input = DecisionInput(
        lineup_status="CONFIRMED",
        odds_handicap_status="PRESENT",
        score_gap=8,
        market_check="SUPPORT",
        match_type="FRIENDLY",
        rotation_risk="MEDIUM",
    )
    runs = [deterministic_decision(decision_input) for _ in range(3)]
    signatures = [
        (
            run.final_decision,
            run.rule_id,
            tuple(sorted(run.guard_result.items())),
            run.downgrade_reason,
            run.ledger_required,
        )
        for run in runs
    ]
    if len(set(signatures)) != 1:
        raise AssertionError("deterministic_decision_not_stable")
    first = runs[0]
    if first.final_decision != "OBSERVE":
        raise AssertionError(f"deterministic_decision_unexpected:{first.final_decision}")
    if first.guard_result.get("mode_check") != "DOWNGRADE_FRIENDLY":
        raise AssertionError("deterministic_mode_guard_mismatch")
    return {
        "repeat_runs": 3,
        "final_decision": first.final_decision,
        "rule_id": first.rule_id,
        "guard_result": first.guard_result,
    }


def main() -> int:
    try:
        if not BUILDER.exists():
            return fail("builder_missing", str(BUILDER))
        if not DECISION_ENGINE.exists():
            return fail("decision_engine_missing", str(DECISION_ENGINE))
        if not SCHEMA_PATH.exists():
            return fail("schema_missing", str(SCHEMA_PATH))
        if not PROMPT_TEMPLATE_PATH.exists():
            return fail("prompt_template_missing", str(PROMPT_TEMPLATE_PATH))
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
        if record["final_decision"] not in (ALLOWED_DECISIONS | {"PLAY"}):
            return fail("invalid_final_decision", str(record["final_decision"]))
        if record["final_decision"] != "OBSERVE":
            return fail("unexpected_current_decision", str(record["final_decision"]))
        if record["ledger_required"] is not True:
            return fail("ledger_required_not_true")

        guard = record.get("guard_result") or {}
        expected_guard = {
            "lineup_check": "PASS",
            "odds_handicap_check": "PASS",
            "mode_check": "DOWNGRADE_FRIENDLY",
            "ledger_check": "REQUIRED",
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

        if payload.get("schema_path") != "data/v3_worldcup/ai_match_judge_lite/v3_ai_match_judge_lite_schema.json":
            return fail("schema_path_mismatch", str(payload.get("schema_path")))
        if payload.get("prompt_template_path") != "data/v3_worldcup/ai_match_judge_lite/V3_AI_MATCH_JUDGE_LITE_PROMPT_TEMPLATE.md":
            return fail("prompt_template_path_mismatch", str(payload.get("prompt_template_path")))
        if payload.get("decision_engine_path") != "tools/v3_ai_match_judge_lite_decision_engine.py":
            return fail("decision_engine_path_mismatch", str(payload.get("decision_engine_path")))

        schema = load_json(SCHEMA_PATH)
        if schema.get("threshold_lock", {}).get("model_may_change_thresholds") is not False:
            return fail("threshold_lock_missing")
        if schema.get("fixed_five_dimension_weights", {}).get("score_gap") != 25:
            return fail("fixed_weights_mismatch")

        prompt = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
        for required in ["Fixed Input Fields", "Fixed Five Dimension Weights", "Fixed Scoring Policy", "Output JSON Schema", "禁止模型自由改阈值"]:
            if required not in prompt:
                return fail("prompt_template_missing_section", required)

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

        deterministic_check = assert_deterministic_decision()
        assert_no_forbidden_text([OUT_JSON, OUT_MD, SCHEMA_PATH, PROMPT_TEMPLATE_PATH])
        assert_no_runtime_or_secret_staged(git_staged_files())

        print(json.dumps({
            "conclusion": "PASS",
            "match": record["match"],
            "mode": record["mode"],
            "final_decision": record["final_decision"],
            "ledger_required": record["ledger_required"],
            "guard_result": guard,
            "deterministic_check": deterministic_check,
            "schema_path": str(SCHEMA_PATH.relative_to(ROOT)),
            "prompt_template_path": str(PROMPT_TEMPLATE_PATH.relative_to(ROOT)),
            "decision_engine_path": str(DECISION_ENGINE.relative_to(ROOT)),
            "sample_count": payload["sample_count"],
            "hit_rate": "N/A"
        }, ensure_ascii=False, indent=2))
        return 0
    except AssertionError as exc:
        return fail("assertion_failed", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
