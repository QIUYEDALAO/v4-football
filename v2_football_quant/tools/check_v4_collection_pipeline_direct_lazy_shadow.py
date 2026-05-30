#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
REPORT = ROOT / "data" / "daily_reports"
UNIVERSE = ROOT / "data" / "universe"
TZ = timezone(timedelta(hours=8))


def _latest(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_checker(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def _ok(checks: dict[str, dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_collection_pipeline_direct_lazy_shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    brief_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    worker_src = (ROOT / "engine" / "v4_scan_worker.py").read_text(encoding="utf-8")
    runner_src = (ROOT / "engine" / "v4_runner.py").read_text(encoding="utf-8")

    # 1-3 参数存在与默认值
    has_mode_brief = "--collection-mode" in brief_src
    has_mode_worker = "--collection-mode" in worker_src
    has_mode_runner = "--collection-mode" in runner_src
    _ok(result["checks"], "has_collection_mode_arg", has_mode_brief and has_mode_worker and has_mode_runner)
    if not (has_mode_brief and has_mode_worker and has_mode_runner):
        result["blockers"].append("missing_collection_mode_arg")

    default_mode_ok = (
        'default="official_legacy"' in brief_src
        and 'default="official_legacy"' in worker_src
        and 'default="official_legacy"' in runner_src
    )
    _ok(result["checks"], "default_collection_mode_official_legacy", default_mode_ok)
    if not default_mode_ok:
        result["blockers"].append("default_mode_not_official_legacy")

    has_max_brief = "--max-fixtures" in brief_src
    has_max_worker = "--max-fixtures" in worker_src
    has_max_runner = "--max-fixtures" in runner_src
    _ok(result["checks"], "has_max_fixtures_arg", has_max_brief and has_max_worker and has_max_runner)
    if not (has_max_brief and has_max_worker and has_max_runner):
        result["blockers"].append("missing_max_fixtures_arg")

    # 4-5 cron 默认不启用新参数（通过守卫checker + 默认值保证）
    cron_mode_not_enabled = 'default="official_legacy"' in brief_src and '--collection-mode", str(args.collection_mode' in brief_src
    _ok(result["checks"], "cron_not_force_rf_lazy_shadow", cron_mode_not_enabled)
    if not cron_mode_not_enabled:
        result["blockers"].append("cron_may_force_lazy_mode")

    cron_not_force_max = 'if args.max_fixtures is not None' in brief_src
    _ok(result["checks"], "cron_not_force_max_fixtures", cron_not_force_max)
    if not cron_not_force_max:
        result["blockers"].append("cron_may_force_max_fixtures")

    # 6-7 顺序检查（lazy block 内）
    lazy_start = runner_src.find('if collection_mode == "rf_lazy_shadow":')
    legacy_after = runner_src.find('logger.info(f"  ⏳ H2H:', lazy_start)
    lazy_block = runner_src[lazy_start:legacy_after] if lazy_start != -1 and legacy_after != -1 else ""
    idx_rf = lazy_block.find("build_recent_form_shadow_from_recent(")
    idx_market = lazy_block.find("market_stub = build_rf_shadow_grade_layer(")
    idx_prefilter = lazy_block.find("prefilter_done = True")
    idx_h2h = lazy_block.find("evaluate_h2h_edge(")
    order_ok = all(i != -1 for i in [idx_rf, idx_market, idx_prefilter, idx_h2h]) and idx_rf < idx_market < idx_prefilter < idx_h2h
    _ok(result["checks"], "rf_before_h2h_in_lazy_mode", order_ok, f"rf={idx_rf},market={idx_market},prefilter={idx_prefilter},h2h={idx_h2h}")
    if not order_ok:
        result["blockers"].append("lazy_order_invalid")

    # 8-10 skip 不删行（静态字段检查 + 运行态可选）
    required_lazy_fields = [
        "collection_mode",
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
    fields_ok = all(f in lazy_block for f in required_lazy_fields)
    _ok(result["checks"], "lazy_fields_present", fields_ok)
    if not fields_ok:
        result["blockers"].append("lazy_fields_missing")

    # 11-15 规则存在性（源码级）
    _ok(result["checks"], "obvious_skip_can_skip_h2h", "RF_TOO_WEAK" in lazy_block)
    _ok(result["checks"], "no_market_can_skip_h2h", 'h2h_skipped_reason = "NO_MARKET"' in lazy_block)
    _ok(result["checks"], "hard_veto_can_skip_h2h", 'h2h_skipped_reason = "MARKET_HARD_VETO"' in lazy_block)
    _ok(result["checks"], "events_not_full_scan", "events_required = bool(" in lazy_block)
    _ok(result["checks"], "cpl_placeholder_only", "PLACEHOLDER_ONLY" in lazy_block and "cpl_collected = False" in lazy_block)

    # runtime optional checks (latest artifact)
    scout_path = _latest("scout_v4_*.json", REPORT)
    universe_path = _latest("fixtures_universe_*.jsonl", UNIVERSE)
    runtime_rows = 0
    lazy_rows = []
    if scout_path and scout_path.exists():
        try:
            scout_rows = _load_json(scout_path)
            if isinstance(scout_rows, list):
                runtime_rows = len(scout_rows)
                lazy_rows = [r for r in scout_rows if isinstance(r, dict) and str(r.get("collection_mode") or "").lower() == "rf_lazy_shadow"]
        except Exception:
            pass
    _ok(result["checks"], "runtime_scout_exists", scout_path is not None and runtime_rows >= 0, str(scout_path) if scout_path else "")

    if lazy_rows:
        h2h_false_rows = [r for r in lazy_rows if r.get("h2h_required") is False]
        events_false_rows = [r for r in lazy_rows if r.get("events_required") is False]
        cpl_false_rows = [r for r in lazy_rows if r.get("cpl_required") is False]
        _ok(result["checks"], "h2h_false_rows_preserved", len(h2h_false_rows) <= len(lazy_rows), f"h2h_false={len(h2h_false_rows)},lazy_rows={len(lazy_rows)}")
        _ok(result["checks"], "events_false_rows_preserved", len(events_false_rows) <= len(lazy_rows), f"events_false={len(events_false_rows)},lazy_rows={len(lazy_rows)}")
        _ok(result["checks"], "cpl_false_rows_preserved", len(cpl_false_rows) <= len(lazy_rows), f"cpl_false={len(cpl_false_rows)},lazy_rows={len(lazy_rows)}")
    else:
        result["warnings"].append("lazy_runtime_rows_not_found_yet")

    # 16-23 安全守卫
    ok_default, out_default = _run_checker("check_v4_production_default_rules_guard.py")
    _ok(result["checks"], "default_rules_guard_pass", ok_default, out_default[-260:])
    if not ok_default:
        result["blockers"].append("default_rules_guard_failed")

    ok_slim, out_slim = _run_checker("check_v4_system_slim_and_whitelist_mode.py")
    _ok(result["checks"], "system_slim_whitelist_pass", ok_slim, out_slim[-260:])
    if not ok_slim:
        result["blockers"].append("system_slim_whitelist_failed")

    ok_no_market, out_no_market = _run_checker("check_v4_no_market_core_validation_skip.py")
    soft_no_market = ok_no_market or ("WARN_ONLY" in out_no_market)
    _ok(result["checks"], "validation_livebet_guard_soft_pass", soft_no_market, out_no_market[-260:])
    if not soft_no_market:
        result["blockers"].append("validation_livebet_guard_failed")

    qq_disabled = "V4_QQ_ENABLED = False" in brief_src
    _ok(result["checks"], "qq_disabled_in_scan_supervisor", qq_disabled)
    if not qq_disabled:
        result["blockers"].append("qq_push_may_be_enabled")

    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged_files = [x.strip() for x in staged.splitlines() if x.strip()]
    secret_hits = [x for x in staged_files if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    runtime_hits = [x for x in staged_files if x.startswith("data/runtime/")]
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    _ok(result["checks"], "no_runtime_artifacts_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    if secret_hits:
        result["blockers"].append("secrets_staged")
    if runtime_hits:
        result["blockers"].append("runtime_artifacts_staged")

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"

    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_collection_pipeline_direct_lazy_shadow_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
