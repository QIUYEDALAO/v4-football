#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
STATUS = BASE / "data" / "runtime" / "status"
REPORT = BASE / "data" / "daily_reports"
UNIVERSE = BASE / "data" / "universe"
TZ = timezone(timedelta(hours=8))

RESULT = {
    "checker": "check_v4_collection_pipeline_plan_observe_only",
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


def latest(pattern: str, root: Path) -> Path | None:
    fs = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return fs[-1] if fs else None


def run_checker(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(BASE / "tools" / script)], cwd=BASE, capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    runner_src = (BASE / "engine" / "v4_runner.py").read_text(encoding="utf-8")
    adapter_src = (BASE / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    model_src = (BASE / "tools" / "build_v4_control_center_model.py").read_text(encoding="utf-8")

    required_plan_fields = [
        "collection_plan_mode",
        "collection_plan_observe_only",
        "planned_collection_stage",
        "planned_h2h_required",
        "planned_h2h_skipped_reason",
        "planned_events_required",
        "planned_events_skipped_reason",
        "planned_cpl_required",
        "planned_cpl_skipped_reason",
        "planned_expensive_calls_saved",
        "planned_collection_reason",
    ]
    required_actual_fields = [
        "actual_h2h_collected",
        "actual_events_collected",
        "actual_cpl_collected",
        "actual_collection_stage",
        "actual_collection_reason",
    ]

    for f in required_plan_fields + required_actual_fields:
        check(f"runner_has_{f}", f in runner_src)
        check(f"adapter_has_{f}", f in adapter_src)
        check(f"model_has_{f}", f in model_src)

    check("plan_mode_constant", '"collection_plan_mode": "OBSERVE_ONLY"' in runner_src)
    check("plan_observe_only_constant", '"collection_plan_observe_only": True' in runner_src)

    idx_h2h = runner_src.find("result = evaluate_h2h_edge(")
    idx_plan = runner_src.find("observe_plan = _build_observe_only_collection_plan(")
    check("actual_h2h_runs_before_plan_eval", idx_h2h != -1 and idx_plan != -1 and idx_h2h < idx_plan, f"h2h={idx_h2h},plan={idx_plan}")

    check("planned_fields_not_used_as_continue_guard", "if not observe_plan" not in runner_src and "if observe_plan" not in runner_src)
    check("legacy_events_path_kept", "run_heavy = (scan_mode == \"full\") or prelim_candidate" in runner_src)
    check("cpl_not_enabled_actual", "\"actual_cpl_collected\": False" in runner_src)

    acceptance = latest("v4_rf_shadow_grade_light_acceptance_*.json", BASE / "data" / "runtime" / "acceptance")
    acceptance_payload = _json(acceptance) if acceptance else {}
    light_mode = str((acceptance_payload or {}).get("acceptance_status") or "").upper() == "PASS"

    scout = latest("scout_v4_*.json", REPORT)
    universe = latest("fixtures_universe_*.jsonl", UNIVERSE)
    perf = latest("scan_perf_v4_*.json", REPORT)

    if scout is None or universe is None:
        check("runtime_artifacts_exist", False, "missing scout or universe")
    else:
        scout_rows = _json(scout)
        if not isinstance(scout_rows, list):
            scout_rows = []
        uni_rows = []
        for line in universe.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                uni_rows.append(json.loads(line))
            except Exception:
                continue

        check("scout_non_empty", len(scout_rows) > 0, f"scout_rows={len(scout_rows)}", blocker=not light_mode)

        if scout_rows:
            sample = [r for r in scout_rows if isinstance(r, dict)]
            for f in required_plan_fields + required_actual_fields:
                ok = all(f in r for r in sample)
                check(f"scout_has_{f}", ok, f"rows={len(sample)}")

            obs_mode_ok = all(str(r.get("collection_plan_mode")) == "OBSERVE_ONLY" for r in sample)
            obs_true_ok = all(bool(r.get("collection_plan_observe_only")) is True for r in sample)
            check("scout_plan_mode_observe_only", obs_mode_ok)
            check("scout_observe_only_true", obs_true_ok)

        planned_false = [r for r in uni_rows if isinstance(r, dict) and r.get("planned_h2h_required") is False]
        check("planned_h2h_false_exists", len(planned_false) > 0, f"count={len(planned_false)}", blocker=False)
        check(
            "planned_false_not_delete_all_scout",
            not (len(planned_false) > 0 and len(scout_rows) == 0),
            f"planned_false={len(planned_false)},scout={len(scout_rows)}",
            blocker=not light_mode,
        )

    if perf:
        pd = _json(perf) or {}
        check("scan_perf_present", True, perf.name)
        check("scouted_count_positive", int(pd.get("scouted_count") or 0) > 0, f"scouted_count={pd.get('scouted_count')}", blocker=False)

    ok, out = run_checker("check_v4_production_default_rules_guard.py")
    check("default_rules_guard_pass", ok, out[-300:])
    ok, out = run_checker("check_v4_daily_scan_cron_payload.py")
    check("cron_checker_pass", ok, out[-300:])

    p = subprocess.run(["git", "diff", "--name-only", "--", "data/runtime/validation", "data/runtime/live_bets"], cwd=BASE, capture_output=True, text=True)
    check("validation_livebet_no_diff", p.returncode == 0 and p.stdout.strip() == "", p.stdout.strip())

    marker = latest("v4_scan_*_push_*.json", STATUS)
    if marker:
        md = _json(marker) or {}
        qq_not_pushed = not bool(md.get("pushed") or md.get("actual_send") or md.get("qq_sent"))
        check("qq_not_pushed", qq_not_pushed, marker.name)

    p = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=BASE, capture_output=True, text=True)
    staged = [x.strip() for x in p.stdout.splitlines() if x.strip()]
    secret_hits = [x for x in staged if any(k in x.lower() for k in [".env", "secret", "token", "apikey", "api_key"])]
    check("no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))

    if RESULT["blockers"]:
        RESULT["conclusion"] = "BLOCKER"
    elif RESULT["warnings"]:
        RESULT["conclusion"] = "WARN_ONLY"
    else:
        RESULT["conclusion"] = "PASS"

    out_path = STATUS / f"check_v4_collection_pipeline_plan_observe_only_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(RESULT, ensure_ascii=False, indent=2))
    return 0 if RESULT["conclusion"] in {"PASS", "WARN_ONLY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
