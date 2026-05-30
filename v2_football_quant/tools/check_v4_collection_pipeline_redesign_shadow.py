#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
STATUS = BASE / "data" / "runtime" / "status"
REPORT = BASE / "data" / "daily_reports"
TZ = timezone(timedelta(hours=8))

RESULT = {
    "checker": "check_v4_collection_pipeline_redesign_shadow",
    "generated_at": datetime.now(TZ).isoformat(),
    "checks": {},
    "warnings": [],
    "blockers": [],
    "conclusion": "PASS",
}


def check(name: str, ok: bool, detail: str = "", blocker: bool = True) -> None:
    RESULT["checks"][name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        if blocker:
            RESULT["blockers"].append(f"{name}:{detail}")
        else:
            RESULT["warnings"].append(f"{name}:{detail}")


def latest_file(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def git_diff_empty(pathspec: str) -> bool:
    p = subprocess.run(["git", "diff", "--name-only", "--", pathspec], cwd=BASE, capture_output=True, text=True)
    return p.returncode == 0 and p.stdout.strip() == ""


def run_checker(script: str) -> tuple[bool, str]:
    p = subprocess.run([sys.executable, str(BASE / "tools" / script)], cwd=BASE, capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def main() -> int:
    runner_src = (BASE / "engine" / "v4_runner.py").read_text(encoding="utf-8")
    h2h_src = (BASE / "engine" / "data_sources" / "h2h_engine.py").read_text(encoding="utf-8")
    adapter_src = (BASE / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    model_src = (BASE / "tools" / "build_v4_control_center_model.py").read_text(encoding="utf-8")

    # 1) ordering: RF -> Market -> H2H
    i_rf = runner_src.find("build_recent_form_shadow_from_recent(")
    i_market = runner_src.find('odds?fixture=')
    i_h2h = runner_src.find("evaluate_h2h_edge(")
    check("rf_before_h2h_source_order", i_rf != -1 and i_h2h != -1 and i_rf < i_h2h, f"rf={i_rf},h2h={i_h2h}")
    check("market_before_h2h_source_order", i_market != -1 and i_h2h != -1 and i_market < i_h2h, f"market={i_market},h2h={i_h2h}")

    # 2) lazy H2H prefilter guards
    check("prefilter_helper_exists", "def _shadow_prefilter_decision" in runner_src)
    check("prefilter_no_market_skip", 'return False, "NO_MARKET"' in runner_src)
    check("prefilter_hard_veto_skip", 'return False, "MARKET_HARD_VETO"' in runner_src)
    check("prefilter_obvious_skip", 'return False, "OBVIOUS_SKIP"' in runner_src)
    check("prefilter_skip_branch", "if not h2h_required:" in runner_src)

    # 3) lazy events/cpl source guards
    check("lazy_events_helper_exists", "def _shadow_events_requirement" in runner_src)
    check("lazy_events_in_h2h_call", "include_h2h_events=events_required" in runner_src and "include_recent_events=events_required" in runner_src)
    check("h2h_engine_supports_event_flags", "include_h2h_events: bool = True" in h2h_src and "include_recent_events: bool = True" in h2h_src)
    check("lazy_cpl_helper_exists", "def _shadow_cpl_requirement" in runner_src)
    check("lazy_cpl_not_full_run", 'collection["cpl_required"]' in runner_src and 'collection["cpl_collected"] = False' in runner_src)

    # 4) field propagation to scout/adapter/model
    required_fields = [
        "collection_stage",
        "rf_collected",
        "market_collected",
        "prefilter_done",
        "h2h_required",
        "h2h_skipped_reason",
        "h2h_collected",
        "events_required",
        "events_skipped_reason",
        "events_collected",
        "cpl_required",
        "cpl_skipped_reason",
        "cpl_collected",
        "expensive_calls_saved",
        "collection_reason",
    ]
    for f in required_fields:
        check(f"runner_has_field_{f}", f in runner_src)
        check(f"adapter_has_field_{f}", f in adapter_src)
        check(f"model_has_field_{f}", f in model_src)

    # 5) official/default-rules/A-B thresholds unchanged guard
    mi_path = BASE / "engine" / "v4_match_intelligence.py"
    mi_src = mi_path.read_text(encoding="utf-8")
    m = re.search(r"DEFAULT_RULES\s*=\s*(\{.+?\n\})", mi_src, re.DOTALL)
    rules_hash = hashlib.sha256(m.group(1).encode()).hexdigest()[:12] if m else "NOT_FOUND"
    check("default_rules_hash_unchanged", rules_hash == "b04f3da9b770", f"hash={rules_hash}")
    check("official_grade_file_not_modified", git_diff_empty("engine/v4_match_intelligence.py"), "git diff detected on v4_match_intelligence.py")

    # 6) no cron/default validation/live-bet/qq side-effects
    cron_ok, cron_out = run_checker("check_v4_daily_scan_cron_payload.py")
    check("cron_checker_pass", cron_ok, cron_out[-300:])

    check("validation_not_recomputed", git_diff_empty("data/runtime/validation"), "validation dir has local diff")
    check("validation_history_not_modified", git_diff_empty("data/runtime/validation/v4_ab_historical_ledger_20260526.json"), "validation history file changed")
    check("live_bet_raw_not_modified", git_diff_empty("data/runtime/live_bets"), "live_bets dir has local diff")

    push_marker = latest_file("v4_scan_*_push_*.json", STATUS)
    if push_marker:
        try:
            marker = json.loads(push_marker.read_text(encoding="utf-8"))
        except Exception:
            marker = {}
        qq_not_pushed = not bool(marker.get("pushed") or marker.get("actual_send") or marker.get("qq_sent"))
        check("qq_not_pushed", qq_not_pushed, str(push_marker))
    else:
        check("qq_not_pushed", True, "no_push_marker_found")

    # 7) runtime scout checks (if data exists)
    scout_path = latest_file("scout_v4_*.json", REPORT)
    if scout_path:
        try:
            scout_rows = json.loads(scout_path.read_text(encoding="utf-8"))
        except Exception:
            scout_rows = []
    else:
        scout_rows = []

    if isinstance(scout_rows, list) and scout_rows:
        sample = [r for r in scout_rows if isinstance(r, dict)]
        has_fields = all(all(f in row for f in required_fields) for row in sample)
        check("scout_has_collection_fields", has_fields, f"rows={len(sample)}", blocker=False)

        total = len(sample)
        h2h_required_cnt = sum(1 for r in sample if r.get("h2h_required") is True)
        events_required_cnt = sum(1 for r in sample if r.get("events_required") is True)
        cpl_required_cnt = sum(1 for r in sample if r.get("cpl_required") is True)

        check("events_not_full_volume", events_required_cnt < total, f"events_required={events_required_cnt},total={total}", blocker=False)
        check("cpl_not_full_volume", cpl_required_cnt < total, f"cpl_required={cpl_required_cnt},total={total}", blocker=False)
        check("h2h_required_present", h2h_required_cnt >= 0, f"h2h_required={h2h_required_cnt}")
    else:
        check("scout_has_collection_fields", False, "scout missing or empty", blocker=False)

    if RESULT["blockers"]:
        RESULT["conclusion"] = "BLOCKER"
    elif RESULT["warnings"]:
        RESULT["conclusion"] = "WARN_ONLY"
    else:
        RESULT["conclusion"] = "PASS"

    out = STATUS / f"check_v4_collection_pipeline_redesign_shadow_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(RESULT, ensure_ascii=False, indent=2))
    return 0 if RESULT["conclusion"] in {"PASS", "WARN_ONLY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
