#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "data/runtime/dashboard/v4_control_center.html"
MODEL_BUILDER = ROOT / "tools/build_v4_control_center_model.py"
REVIEW_JSON = ROOT / "data/runtime/validation/v4_official_ab_validation_review_20260531.json"
REVIEW_MD = ROOT / "data/daily_reports/V4_20260531_OFFICIAL_AB_VALIDATION_REVIEW.md"
OUT = ROOT / "data/runtime/status/check_v4_control_center_validation_sync_20260601.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _run_builder() -> tuple[bool, str]:
    cp = subprocess.run(
        ["python3", str(MODEL_BUILDER)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return cp.returncode == 0, (cp.stdout + cp.stderr)[-4000:]


def _assert_value(blockers: list[str], name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        blockers.append(f"{name}:expected={expected!r},actual={actual!r}")


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    if not REVIEW_JSON.exists():
        blockers.append("locked_review_json_missing")
    if not REVIEW_MD.exists():
        blockers.append("locked_review_md_missing")
    if not DASHBOARD.exists():
        blockers.append("dashboard_html_missing")

    build_ok, build_log = _run_builder()
    if not build_ok:
        blockers.append(f"model_builder_failed:{build_log}")

    review_raw = _load_json(REVIEW_JSON)
    models = sorted((ROOT / "data/runtime/status").glob("v4_control_center_model_*.json"))
    model_path = models[-1] if models else ROOT / "data/runtime/status/v4_control_center_model_20260601.json"
    model = _load_json(model_path)
    latest = model.get("latest_validation_review") if isinstance(model, dict) else {}
    league_snap = model.get("latest_league_validation_snapshot") if isinstance(model, dict) else {}
    html = _read(DASHBOARD)

    if not isinstance(latest, dict) or not latest:
        blockers.append("latest_validation_review_missing_in_model")
        latest = {}
    if not isinstance(league_snap, dict) or not league_snap:
        blockers.append("latest_league_validation_snapshot_missing_in_model")
        league_snap = {}

    _assert_value(blockers, "review_candidate_date", review_raw.get("candidate_date"), "20260531")
    _assert_value(blockers, "model_validation_date", latest.get("validation_date"), "20260531")
    _assert_value(blockers, "artifact_generated_date", latest.get("artifact_generated_date"), "20260601")
    _assert_value(blockers, "validated_count", latest.get("validated_count"), 36)
    _assert_value(blockers, "pending_result_count", latest.get("pending_result_count"), 1)
    _assert_value(blockers, "hit_count", latest.get("hit_count"), 25)
    _assert_value(blockers, "miss_count", latest.get("miss_count"), 11)

    official = latest.get("official_A_B_C_SKIP") or {}
    _assert_value(blockers, "official_A", official.get("A"), 1)
    _assert_value(blockers, "official_B", official.get("B"), 36)
    _assert_value(blockers, "official_C", official.get("C"), 0)
    _assert_value(blockers, "official_SKIP", official.get("SKIP"), 55)
    _assert_value(blockers, "A_rate", (latest.get("A_hit_miss_rate") or {}).get("display"), "1/1 = 100.0%")
    _assert_value(blockers, "B_rate", (latest.get("B_hit_miss_rate") or {}).get("display"), "24/35 = 68.6%")
    _assert_value(blockers, "AB_rate", (latest.get("AB_hit_miss_rate") or {}).get("display"), "25/36 = 69.4%")
    _assert_value(blockers, "rescue_rate", (latest.get("rescue_hit_miss_rate") or {}).get("display"), "6/9 = 66.7%")
    _assert_value(blockers, "non_rescue_rate", (latest.get("non_rescue_hit_miss_rate") or {}).get("display"), "19/27 = 70.4%")
    _assert_value(blockers, "system_anomaly_count", latest.get("system_anomaly_count"), 0)
    _assert_value(blockers, "rule_change_recommended", latest.get("rule_change_recommended"), "NO")

    focus = {row.get("league"): row for row in (league_snap.get("focus_leagues") or []) if isinstance(row, dict)}
    expected_focus = {
        "冰岛超": ("4/4 = 100.0%", 0),
        "挪甲": ("4/4 = 100.0%", 0),
        "巴西甲": ("3/5 = 60.0%", 0),
        "智利甲": ("1/3 = 33.3%", 0),
        "阿根廷杯": ("0 validated / 1 pending", 1),
    }
    for league, (display, pending) in expected_focus.items():
        row = focus.get(league)
        if not row:
            blockers.append(f"focus_league_missing:{league}")
            continue
        _assert_value(blockers, f"focus_display:{league}", row.get("display"), display)
        _assert_value(blockers, f"focus_pending:{league}", row.get("pending_count"), pending)

    html_tokens = [
        "昨日验证复盘摘要",
        "20260531 联赛验证快照",
        "rule change recommended",
        "system anomalies",
        "pending/postponed 不作为 miss",
        "不自动修改 DEFAULT_RULES / A-B thresholds / official grade",
    ]
    for token in html_tokens:
        if token not in html:
            blockers.append(f"html_token_missing:{token}")

    model_src = _read(MODEL_BUILDER)
    banned_static = {
        "api_or_http_call": r"(requests\.|urlopen\(|fetch\(|/api/)",
        "qq_push": r"(qq_push|send_qq|push_qq|QQ_push\s*=\s*True)",
        "pending_write": r"(pending.*write_text|write_text.*pending|pending_route)",
        "live_bet_write": r"(v4_live_bets_.*write|live_bets.*write_text)",
        "cron_modify": r"(crontab|cron_schedule_modified.*True)",
        "sent_marker": r"(sent_marker|sent.*marker)",
        "validation_recompute": r"(recompute_validation|重新计算|validation_recomputed[\"']?\s*[:=]\s*True)",
    }
    for name, pattern in banned_static.items():
        if re.search(pattern, model_src, flags=re.IGNORECASE):
            if name == "api_or_http_call" and "/api/" in html:
                continue
            blockers.append(f"forbidden_static_token:{name}")

    audit = model.get("audit", {}) if isinstance(model, dict) else {}
    if audit.get("strategy_changed") is not False:
        blockers.append("audit_strategy_changed_not_false")
    if audit.get("validation_recomputed") is not False:
        blockers.append("audit_validation_recomputed_not_false")
    if audit.get("QQ_recommendation_pushed") is not False:
        blockers.append("audit_QQ_push_not_false")
    if audit.get("cron_schedule_modified") is not False:
        blockers.append("audit_cron_modified_not_false")

    result = {
        "checker": "tools/check_v4_control_center_validation_sync.py",
        "generated_at": datetime.now().isoformat(),
        "conclusion": "BLOCKER" if blockers else ("WARN_ONLY" if warnings else "PASS"),
        "blockers": blockers,
        "warnings": warnings,
        "locked_review_json": str(REVIEW_JSON),
        "locked_review_md": str(REVIEW_MD),
        "model_file": str(model_path),
        "full_scan_ran": False,
        "validation_recomputed": False,
        "QQ_push": False,
        "pending_written": False,
        "live_bet_touched": False,
        "cron_modified": False,
        "sent_marker_touched": False,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
