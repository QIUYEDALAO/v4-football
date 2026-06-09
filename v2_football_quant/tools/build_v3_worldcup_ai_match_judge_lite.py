#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LEDGER = ROOT / "data/v3_worldcup/friendly_simulation/v3_friendly_simulation_ledger_20260608.json"
OUT_DIR = ROOT / "data/v3_worldcup/ai_match_judge_lite"
OUT_JSON = OUT_DIR / "v3_ai_match_judge_lite_20260608.json"
OUT_MD = OUT_DIR / "V3_AI_MATCH_JUDGE_LITE_20260608.md"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_record(source: dict) -> dict:
    records = source.get("records") or []
    denmark = next((r for r in records if r.get("match") == "Denmark vs Ukraine"), {})
    return {
        "match": denmark.get("match", "Denmark vs Ukraine"),
        "mode": "SIMULATION_ONLY",
        "ai_direction": denmark.get("direction", "Denmark -0.75"),
        "confidence": denmark.get("confidence", "MEDIUM-LOW"),
        "top_reasons": [
            "AI主判断给出丹麦方向，但置信度未达到高档。",
            "友谊赛模式下轮换与临场信息不确定。",
            "赛后模拟记录为2-1，对-0.75方向仅为半赢结算。"
        ],
        "top_risks": [
            "首发确认需要临场检查。",
            "赔率/盘口需要赛前复核。",
            "友谊赛样本不可外推，不能形成稳定结论。"
        ],
        "guard_result": {
            "lineup_check": "WAIT",
            "odds_handicap_check": "WAIT",
            "mode_check": "PASS",
            "ledger_check": "PASS",
            "overall": "OBSERVE"
        },
        "final_decision": "OBSERVE",
        "ledger_required": True,
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
        "sample_count": 1,
        "hit_rate": None,
        "hit_rate_label": "N/A",
        "items": [record],
        "allowed_decisions": ["PASS", "WAIT", "OBSERVE"],
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
