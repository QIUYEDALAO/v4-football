#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "v2_football_quant/data/runtime/status/check_working_tree_dirty_hygiene_20260604.json"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
RUNTIME_RE = re.compile(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", re.I)
SECRET_PATH_RE = re.compile(r"(^|/)(\.env|.*\.env|.*\.key|.*secret.*|.*token.*)(/|$)", re.I)
V4_PATH_RE = re.compile(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", re.I)
APPROVED_UNTRACK_ALLOWLIST = {
    "v2_football_quant/data/runtime/status/check_v4_all_eligible_candidate_pool_result.json",
    "v2_football_quant/data/runtime/status/check_v4_control_center_content_checker_20260526.json",
    "v2_football_quant/data/runtime/status/check_v4_whitelist57_split_stats_result.json",
    "v2_football_quant/data/runtime/status/v4_control_center_model_20260526.json",
    "v2_football_quant/data/runtime/status/v4_daily_scan_parallel_adapter_checker_20260527.json",
    "v2_football_quant/data/runtime/status/v4_lab_fullscan_checker_20260527.json",
    "v2_football_quant/data/runtime/status/v4_lab_production_clone_h2h_last3_checker_20260527.json",
    "v2_football_quant/data/runtime/status/v4_production_default_rules_guard_20260527.json",
    "v2_football_quant/data/runtime/status/v4_recent_form_sample_size_checker_20260527.json",
}
APPROVED_TRACKED_RUNTIME_UI_STAGE_ALLOWLIST = {
    "v2_football_quant/data/runtime/dashboard/v3_worldcup_wc10_war_room.html",
    "v2_football_quant/data/runtime/dashboard/v4_control_center.html",
}
APPROVED_V4_AUDIT_STAGE_ALLOWLIST = {
    "v2_football_quant/docs/V4_PRICE_SOURCE_AND_SELECTION_SIGNAL_INVENTORY_20260606.md",
    "v2_football_quant/docs/V4_PRICE_FIELD_PERSISTENCE_PIPELINE_20260606.md",
    "v2_football_quant/docs/V4_MAIN_LEAGUE_WHITELIST_AND_ADMISSION_GUARD_20260606.md",
    "v2_football_quant/docs/V4_MARKET_STRATEGY_RESEARCH_CARD_PACK_20260606.md",
    "v2_football_quant/docs/V4_MARKET_STRATEGY_RESEARCH_CARD_PACK_20260607.md",
    "v2_football_quant/docs/V4_MARKET_STRATEGY_CARD_REPLAY_LEDGER_PACK_20260607.md",
    "v2_football_quant/docs/V4_MARKET_STRATEGY_CARD_REPLAY_EXPANSION_PACK_20260607.md",
    "v2_football_quant/docs/V4_FIVE_DIMENSION_LITE_SCHEMA_PACK_20260607.md",
    "v2_football_quant/docs/V4_RESEARCH_CARD_DATA_COMPLETENESS_SMOKE_PACK_20260607.md",
    "v2_football_quant/config/v4_main_league_admission_policy.json",
    "v2_football_quant/config/v4_five_dimension_lite_schema.json",
    "v2_football_quant/config/v4_market_strategy_card_replay_ledger_schema.json",
    "v2_football_quant/config/v4_market_strategy_card_replay_expansion_schema.json",
    "v2_football_quant/data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_20260606.json",
    "v2_football_quant/data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_summary_20260606.json",
    "v2_football_quant/data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_20260607.json",
    "v2_football_quant/data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_summary_20260607.json",
    "v2_football_quant/data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_ledger_20260607.json",
    "v2_football_quant/data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_summary_20260607.json",
    "v2_football_quant/data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_expansion_20260607.json",
    "v2_football_quant/data/manual_sources/v4/market_strategy_replay/v4_market_strategy_card_replay_expansion_summary_20260607.json",
    "v2_football_quant/data/manual_sources/v4/five_dimension_lite/v4_five_dimension_lite_samples_20260607.json",
    "v2_football_quant/data/manual_sources/v4/five_dimension_lite/v4_five_dimension_lite_summary_20260607.json",
    "v2_football_quant/engine/v4_league_admission.py",
    "v2_football_quant/engine/v4_runner.py",
    "v2_football_quant/engine/v4_scan_and_brief.py",
    "v2_football_quant/tools/build_v4_ab_historical_ledger.py",
    "v2_football_quant/tools/build_v4_official_candidate_view.py",
    "v2_football_quant/tools/build_v4_market_strategy_research_cards.py",
    "v2_football_quant/tools/build_v4_market_strategy_card_replay_ledger.py",
    "v2_football_quant/tools/build_v4_market_strategy_card_replay_expansion.py",
    "v2_football_quant/tools/build_v4_five_dimension_lite.py",
    "v2_football_quant/tools/check_v4_main_league_admission_guard.py",
    "v2_football_quant/tools/check_v4_market_strategy_research_cards.py",
    "v2_football_quant/tools/check_v4_market_strategy_card_replay_ledger.py",
    "v2_football_quant/tools/check_v4_market_strategy_card_replay_expansion.py",
    "v2_football_quant/tools/check_v4_five_dimension_lite.py",
    "v2_football_quant/tools/check_v4_price_field_persistence_pipeline.py",
    "v2_football_quant/tools/check_v4_price_source_selection_signal_inventory.py",
    "v2_football_quant/tools/run_v4_research_card_data_completeness_smoke.py",
    "v2_football_quant/tools/check_v4_research_card_data_completeness_smoke.py",
}
APPROVED_MANUAL_SOURCE_PREFIX_ALLOWLIST = (
    "v4-football/data/manual_sources/v4_football_data_csv/",
)


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = run_git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def staged_status() -> dict[str, str]:
    result = run_git(["diff", "--cached", "--name-status"])
    status: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status[parts[-1]] = parts[0]
    return status


def staged_diff() -> str:
    return run_git(["diff", "--cached"]).stdout


def approved_manual_source_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in APPROVED_MANUAL_SOURCE_PREFIX_ALLOWLIST)


def main() -> int:
    staged = staged_files()
    status = staged_status()
    approved_runtime_untrack = []
    approved_untrack_bad_status = []
    approved_untrack_missing_local = []
    for path in staged:
        if path in APPROVED_UNTRACK_ALLOWLIST:
            if status.get(path) != "D":
                approved_untrack_bad_status.append(path)
            elif not (ROOT / path).exists():
                approved_untrack_missing_local.append(path)
            else:
                approved_runtime_untrack.append(path)
    approved_tracked_runtime_ui_stage = []
    approved_tracked_runtime_ui_bad_status = []
    for path in staged:
        if path in APPROVED_TRACKED_RUNTIME_UI_STAGE_ALLOWLIST:
            if status.get(path) != "M":
                approved_tracked_runtime_ui_bad_status.append(path)
            else:
                approved_tracked_runtime_ui_stage.append(path)
    ordinary_staged = [
        path for path in staged
        if path not in set(approved_runtime_untrack)
        and path not in set(approved_tracked_runtime_ui_stage)
        and path not in APPROVED_V4_AUDIT_STAGE_ALLOWLIST
        and not approved_manual_source_path(path)
    ]
    runtime_staged = [path for path in ordinary_staged if RUNTIME_RE.search(path)]
    secret_path_staged = [path for path in ordinary_staged if SECRET_PATH_RE.search(path)]
    v4_staged = [path for path in ordinary_staged if V4_PATH_RE.search(path)]
    diff_text = staged_diff()
    secret_literal_hits = []
    for pattern in SECRET_PATTERNS:
        secret_literal_hits.extend(match.group(0)[:48] for match in pattern.finditer(diff_text))
    blockers = []
    if approved_untrack_bad_status:
        blockers.append("approved_untrack_bad_cached_status")
    if approved_untrack_missing_local:
        blockers.append("approved_untrack_missing_local_file")
    if approved_tracked_runtime_ui_bad_status:
        blockers.append("approved_tracked_runtime_ui_bad_status")
    if runtime_staged:
        blockers.append("runtime_cache_log_status_staged")
    if secret_path_staged or secret_literal_hits:
        blockers.append("secret_env_key_token_staged")
    if v4_staged:
        blockers.append("v4_file_staged")
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "staged_files": staged,
        "approved_runtime_untrack": approved_runtime_untrack,
        "approved_runtime_untrack_count": len(approved_runtime_untrack),
        "approved_untrack_bad_status": approved_untrack_bad_status,
        "approved_untrack_missing_local": approved_untrack_missing_local,
        "approved_tracked_runtime_ui_stage": approved_tracked_runtime_ui_stage,
        "approved_tracked_runtime_ui_bad_status": approved_tracked_runtime_ui_bad_status,
        "approved_v4_audit_stage": [path for path in staged if path in APPROVED_V4_AUDIT_STAGE_ALLOWLIST],
        "approved_manual_source_stage": [path for path in staged if approved_manual_source_path(path)],
        "runtime_staged": runtime_staged,
        "secret_path_staged": secret_path_staged,
        "secret_literal_hit_count": len(secret_literal_hits),
        "v4_staged": v4_staged,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
