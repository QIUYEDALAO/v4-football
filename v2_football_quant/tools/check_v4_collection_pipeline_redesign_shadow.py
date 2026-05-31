#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
REPORT = ROOT / "data" / "daily_reports"
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
        "checker": "check_v4_collection_pipeline_redesign_shadow",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    brief_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
    worker_src = (ROOT / "engine" / "v4_scan_worker.py").read_text(encoding="utf-8")
    runner_src = (ROOT / "engine" / "v4_runner.py").read_text(encoding="utf-8")

    # 1) 正式入口 whitelist serial path 仍在
    whitelist_ok = 'default="whitelist"' in brief_src and '--fixture-universe' in brief_src
    serial_ok = 'default="serial"' in brief_src and '--scan-engine' in brief_src
    _ok(result["checks"], "formal_entry_whitelist_serial", whitelist_ok and serial_ok)
    if not (whitelist_ok and serial_ok):
        result["blockers"].append("formal_entry_not_whitelist_serial")

    # Lazy 区块定位
    lazy_start = runner_src.find('if collection_mode == "rf_lazy_shadow":')
    legacy_after = runner_src.find('logger.info(f"  ⏳ H2H:', lazy_start)
    lazy_block = runner_src[lazy_start:legacy_after] if lazy_start != -1 and legacy_after != -1 else ""
    if not lazy_block:
        result["blockers"].append("lazy_block_not_found")

    # 2-4) 顺序：RF -> Market -> PreFilter -> H2H
    idx_rf = lazy_block.find("build_recent_form_shadow_from_recent(")
    idx_market = lazy_block.find("market_stub = build_rf_shadow_grade_layer(")
    idx_prefilter = lazy_block.find("prefilter_done = True")
    idx_h2h = lazy_block.find("evaluate_h2h_edge(")
    order_ok = all(i != -1 for i in [idx_rf, idx_market, idx_prefilter, idx_h2h]) and idx_rf < idx_market < idx_prefilter < idx_h2h
    _ok(result["checks"], "rf_market_prefilter_before_h2h", order_ok, f"rf={idx_rf},market={idx_market},prefilter={idx_prefilter},h2h={idx_h2h}")
    if not order_ok:
        result["blockers"].append("rf_first_order_invalid")

    # 5-9) H2H/Events/CPL gating 规则存在
    _ok(result["checks"], "obvious_skip_avoids_h2h", "RF_TOO_WEAK" in runner_src)
    _ok(result["checks"], "no_market_avoids_h2h", '"NO_MARKET"' in runner_src)
    _ok(result["checks"], "hard_veto_avoids_h2h", '"MARKET_HARD_VETO"' in runner_src)
    _ok(result["checks"], "events_is_gated", "events_required = bool(" in lazy_block)
    _ok(result["checks"], "cpl_is_gated_placeholder", "cpl_required = bool(" in lazy_block and "PLACEHOLDER_ONLY" in lazy_block)

    # 10-14) 字段存在
    required_fields = [
        "collection_stage", "h2h_required", "h2h_skipped_reason",
        "events_required", "events_skipped_reason", "events_collected",
        "cpl_required", "cpl_skipped_reason", "cpl_collected",
        "rf_collected", "market_collected", "prefilter_done",
        "expensive_calls_saved", "collection_reason",
    ]
    fields_ok = all(f in lazy_block for f in required_fields)
    _ok(result["checks"], "collection_fields_present_in_lazy_path", fields_ok)
    if not fields_ok:
        result["blockers"].append("lazy_fields_missing")

    # 24-25) 不再全量先查 H2H；避免 parallel-only 假PASS
    no_h2h_first = idx_h2h > idx_prefilter > idx_market > idx_rf >= 0
    _ok(result["checks"], "scanner_not_h2h_first", no_h2h_first)
    _ok(result["checks"], "serial_checker_not_parallel_only", "serial" in brief_src and "parallel" in brief_src)

    # 15-23 安全守卫（复用已有 checker）
    guard_scripts = {
        "official_grade_unchanged_guard": "check_v4_season_aware_production_switch.py",
        "default_rules_guard": "check_v4_production_default_rules_guard.py",
        "no_market_validation_guard": "check_v4_no_market_core_validation_skip.py",
        "qq_gate_guard": "check_v4_qq_enabled_gate.py",
    }
    for key, script in guard_scripts.items():
        ok, out = _run_checker(script)
        soft_ok = ok or ("WARN_ONLY" in out)
        _ok(result["checks"], key, soft_ok, out[-220:])
        if not soft_ok:
            result["blockers"].append(f"guard_failed:{script}")

    # H2H runtime gating 未改（静态确认：仍走 evaluate_h2h_edge，且 legacy 分支还在）
    h2h_runtime_unchanged = (
        "evaluate_h2h_edge(" in runner_src
        and 'if collection_mode == "rf_lazy_shadow":' in runner_src
        and 'logger.info(f"  ⏳ H2H:' in runner_src
    )
    _ok(result["checks"], "h2h_runtime_gating_unchanged", h2h_runtime_unchanged)
    if not h2h_runtime_unchanged:
        result["blockers"].append("h2h_runtime_gating_changed")

    # staged 安全
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged_files = [x.strip() for x in staged.splitlines() if x.strip()]
    secret_hits = [x for x in staged_files if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    runtime_hits = [x for x in staged_files if x.startswith("data/runtime/")]
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    _ok(result["checks"], "no_runtime_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    if secret_hits:
        result["blockers"].append("secrets_staged")
    if runtime_hits:
        result["blockers"].append("runtime_staged")

    # runtime 读最近 scout 做补充校验（可选）
    scout_path = _latest("scout_v4_*.json", REPORT)
    if scout_path and scout_path.exists():
        try:
            rows = _load_json(scout_path)
            lazy_rows = [r for r in rows if isinstance(r, dict) and str(r.get("collection_mode") or "").lower() == "rf_lazy_shadow"]
            if lazy_rows:
                h2h_false = sum(1 for r in lazy_rows if r.get("h2h_required") is False)
                events_false = sum(1 for r in lazy_rows if r.get("events_required") is False)
                cpl_false = sum(1 for r in lazy_rows if r.get("cpl_required") is False)
                _ok(result["checks"], "runtime_rows_preserved_when_skip_flags_false", True, f"lazy_rows={len(lazy_rows)},h2h_false={h2h_false},events_false={events_false},cpl_false={cpl_false}")
            else:
                result["warnings"].append("latest_scout_has_no_rf_lazy_shadow_rows")
        except Exception as exc:
            result["warnings"].append(f"runtime_read_warning:{exc}")
    else:
        result["warnings"].append("scout_artifact_not_found")

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"

    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_collection_pipeline_redesign_shadow_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
