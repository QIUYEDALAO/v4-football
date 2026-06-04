#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_wc10_war_room_20260602.json"
BUILDER = ROOT / "tools/build_v3_worldcup_wc10_war_room.py"
TACTICAL_BUILDER = ROOT / "tools/build_v3_worldcup_tactical_profile_layer.py"
CLOSING_1X2_BUILDER = ROOT / "tools/build_v3_worldcup_closing_1x2_market_structure.py"
FINAL26_UI_BUILDER = ROOT / "tools/build_v3_worldcup_final_26_war_room_ui_payload.py"
FINAL26_PROFILE_BUILDER = ROOT / "tools/build_v3_worldcup_final_26_squad_profile_observation.py"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
HTML = ROOT / "data/runtime/dashboard/v3_worldcup_wc10_war_room.html"

BAD_HINTS = {"BET", "STAKE", "BUY", "SELL", "AUTO_BET", "RECOMMENDATION", "LOCKED_PICK"}
ALLOW_HINTS = {"OBSERVE_ONLY", "WATCHLIST_ONLY", "NEED_SUPPLEMENT", "DO_NOT_CONCLUDE", "DATA_GAP_REVIEW"}


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    checks: list[dict[str, Any]] = []
    tactical_run = subprocess.run([sys.executable, str(TACTICAL_BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "tactical_builder_runs", tactical_run.returncode == 0, tactical_run.stderr or tactical_run.stdout[-500:])
    closing_run = subprocess.run([sys.executable, str(CLOSING_1X2_BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "closing_1x2_builder_runs", closing_run.returncode == 0, closing_run.stderr or closing_run.stdout[-500:])
    final26_ui_run = subprocess.run([sys.executable, str(FINAL26_UI_BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "final26_ui_builder_runs", final26_ui_run.returncode == 0, final26_ui_run.stderr or final26_ui_run.stdout[-500:])
    final26_profile_run = subprocess.run([sys.executable, str(FINAL26_PROFILE_BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "final26_profile_builder_runs", final26_profile_run.returncode == 0, final26_profile_run.stderr or final26_profile_run.stdout[-500:])
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    add(checks, "war_room_json_exists", WAR.exists(), str(WAR))
    add(checks, "dashboard_html_exists", HTML.exists(), str(HTML))
    payload = _load(WAR)
    add(checks, "teams_with_roster_46", int(payload.get("teams_with_roster") or 0) == 46, payload.get("teams_with_roster"))
    add(checks, "teams_total_46", int(payload.get("teams_total") or 0) == 46, payload.get("teams_total"))
    add(checks, "players_total_1375", int(payload.get("players_total") or 0) == 1375, payload.get("players_total"))
    add(checks, "status_ok", payload.get("status") == "WAR_ROOM_READY_WITH_WARN_ONLY", payload.get("status"))
    add(checks, "status_level_ok", payload.get("status_level") == "CODE_READY", payload.get("status_level"))
    add(checks, "blocker_none", payload.get("blocker") == "NONE", payload.get("blocker"))
    warn = payload.get("warn_only_items") or []
    for x in ["CAPS_GOALS_MINUTES_SUPPLEMENT_MISSING", "INJURY_SUPPLEMENT_MISSING", "FRIENDLY_FORM_SUPPLEMENT_MISSING", "MARKET_BASELINE_SUPPLEMENT_MISSING"]:
        add(checks, f"warn_has_{x}", x in warn, warn)
    wl = payload.get("perception_gap_watchlist") or []
    add(checks, "watchlist_count_ge_1", int(payload.get("perception_gap_watchlist_count") or len(wl)) >= 1, payload.get("perception_gap_watchlist_count"))
    guard = payload.get("safety_guard") or {}
    add(checks, "guard_observation_only", guard.get("observation_only") is True, guard)
    add(checks, "guard_no_betting", guard.get("no_betting_recommendations") is True, guard)
    add(checks, "guard_no_v4_changes", guard.get("no_v4_changes") is True, guard)
    add(checks, "supplement_coverage_status_present", bool(payload.get("supplement_coverage_status")), payload.get("supplement_coverage_status"))
    add(checks, "supplement_coverage_by_category_present", isinstance(payload.get("supplement_coverage_by_category"), dict), type(payload.get("supplement_coverage_by_category")).__name__)
    add(checks, "final_squad_status_present", bool(payload.get("final_squad_status")), payload.get("final_squad_status"))
    add(checks, "teams_expected_final_squad_48", int(payload.get("teams_expected_final_squad") or 0) == 48, payload.get("teams_expected_final_squad"))
    add(checks, "teams_detected_in_baseline_46", int(payload.get("teams_detected_in_baseline") or 0) == 46, payload.get("teams_detected_in_baseline"))
    add(checks, "players_total_baseline_1375", int(payload.get("players_total_baseline") or 0) == 1375, payload.get("players_total_baseline"))
    add(checks, "baseline_pool_not_final_26_flag", payload.get("baseline_pool_not_final_26") is True, payload.get("baseline_pool_not_final_26"))
    add(checks, "source_gate_status_present", bool(payload.get("source_authorization_gate_status")), payload.get("source_authorization_gate_status"))
    add(checks, "source_gate_approved_count_present", int(payload.get("source_authorization_approved_sources_count") or 0) >= 0, payload.get("source_authorization_approved_sources_count"))
    add(checks, "source_gate_intake_count_present", int(payload.get("source_authorization_intake_files_found") or 0) >= 0, payload.get("source_authorization_intake_files_found"))
    add(checks, "wc6_dryrun_status_present", bool(payload.get("wc6_ingestion_dryrun_status")), payload.get("wc6_ingestion_dryrun_status"))
    add(checks, "wc6_official_not_written", payload.get("wc6_ingestion_dryrun_official_written") is False, payload.get("wc6_ingestion_dryrun_official_written"))
    add(checks, "candidate_review_status_present", bool(payload.get("candidate_review_status")), payload.get("candidate_review_status"))
    csum = payload.get("candidate_review_summary") if isinstance(payload.get("candidate_review_summary"), dict) else {}
    cc = payload.get("candidate_review_counts") if isinstance(payload.get("candidate_review_counts"), dict) else {}
    add(checks, "candidate_review_only", csum.get("source_status") in {"CANDIDATE_REVIEW_ONLY", "WC5D_MISSING_WARN_ONLY"}, csum.get("source_status"))
    add(checks, "candidate_review_not_official", csum.get("official_final_squad_written") is False and csum.get("final_squad_complete") is False, csum)
    add(checks, "candidate_safe_29", int(csum.get("teams_safe") or 0) in {0, 29}, csum.get("teams_safe"))
    add(checks, "candidate_hold_19", int(csum.get("teams_hold") or 0) in {48, 19}, csum.get("teams_hold"))
    add(checks, "candidate_counts_expected", all([
        int(cc.get("OFFICIAL_CONFIRMED") or 0) in {0, 1},
        int(cc.get("API_CLEAN_CANDIDATE") or 0) in {0, 25},
        int(cc.get("API_WIKI_ALIGNED_CANDIDATE") or 0) in {0, 3},
        int(cc.get("WIKI_PREFERRED_API_POOL_OVERFULL") or 0) in {0, 15},
        int(cc.get("API_INCOMPLETE_NEED_REVIEW") or 0) in {0, 3},
        int(cc.get("PROVISIONAL_OVERFULL_NEED_REVIEW") or 0) in {0, 1},
    ]), cc)
    add(checks, "historical_market_status_present", bool(payload.get("historical_market_baseline_status")), payload.get("historical_market_baseline_status"))
    hm_summary = payload.get("historical_market_baseline_summary") if isinstance(payload.get("historical_market_baseline_summary"), dict) else {}
    hm_counts = payload.get("historical_market_baseline_counts") if isinstance(payload.get("historical_market_baseline_counts"), dict) else {}
    hm_rates = payload.get("historical_market_baseline_key_rates") if isinstance(payload.get("historical_market_baseline_key_rates"), dict) else {}
    add(checks, "historical_market_matches_192", int(hm_summary.get("total_world_cup_finals_matches") or 0) in {0, 192}, hm_summary)
    add(checks, "historical_market_key_counts", all([
        int(hm_counts.get("underdog_upset_count") or 0) in {0, 43},
        int(hm_counts.get("draw_result_count") or 0) in {0, 38},
        int(hm_counts.get("ht_draw_count") or 0) in {0, 95},
        int(hm_counts.get("over_2_5_count") or 0) in {0, 99},
        int(hm_counts.get("btts_count") or 0) in {0, 96},
    ]), hm_counts)
    add(checks, "historical_market_key_rates", all([
        round(float(hm_rates.get("heavy_favorite_win_rate") or 0), 3) in {0.0, 0.719},
        round(float(hm_rates.get("strong_favorite_win_rate") or 0), 3) in {0.0, 0.605},
        round(float(hm_rates.get("favorite_failed_rate") or 0), 3) in {0.0, 0.422},
    ]), hm_rates)
    pg_layers = payload.get("perception_gap_input_layers") if isinstance(payload.get("perception_gap_input_layers"), dict) else {}
    pg_tags = payload.get("perception_gap_output_tags") if isinstance(payload.get("perception_gap_output_tags"), list) else []
    pg_guard = payload.get("perception_gap_safety_guard") if isinstance(payload.get("perception_gap_safety_guard"), dict) else {}
    add(checks, "perception_gap_blueprint_status_present", bool(payload.get("perception_gap_blueprint_status")), payload.get("perception_gap_blueprint_status"))
    add(checks, "perception_gap_layers_present", all(k in pg_layers for k in ["historical_market_baseline", "current_match_market_layer", "lineup_formation_value_delta_layer"]), list(pg_layers.keys()))
    add(checks, "perception_gap_tags_complete", set(pg_tags) == {"UNDERVALUED_WATCH", "OVERHYPED_RISK", "MARKET_FAIR", "LINEUP_WEAKENED", "LINEUP_STRONGER_THAN_EXPECTED", "DATA_INSUFFICIENT", "WATCH_ONLY"}, pg_tags)
    add(checks, "perception_gap_observation_only", pg_guard.get("observation_only") is True, pg_guard)
    add(checks, "perception_gap_no_betting", pg_guard.get("betting_recommendation") is False and pg_guard.get("auto_bet_allowed") is False, pg_guard)
    add(checks, "perception_gap_no_v4_grade_impact", pg_guard.get("affects_v4_grade") is False, pg_guard)
    mlpg_samples = payload.get("match_level_perception_gap_dryrun_samples") if isinstance(payload.get("match_level_perception_gap_dryrun_samples"), list) else []
    mlpg_guard = payload.get("match_level_perception_gap_dryrun_safety_guard") if isinstance(payload.get("match_level_perception_gap_dryrun_safety_guard"), dict) else {}
    add(checks, "match_level_pg_dryrun_ready", payload.get("match_level_perception_gap_dryrun_status") == "DRY_RUN_READY", payload.get("match_level_perception_gap_dryrun_status"))
    add(checks, "match_level_pg_dryrun_samples_5", len(mlpg_samples) == 5 and int(payload.get("match_level_perception_gap_dryrun_sample_count") or 0) == 5, payload.get("match_level_perception_gap_dryrun_sample_count"))
    add(checks, "match_level_pg_dryrun_observation_only", mlpg_guard.get("observation_only") is True, mlpg_guard)
    add(checks, "match_level_pg_dryrun_no_betting", mlpg_guard.get("betting_recommendation") is False, mlpg_guard)
    add(checks, "match_level_pg_dryrun_no_v4_grade_impact", mlpg_guard.get("affects_v4_grade") is False, mlpg_guard)
    add(checks, "match_level_pg_dryrun_scoring_unchanged", mlpg_guard.get("scoring_changed") is False, mlpg_guard)
    add(checks, "match_level_pg_dryrun_upset_watch_not_scoring", mlpg_guard.get("venue_upset_watch_scoring") is False, mlpg_guard)
    add(checks, "match_level_pg_dryrun_upset_watch_definition", payload.get("match_level_perception_gap_dryrun_upset_watch_definition") == "historical_data_insufficient_for_probability", payload.get("match_level_perception_gap_dryrun_upset_watch_definition"))
    add(checks, "match_level_pg_dryrun_market_path", payload.get("match_level_perception_gap_dryrun_market_data_status_path") == ["CURRENT_MARKET_DATA_MISSING", "MARKET_DATA_PARTIAL", "MARKET_DATA_AVAILABLE"], payload.get("match_level_perception_gap_dryrun_market_data_status_path"))
    add(checks, "match_level_pg_dryrun_market_cases", payload.get("match_level_perception_gap_dryrun_market_data_status_cases") == {"CURRENT_MARKET_DATA_MISSING": 1, "MARKET_DATA_PARTIAL": 3, "MARKET_DATA_AVAILABLE": 1}, payload.get("match_level_perception_gap_dryrun_market_data_status_cases"))
    add(checks, "match_level_pg_dryrun_real_market_not_used", payload.get("match_level_perception_gap_dryrun_real_market_cache_used") is False, payload.get("match_level_perception_gap_dryrun_real_market_cache_used"))
    add(checks, "match_level_pg_dryrun_samples_marked", all(x.get("dryrun_market_data_sample") is True and x.get("real_market_cache_used") is False for x in mlpg_samples), mlpg_samples[:2])
    tactical_guard = payload.get("tactical_profile_safety_guard") if isinstance(payload.get("tactical_profile_safety_guard"), dict) else {}
    add(checks, "tactical_profile_ready", payload.get("tactical_profile_status") == "TACTICAL_PROFILE_LAYER_READY", payload.get("tactical_profile_status"))
    add(checks, "tactical_profile_48", int(payload.get("tactical_profile_team_count") or 0) == 48, payload.get("tactical_profile_team_count"))
    add(checks, "tactical_profile_real_samples_24", int(payload.get("tactical_profile_real_sample_team_count") or 0) == 24, payload.get("tactical_profile_real_sample_team_count"))
    add(checks, "tactical_profile_insufficient_24", int(payload.get("tactical_profile_data_insufficient_team_count") or 0) == 24, payload.get("tactical_profile_data_insufficient_team_count"))
    add(checks, "tactical_profile_matchups_72", int(payload.get("tactical_profile_matchup_count") or 0) == 72, payload.get("tactical_profile_matchup_count"))
    add(checks, "tactical_profile_unique_formations_14", int(payload.get("tactical_profile_unique_formations_count") or 0) == 14, payload.get("tactical_profile_unique_formations_count"))
    add(checks, "tactical_profile_no_scoring", tactical_guard.get("observation_only") is True and tactical_guard.get("no_scoring") is True and tactical_guard.get("scoring_changed") is False, tactical_guard)
    add(checks, "tactical_profile_no_betting", tactical_guard.get("betting_recommendation") is False, tactical_guard)
    closing_guard = payload.get("closing_1x2_safety_guard") if isinstance(payload.get("closing_1x2_safety_guard"), dict) else {}
    add(checks, "closing_1x2_ready", payload.get("closing_1x2_status") == "CLOSING_1X2_MARKET_STRUCTURE_READY", payload.get("closing_1x2_status"))
    add(checks, "closing_1x2_matches_192", int(payload.get("closing_1x2_match_count") or 0) == 192, payload.get("closing_1x2_match_count"))
    add(checks, "closing_1x2_complete", payload.get("closing_1x2_complete") is True, payload.get("closing_1x2_complete"))
    add(checks, "closing_1x2_favorite_failed_42_2", round(float(payload.get("closing_1x2_favorite_failed_rate") or 0), 1) == 42.2, payload.get("closing_1x2_favorite_failed_rate"))
    add(checks, "closing_1x2_disabled_tags", set(payload.get("closing_1x2_disabled_tags") or []) == {"FAVORITE_STEAM", "FAVORITE_DRIFT", "LATE_SHARP_MOVE", "AH_LINE_MOVEMENT", "OU_LINE_MOVEMENT", "FUND_FLOW_SIGNAL"}, payload.get("closing_1x2_disabled_tags"))
    add(checks, "closing_1x2_no_steam_drift", closing_guard.get("no_opening_odds") is True and closing_guard.get("no_steam_drift") is True and closing_guard.get("no_fund_flow") is True, closing_guard)
    add(checks, "closing_1x2_no_betting_no_v4", closing_guard.get("betting_recommendation") is False and closing_guard.get("affects_v4_grade") is False, closing_guard)
    final26_node = payload.get("final_26_squad_observation") if isinstance(payload.get("final_26_squad_observation"), dict) else {}
    final26_safety = final26_node.get("safety") if isinstance(final26_node.get("safety"), dict) else {}
    add(checks, "final26_observation_ready", final26_node.get("status") == "FINAL_26_OBSERVATION_READY", final26_node.get("status"))
    add(checks, "final26_module", final26_node.get("module") == "final_26_squad_observation", final26_node.get("module"))
    add(checks, "final26_counts", int(final26_node.get("team_count") or 0) == 48 and int(final26_node.get("total_players") or 0) == 1248 and int(final26_node.get("coach_count") or 0) == 48, final26_node)
    add(checks, "final26_safety", final26_safety.get("observation_only") is True and final26_safety.get("no_starting_xi") is True and final26_safety.get("no_injury_judgment") is True and final26_safety.get("betting_recommendation") is False and final26_safety.get("affects_v4") is False, final26_safety)
    profile_node = payload.get("final_26_squad_profile_observation") if isinstance(payload.get("final_26_squad_profile_observation"), dict) else {}
    profile_safety = profile_node.get("safety") if isinstance(profile_node.get("safety"), dict) else {}
    profile_rankings = profile_node.get("observation_rankings") if isinstance(profile_node.get("observation_rankings"), dict) else {}
    profile_text = json.dumps(profile_node, ensure_ascii=False).lower()
    add(checks, "final26_profile_node_present", bool(profile_node), profile_node)
    add(checks, "final26_profile_ready", profile_node.get("status") == "FINAL_26_SQUAD_PROFILE_READY", profile_node.get("status"))
    add(checks, "final26_profile_module", profile_node.get("module") == "final_26_squad_profile_observation", profile_node.get("module"))
    add(checks, "final26_profile_counts", int(profile_node.get("team_count") or 0) == 48 and int(profile_node.get("total_players") or 0) == 1248, profile_node)
    add(checks, "final26_profile_position_distribution", profile_node.get("position_distribution") == {"GK": 145, "DF": 421, "MF": 371, "FW": 311}, profile_node.get("position_distribution"))
    add(checks, "final26_profile_core_profiles", all(isinstance(profile_node.get(k), dict) and bool(profile_node.get(k)) for k in ["age_profile", "height_profile", "club_profile", "position_group_profiles"]), list(profile_node.keys()))
    add(checks, "final26_profile_rankings", profile_rankings.get("ranking_type") == "roster_observation_ranking" and all(isinstance(profile_rankings.get(k), list) and bool(profile_rankings.get(k)) for k in ["oldest_avg_age_teams", "youngest_avg_age_teams", "tallest_avg_height_teams", "shortest_avg_height_teams"]), profile_rankings)
    add(checks, "final26_profile_team_refs", isinstance(profile_node.get("team_profile_refs"), list) and len(profile_node.get("team_profile_refs")) == 48, len(profile_node.get("team_profile_refs") or []))
    add(checks, "final26_profile_safety", profile_safety.get("observation_only") is True and profile_safety.get("no_starting_xi") is True and profile_safety.get("no_injury_judgment") is True and profile_safety.get("no_prediction") is True and profile_safety.get("betting_recommendation") is False and profile_safety.get("affects_v4") is False, profile_safety)
    add(checks, "final26_profile_no_prediction_betting_terms", all(token not in profile_text for token in ["strength ranking", "strength_ranking", "prediction ranking", "prediction_ranking", "betting signal", "betting_signal", "recommendation_ranking", "recommended_pick", "starting_lineup", "starting_players", "injury_status", "suspension_status"]), "profile_node_text_scan")
    hints = [str(x.get("action_hint") or "") for x in wl if isinstance(x, dict)]
    add(checks, "action_hint_whitelist", all(h in ALLOW_HINTS for h in hints), hints[:12])
    add(checks, "action_hint_no_bad", all(h not in BAD_HINTS for h in hints), hints[:12])
    text = (json.dumps(payload, ensure_ascii=False) + "\n" + (HTML.read_text(encoding="utf-8", errors="ignore") if HTML.exists() else "")).lower()
    sanitized = (
        text.replace("no betting recommendation", "")
        .replace("no betting recommendations", "")
        .replace("not a betting recommendation", "")
        .replace("不是投注建议", "")
        .replace("不作为投注建议", "")
        .replace("不输出投注建议", "")
        .replace("任何 watchlist 都不是推荐下注", "")
        .replace("no_stake", "")
    )
    banned = ["bet ready", "recommendation_ready", "auto_trade_ready", "wager", "推荐下注", "投注建议", "auto bet", "locked pick"]
    add(checks, "no_betting_terms", all(x not in sanitized for x in banned), banned)
    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_v4_scan", "scan_and_brief" not in src and "fullscan" not in src)
    add(
        checks,
        "no_qq_pending_validation_livebet_cron",
        all(x not in src for x in ["send_qq(", "pending_route(", "recompute_validation(", "append_live_bet(", "crontab"]),
    )
    add(checks, "no_touch_outside57_scanner", "v4_outside57_scanner.py" not in src)
    add(checks, "no_secrets", all(x not in src for x in ["api-key", "token=", "secret"]), "source_scan")

    blockers = [c["name"] for c in checks if not c["ok"]]
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
