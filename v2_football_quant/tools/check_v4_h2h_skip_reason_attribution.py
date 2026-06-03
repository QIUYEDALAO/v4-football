#!/usr/bin/env python3
"""Check V4 skip attribution does not present H2H low sample as a hard gate."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "data/daily_reports"
STATUS = ROOT / "data/runtime/status"
MODEL = STATUS / "v4_control_center_model_20260603.json"
CANDIDATE = STATUS / "v4_official_candidate_view_20260603.json"
BRIEF = DAILY / "v4_openclaw_brief_20260603.txt"
SCAN_PERF = DAILY / "scan_perf_v4_20260603.json"
SCOUT = DAILY / "scout_v4_20260603.json"
RUNNER = ROOT / "engine/v4_runner.py"
SCAN_SUPERVISOR = ROOT / "engine/v4_scan_and_brief.py"
OUT = STATUS / "check_v4_h2h_skip_reason_attribution_20260603.json"

H2H_DATA_GAP_NOTE = "资料缺口：H2H样本不足，不参与评分。"


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    checks: dict[str, bool] = {}
    blockers: list[str] = []
    scan_perf = load_json(SCAN_PERF)
    scout = load_json(SCOUT)
    candidate = load_json(CANDIDATE)
    model = load_json(MODEL)
    brief = BRIEF.read_text(encoding="utf-8", errors="ignore") if BRIEF.exists() else ""
    runner = RUNNER.read_text(encoding="utf-8", errors="ignore") if RUNNER.exists() else ""
    supervisor = SCAN_SUPERVISOR.read_text(encoding="utf-8", errors="ignore") if SCAN_SUPERVISOR.exists() else ""

    top = model.get("top_status", {}).get("today_candidates", {}) if isinstance(model, dict) else {}
    model_candidates = model.get("candidates", {}) if isinstance(model, dict) else {}
    model_skip_items = model.get("skip", {}).get("items", []) if isinstance(model.get("skip"), dict) else []
    candidate_skip_items = candidate.get("SKIP_candidates", []) if isinstance(candidate, dict) else []

    checks["scan_perf_total_15"] = scan_perf.get("total_fixtures") == 15
    checks["scan_perf_scouted_1"] = scan_perf.get("scouted_count") == 1
    checks["scout_one_row_preserved"] = isinstance(scout, list) and len(scout) == 1
    checks["candidate_counts_from_scan_total"] = {
        "A": candidate.get("A_count"),
        "B": candidate.get("B_count"),
        "C": candidate.get("C_count"),
        "SKIP": candidate.get("SKIP_count"),
        "scan_total": candidate.get("scan_total"),
    } == {"A": 0, "B": 0, "C": 0, "SKIP": 15, "scan_total": 15}
    checks["candidate_skip_attribution_visible"] = len(candidate_skip_items) >= 14
    checks["candidate_h2h_gap_note_only"] = all(
        (not str(x.get("reason") or x.get("skip_reason") or "").startswith("H2H"))
        and (not x.get("h2h_data_gap") or x.get("h2h_data_gap_note") == H2H_DATA_GAP_NOTE)
        for x in candidate_skip_items
        if isinstance(x, dict)
    )
    checks["brief_counts_from_candidate"] = all(token in brief for token in [
        "HT_SKIP跳过：15场",
        "全量扫描：15场",
        "综合前筛未达标",
        H2H_DATA_GAP_NOTE,
    ])
    checks["brief_no_h2h_main_reason"] = "H2H_未达标" not in brief and "H2H不足未达标" not in brief
    checks["model_counts_from_scan_total"] = {
        "A": top.get("A"),
        "B": top.get("B"),
        "SKIP": top.get("SKIP"),
        "scan_total": top.get("scan_total"),
    } == {"A": 0, "B": 0, "SKIP": 15, "scan_total": 15}
    checks["model_skip_attribution_visible"] = len(model_skip_items) >= 14
    model_reason_text = "\n".join(
        str(x.get("reason") or x.get("skip_reason") or x.get("filter_reason") or "")
        for x in model_skip_items
        if isinstance(x, dict)
    )
    checks["model_no_h2h_main_reason"] = "H2H_未达标" not in model_reason_text and "H2H不足未达标" not in model_reason_text
    checks["model_h2h_gap_note_only"] = any(
        isinstance(x, dict) and x.get("h2h_data_gap_note") == H2H_DATA_GAP_NOTE
        for x in model_skip_items
    )
    checks["future_runner_uses_composite_reason"] = (
        "filter_reason\": f\"H2H_" not in runner
        and "PRE_SCOUT_COMPOSITE_GATE_INVALID" in runner
        and H2H_DATA_GAP_NOTE in runner
    )
    checks["scan_adapter_uses_scan_perf_total"] = (
        "_scan_total_from_perf" in supervisor
        and "scan_perf_total_fixtures" in supervisor
        and "SKIP_candidates" in supervisor
    )
    checks["h2h_low_sample_add_only_rule_present"] = "H2H低样本仅标注，不触发降级" in supervisor

    # Guard against accidental threshold changes in this task.
    checks["no_threshold_tokens_changed_by_checker_scope"] = all(token in runner for token in [
        "H2H_MAX_REQUIRED_RATIO = 0.35",
        "H2H_PER_FIXTURE_TIMEOUT_SECONDS = 20",
    ])

    blockers = [name for name, ok in checks.items() if not ok]
    out = {
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
        "scan_perf": {
            "total_fixtures": scan_perf.get("total_fixtures"),
            "scouted_count": scan_perf.get("scouted_count"),
        },
        "candidate_counts": {
            "A": candidate.get("A_count"),
            "B": candidate.get("B_count"),
            "C": candidate.get("C_count"),
            "SKIP": candidate.get("SKIP_count"),
            "scan_total": candidate.get("scan_total"),
        },
        "model_counts": {
            "A": top.get("A"),
            "B": top.get("B"),
            "SKIP": top.get("SKIP"),
            "scan_total": top.get("scan_total"),
        },
        "h2h_current_role": "资料缺口说明，不作为SKIP主因",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ["conclusion", "blockers", "scan_perf", "candidate_counts", "model_counts", "h2h_current_role"]}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
