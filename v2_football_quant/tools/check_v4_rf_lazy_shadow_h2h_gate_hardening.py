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


def _ok(checks: dict[str, dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}


def _latest(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _run_checker(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def _cron_payload() -> str:
    p = subprocess.run(["openclaw", "cron", "list", "--json"], cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        return ""
    try:
        data = json.loads(p.stdout)
    except Exception:
        return ""
    jobs = data.get("jobs") if isinstance(data, dict) else []
    if not isinstance(jobs, list):
        return ""
    for job in jobs:
        if str(job.get("name") or "") == "V4_DAILY_SCAN_READONLY":
            return str(((job.get("payload") or {}).get("message")) or "")
    return ""


def main() -> int:
    result: dict[str, Any] = {
        "checker": "check_v4_rf_lazy_shadow_h2h_gate_hardening",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": {},
        "warnings": [],
        "blockers": [],
        "conclusion": "PASS",
    }

    runner_src = (ROOT / "engine" / "v4_runner.py").read_text(encoding="utf-8")
    brief_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")

    # 1) order: RF + market before H2H call
    lazy_anchor = runner_src.find('if collection_mode == "rf_lazy_shadow":')
    lazy_end = runner_src.find('logger.info(f"  ⏳ H2H:', lazy_anchor)
    lazy_block = runner_src[lazy_anchor:lazy_end] if lazy_anchor != -1 and lazy_end != -1 else ""

    idx_rf = lazy_block.find("build_recent_form_shadow_from_recent(")
    idx_market = lazy_block.find("market_stub = build_rf_shadow_grade_layer(")
    idx_gate = lazy_block.find("_build_lazy_prefilter_decision(")
    idx_h2h = lazy_block.find("evaluate_h2h_edge(")
    order_ok = all(i != -1 for i in [idx_rf, idx_market, idx_gate, idx_h2h]) and idx_rf < idx_market < idx_gate < idx_h2h
    _ok(result["checks"], "h2h_after_rf_and_market", order_ok, f"rf={idx_rf},market={idx_market},gate={idx_gate},h2h={idx_h2h}")
    if not order_ok:
        result["blockers"].append("h2h_order_invalid")

    # 2-5 hard reasons before H2H
    must_reasons = [
        "MARKET_HARD_VETO_BEFORE_H2H",
        "MARKET_NO_DATA_RF_NOT_STRONG",
        "FRIENDLY_SKIP_H2H",
        "YOUTH_SKIP_H2H",
        "NON_FORMAL_SKIP_H2H",
        "NO_MARKET_BEFORE_H2H",
    ]
    reasons_ok = all(r in runner_src for r in must_reasons)
    _ok(result["checks"], "hard_skip_reasons_present", reasons_ok, ",".join([r for r in must_reasons if r not in runner_src]))
    if not reasons_ok:
        result["blockers"].append("hard_skip_reasons_missing")

    # 6-8 hard behavior markers
    _ok(result["checks"], "h2h_false_not_call_api_marker", "if h2h_required:" in lazy_block)
    _ok(result["checks"], "h2h_false_row_preserve_marker", "stats[\"scouted\"] += 1" in lazy_block)
    denominator_ok = "H2H(lazy required" in runner_src and "h2h_required_total" in runner_src
    _ok(result["checks"], "h2h_progress_uses_required_denominator", denominator_ok)
    if not denominator_ok:
        result["blockers"].append("h2h_progress_denominator_not_required")

    # 9-10 budget + timeout markers
    budget_ok = "H2H_MAX_REQUIRED_RATIO = 0.35" in runner_src and "H2H_BUDGET_EXCEEDED" in runner_src
    timeout_ok = "H2H_PER_FIXTURE_TIMEOUT_SECONDS" in runner_src and "H2H_TIMEOUT_SKIP" in runner_src
    _ok(result["checks"], "h2h_budget_present", budget_ok)
    _ok(result["checks"], "h2h_timeout_skip_present", timeout_ok)
    if not budget_ok:
        result["blockers"].append("h2h_budget_missing")
    if not timeout_ok:
        result["blockers"].append("h2h_timeout_missing")

    # 11-15 security guards
    cron_msg = _cron_payload()
    cron_ok = "--collection-mode rf_lazy_shadow" not in cron_msg and "--max-fixtures" not in cron_msg
    _ok(result["checks"], "cron_not_changed_to_lazy", cron_ok, cron_msg)
    if not cron_ok:
        result["blockers"].append("cron_modified_for_lazy")

    default_ok, default_out = _run_checker("check_v4_production_default_rules_guard.py")
    _ok(result["checks"], "default_rules_guard_pass", default_ok, default_out[-200:])
    if not default_ok:
        result["blockers"].append("default_rules_guard_failed")

    qq_disabled = "V4_QQ_ENABLED = False" in brief_src
    _ok(result["checks"], "qq_push_disabled", qq_disabled)
    if not qq_disabled:
        result["blockers"].append("qq_guard_missing")

    # runtime sanity from latest scout
    scout_path = _latest("scout_v4_*.json", REPORT)
    scout_rows = _load_json(scout_path)
    lazy_rows = [r for r in scout_rows if isinstance(r, dict) and str(r.get("collection_mode") or "").lower() == "rf_lazy_shadow"] if isinstance(scout_rows, list) else []

    if not lazy_rows:
        result["warnings"].append("no_lazy_rows_in_latest_scout")
    else:
        h2h_false = [r for r in lazy_rows if r.get("h2h_required") is False]
        h2h_false_called = [r for r in h2h_false if r.get("h2h_collected") is True]
        _ok(result["checks"], "h2h_false_not_collected_runtime", len(h2h_false_called) == 0, f"h2h_false={len(h2h_false)} called={len(h2h_false_called)}")
        if h2h_false_called:
            result["blockers"].append("h2h_called_when_not_required")

        required_true = [r for r in lazy_rows if r.get("h2h_required") is True]
        ratio = (len(required_true) / max(1, len(lazy_rows)))
        ratio_ok = ratio <= 0.35 + 1e-9 or any(str(r.get("h2h_skipped_reason") or "") == "H2H_BUDGET_EXCEEDED" for r in lazy_rows)
        _ok(result["checks"], "h2h_required_ratio_controlled", ratio_ok, f"required={len(required_true)}/{len(lazy_rows)} ratio={ratio:.3f}")
        if not ratio_ok:
            result["warnings"].append("h2h_required_ratio_over_35_without_budget_reason")

        rows_preserved_ok = len(lazy_rows) > 0
        _ok(result["checks"], "scout_rows_preserved_in_lazy", rows_preserved_ok, f"lazy_rows={len(lazy_rows)}")
        if not rows_preserved_ok:
            result["blockers"].append("lazy_rows_missing")

    # staging safety
    staged_raw = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged = [x.strip() for x in staged_raw.splitlines() if x.strip()]
    secret_hits = [x for x in staged if any(k in x.lower() for k in [".env", "secret", "token", "api_key", "apikey"])]
    runtime_hits = [x for x in staged if x.startswith("data/runtime/")]
    _ok(result["checks"], "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    _ok(result["checks"], "runtime_artifact_not_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    if secret_hits:
        result["blockers"].append("secrets_staged")
    if runtime_hits:
        result["blockers"].append("runtime_artifacts_staged")

    if result["blockers"]:
        result["conclusion"] = "BLOCKER"

    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / f"check_v4_rf_lazy_shadow_h2h_gate_hardening_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
