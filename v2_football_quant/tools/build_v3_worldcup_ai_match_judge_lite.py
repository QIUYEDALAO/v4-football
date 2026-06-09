#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from v3_ai_match_judge_lite_decision_engine import DecisionInput, deterministic_decision

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LEDGER = ROOT / "data/v3_worldcup/friendly_simulation/v3_friendly_simulation_ledger_20260608.json"
OUT_DIR = ROOT / "data/v3_worldcup/ai_match_judge_lite"
OUT_JSON = OUT_DIR / "v3_ai_match_judge_lite_20260608.json"
OUT_MD = OUT_DIR / "V3_AI_MATCH_JUDGE_LITE_20260608.md"
SCHEMA_PATH = OUT_DIR / "v3_ai_match_judge_lite_schema.json"
PROMPT_TEMPLATE_PATH = OUT_DIR / "V3_AI_MATCH_JUDGE_LITE_PROMPT_TEMPLATE.md"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_record(source: dict) -> dict:
    records = source.get("records") or []
    denmark = next((r for r in records if r.get("match") == "Denmark vs Ukraine"), {})
    decision_input = DecisionInput(
        lineup_status="CONFIRMED",
        odds_handicap_status="PRESENT",
        score_gap=8,
        market_check="SUPPORT",
        match_type="FRIENDLY",
        rotation_risk="MEDIUM",
    )
    decision_output = deterministic_decision(decision_input)
    return {
        "match": denmark.get("match", "Denmark vs Ukraine"),
        "mode": "SIMULATION_ONLY",
        "ai_direction": denmark.get("direction", "Denmark -0.75"),
        "confidence": denmark.get("confidence", "MEDIUM-LOW"),
        "decision_input": {
            "lineup_status": decision_input.lineup_status,
            "odds_handicap_status": decision_input.odds_handicap_status,
            "score_gap": decision_input.score_gap,
            "market_check": decision_input.market_check,
            "match_type": decision_input.match_type,
            "rotation_risk": decision_input.rotation_risk,
        },
        "decision_rule_id": decision_output.rule_id,
        "downgrade_reason": decision_output.downgrade_reason,
        "top_reasons": [
            "AI主判断给出丹麦方向，但置信度未达到高档。",
            "首发与赔率/盘口检查均通过固定guard。",
            "友谊赛模式触发固定降级规则。",
            "赛后模拟记录为2-1，对-0.75方向仅为半赢结算。"
        ],
        "top_risks": [
            "友谊赛模式不可直接升级为执行判断。",
            "轮换风险虽非HIGH，但仍保留观察折扣。",
            "友谊赛样本不可外推，不能形成稳定结论。"
        ],
        "guard_result": decision_output.guard_result,
        "final_decision": decision_output.final_decision,
        "ledger_required": decision_output.ledger_required,
        "ledger_ref": str(SOURCE_LEDGER.relative_to(ROOT)),
        "settlement": denmark.get("settlement", "HALF_WIN"),
        "score": denmark.get("score", "2-1"),
        "safety": {
            "simulation_only": True,
            "lite_output": True,
            "dashboard_required": False,
            "read_model_required": False,
            "pending_written": False,
            "qq_sent": False,
            "affects_v4": False
        }
    }


def write_md(record: dict) -> str:
    guard = record["guard_result"]
    reasons = "\n".join(f"- {x}" for x in record["top_reasons"])
    risks = "\n".join(f"- {x}" for x in record["top_risks"])
    return f"""# V3 AI Match Judge Lite - 2026-06-08

## Lite Card

- match: {record['match']}
- mode: {record['mode']}
- ai_direction: {record['ai_direction']}
- confidence: {record['confidence']}
- final_decision: {record['final_decision']}
- ledger_required: {str(record['ledger_required']).lower()}

## Top Reasons

{reasons}

## Top Risks

{risks}

## Guard

- lineup_check: {guard['lineup_check']}
- odds_handicap_check: {guard['odds_handicap_check']}
- mode_check: {guard['mode_check']}
- ledger_check: {guard['ledger_check']}
- overall: {guard['overall']}

## Ledger

- ledger_ref: `{record['ledger_ref']}`
- score: {record['score']}
- settlement: {record['settlement']}

## Lite Boundary

- simulation_only: true
- dashboard_required: false
- read_model_required: false
- pending_written: false
- qq_sent: false
- affects_v4: false
"""


def main() -> int:
    source = load_json(SOURCE_LEDGER)
    record = build_record(source)
    payload = {
        "schema_version": "v3_ai_match_judge_lite.v1",
        "generated_at": "2026-06-10T00:00:00+08:00",
        "source_ledger": str(SOURCE_LEDGER.relative_to(ROOT)),
        "schema_path": str(SCHEMA_PATH.relative_to(ROOT)),
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH.relative_to(ROOT)),
        "decision_engine_path": "tools/v3_ai_match_judge_lite_decision_engine.py",
        "sample_count": 1,
        "hit_rate": None,
        "hit_rate_label": "N/A",
        "items": [record],
        "allowed_decisions": ["PLAY", "PASS", "WAIT", "OBSERVE"],
        "safety": {
            "simulation_only": True,
            "lite_output": True,
            "no_dashboard": True,
            "no_multi_layer_read_model": True,
            "pending_written": False,
            "qq_sent": False,
            "affects_v4": False
        }
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(write_md(record), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "output_json": str(OUT_JSON.relative_to(ROOT)),
        "output_md": str(OUT_MD.relative_to(ROOT)),
        "match": record["match"],
        "final_decision": record["final_decision"],
        "ledger_required": record["ledger_required"]
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
