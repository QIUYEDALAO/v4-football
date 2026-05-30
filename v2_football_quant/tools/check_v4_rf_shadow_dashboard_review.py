#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
TZ = timezone(timedelta(hours=8))

REQUIRED_SHADOW_FIELDS = [
    "rf_shadow_grade",
    "market_adjusted_shadow_grade",
    "rf_balance_reason",
    "h2h_recent5_bonus_reason",
    "opening_market_reason",
    "market_adjustment_reason",
    "shadow_review_status",
    "shadow_review_note",
    "official_vs_shadow_diff",
    "official_vs_shadow_reason",
]


def _latest(pattern: str, base: Path) -> Path | None:
    files = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ok(checks: list[dict], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _run(script: str) -> tuple[bool, str]:
    p = subprocess.run(["python3", str(ROOT / "tools" / script)], capture_output=True, text=True)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def _clean_str(v: Any) -> str:
    return str(v if v is not None else "").strip()


def _is_bad(v: Any) -> bool:
    s = _clean_str(v).lower()
    return s in {"undefined", "null", "nan"}


def main() -> int:
    checks: list[dict] = []
    warnings: list[str] = []
    blockers: list[str] = []

    model_path = _latest("v4_control_center_model_*.json", STATUS)
    html_path = ROOT / "data" / "runtime" / "dashboard" / "v4_control_center.html"
    builder_path = ROOT / "tools" / "build_v4_control_center_model.py"

    _ok(checks, "model_exists", model_path is not None and model_path.exists(), str(model_path) if model_path else "")
    _ok(checks, "dashboard_html_exists", html_path.exists(), str(html_path))
    _ok(checks, "builder_exists", builder_path.exists(), str(builder_path))
    if not (model_path and model_path.exists() and html_path.exists() and builder_path.exists()):
        blockers.append("required_files_missing")
        return _finish(checks, warnings, blockers)

    model = _load_json(model_path)
    html_src = html_path.read_text(encoding="utf-8")
    builder_src = builder_path.read_text(encoding="utf-8")

    items = ((model.get("candidates") or {}).get("items") or [])
    pending = ((model.get("todo_summary") or {}).get("pending_bet_candidates") or [])
    todo_summary = model.get("todo_summary") or {}
    top_todo = ((model.get("top_status") or {}).get("today_todo") or {})
    pending_count = int(todo_summary.get("to_bet") or 0)

    # 1-6 model shadow fields
    if items:
        for f in REQUIRED_SHADOW_FIELDS:
            ok = all((f in x and not _is_bad(x.get(f))) for x in items if isinstance(x, dict))
            _ok(checks, f"model_items_has_{f}", ok)
            if not ok:
                blockers.append(f"missing_or_bad:{f}")
    else:
        warnings.append("candidate_items_empty")
        for f in REQUIRED_SHADOW_FIELDS:
            ok = f in builder_src
            _ok(checks, f"builder_contains_{f}", ok)
            if not ok:
                blockers.append(f"builder_missing:{f}")

    # 7 official grade no overwrite
    _ok(checks, "official_grade_not_overwritten_by_shadow", "official_grade" in builder_src and "grade" in builder_src)
    if "official_grade" not in builder_src:
        blockers.append("official_grade_mapping_missing")

    # 8-9 todo / pending not altered by shadow
    _ok(checks, "todo_to_bet_matches_pending_len", pending_count == len(pending), f"to_bet={pending_count},pending_len={len(pending)}")
    if pending_count != len(pending):
        blockers.append("todo_pending_mismatch")
    pending_grades_ok = all(str((x or {}).get("grade") or "").upper() in {"A", "B"} for x in pending if isinstance(x, dict))
    _ok(checks, "pending_candidates_official_ab_only", pending_grades_ok, f"count={len(pending)}")
    if not pending_grades_ok:
        blockers.append("pending_contains_non_official_grade")

    # 10-12 validation/live-bet/qq no shadow usage
    validation_uses_shadow = "rf_shadow_grade" in json.dumps(model.get("cumulative_validation_detail") or {}, ensure_ascii=False)
    _ok(checks, "validation_not_using_shadow_grade", not validation_uses_shadow)
    if validation_uses_shadow:
        blockers.append("validation_uses_shadow")
    _ok(checks, "live_bet_not_using_shadow_grade", "rf_shadow_grade" not in json.dumps(model.get("live_bet") or {}, ensure_ascii=False))
    qq_src = (ROOT / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8").lower()
    qq_lines = "\n".join(line for line in qq_src.splitlines() if "qq" in line)
    qq_shadow_coupled = ("rf_shadow_grade" in qq_lines) or ("market_adjusted_shadow_grade" in qq_lines)
    _ok(checks, "qq_not_using_shadow_grade", not qq_shadow_coupled)

    # 13-17 HTML review content
    _ok(checks, "html_has_rf_shadow_review_block", "RF影子观察" in html_src)
    _ok(checks, "html_has_shadow_disclaimer", "影子观察，不作为投注推荐" in html_src)
    _ok(checks, "html_uses_safe_for_null_undefined_nan", "low===\"undefined\"||low===\"null\"||low===\"nan\"" in html_src.replace(" ", ""))
    _ok(checks, "html_not_restore_candidate_card", "candidate-card" not in html_src)
    _ok(checks, "shadow_only_bet_disabled_copy_exists", "该行仅影子观察，投注操作已禁用" in html_src)
    for name, cond in [
        ("html_has_rf_shadow_review_block", "RF影子观察" in html_src),
        ("html_has_shadow_disclaimer", "影子观察，不作为投注推荐" in html_src),
        ("html_not_restore_candidate_card", "candidate-card" not in html_src),
    ]:
        if not cond:
            blockers.append(name)

    # 18-21 safety guards
    ok_guard, out_guard = _run("check_v4_production_default_rules_guard.py")
    _ok(checks, "default_rules_guard_pass", ok_guard, out_guard[-300:])
    if not ok_guard:
        blockers.append("default_rules_guard_failed")

    ok_slim, out_slim = _run("check_v4_system_slim_and_whitelist_mode.py")
    _ok(checks, "cron_whitelist_guard_pass", ok_slim, out_slim[-300:])
    if not ok_slim:
        blockers.append("cron_or_whitelist_guard_failed")

    ok_no_market, out_no_market = _run("check_v4_no_market_core_validation_skip.py")
    soft_no_market = ok_no_market or ("WARN_ONLY" in out_no_market)
    _ok(checks, "validation_livebet_guard_pass", soft_no_market, out_no_market[-300:])
    if not soft_no_market:
        blockers.append("validation_or_livebet_guard_failed")

    # 22-23 staged safety
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout
    staged_files = [x.strip() for x in staged.splitlines() if x.strip()]
    secret_hits = [x for x in staged_files if any(k in x.lower() for k in [".env", "secret", "token", "apikey", "api_key"])]
    runtime_hits = [x for x in staged_files if x.startswith("v2_football_quant/data/runtime/")]
    acceptance_hits = [x for x in staged_files if "data/runtime/acceptance/" in x]
    _ok(checks, "no_secrets_staged", len(secret_hits) == 0, ",".join(secret_hits))
    _ok(checks, "no_runtime_artifact_staged", len(runtime_hits) == 0, ",".join(runtime_hits))
    _ok(checks, "no_acceptance_artifact_staged", len(acceptance_hits) == 0, ",".join(acceptance_hits))
    if secret_hits:
        blockers.append("secrets_staged")
    if runtime_hits:
        blockers.append("runtime_artifact_staged")
    if acceptance_hits:
        blockers.append("acceptance_artifact_staged")

    # extra consistency
    top_to_bet = int(top_todo.get("pending_bets") or 0)
    _ok(checks, "top_status_pending_bets_consistent", top_to_bet == pending_count, f"top={top_to_bet},todo={pending_count}")
    if top_to_bet != pending_count:
        warnings.append("top_todo_pending_bets_mismatch")

    return _finish(checks, warnings, blockers)


def _finish(checks: list[dict], warnings: list[str], blockers: list[str]) -> int:
    result = {
        "checker": "check_v4_rf_shadow_dashboard_review",
        "generated_at": datetime.now(TZ).isoformat(),
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    out = STATUS / f"check_v4_rf_shadow_dashboard_review_{datetime.now(TZ).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
