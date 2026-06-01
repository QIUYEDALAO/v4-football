#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
OUT = STATUS / "check_v4_control_center_league_intel_20260601.json"
MODEL_BUILDER = ROOT / "tools/build_v4_control_center_model.py"
HTML = ROOT / "data/runtime/dashboard/v4_control_center.html"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _latest_model() -> dict[str, Any]:
    files = sorted(STATUS.glob("v4_control_center_model_*.json"))
    if not files:
        return {}
    payload = _load_json(files[-1])
    if isinstance(payload.get("model"), dict):
        return payload["model"]
    return payload


def main() -> int:
    checks: list[dict[str, Any]] = []
    run = subprocess.run([sys.executable, str(MODEL_BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    _add(checks, "build_v4_control_center_model_runs", run.returncode == 0, run.stderr or run.stdout[-800:])

    model = _latest_model()
    panel = model.get("league_intelligence_panel") if isinstance(model, dict) else {}
    _add(checks, "league_intelligence_panel_exists", isinstance(panel, dict) and bool(panel), type(panel).__name__)
    _add(checks, "league_intelligence_panel_status_valid", str(panel.get("status")) in {"PASS", "WARN_ONLY", "DATA_MISSING"}, panel.get("status"))

    tag_counts = panel.get("tag_counts") if isinstance(panel, dict) else {}
    _add(checks, "tag_counts_exists", isinstance(tag_counts, dict), tag_counts)
    total_leagues = int(panel.get("total_leagues") or 0)
    _add(checks, "total_leagues_expected", total_leagues == 54, total_leagues)
    _add(checks, "low_sample_count_expected", int(tag_counts.get("LOW_SAMPLE") or 0) == 7, tag_counts.get("LOW_SAMPLE"))
    _add(checks, "do_not_conclude_count_expected", int(tag_counts.get("DO_NOT_CONCLUDE") or 0) == 42, tag_counts.get("DO_NOT_CONCLUDE"))
    _add(checks, "pending_only_count_expected", int(tag_counts.get("PENDING_ONLY") or 0) == 1, tag_counts.get("PENDING_ONLY"))
    _add(checks, "data_gap_count_expected", int(tag_counts.get("DATA_GAP") or 0) == 4, tag_counts.get("DATA_GAP"))

    pending_list = model.get("pending_only_league_list") or []
    arg_cup = [x for x in pending_list if isinstance(x, dict) and str(x.get("league")) == "阿根廷杯"]
    _add(checks, "argentina_cup_pending_only_present", bool(arg_cup), arg_cup[:1])

    guard = model.get("league_watchlist_safety_guard") or {}
    _add(checks, "pending_only_excluded_from_denominator", guard.get("pending_only_excluded_from_denominator") is True, guard)
    _add(checks, "low_trust_alert_auto_exclude_false", guard.get("low_trust_alert_auto_exclude") is False, guard)
    _add(checks, "do_not_conclude_negative_grade_false", guard.get("do_not_conclude_negative_grade") is False, guard)
    _add(checks, "league_tags_no_official_grade_change", guard.get("league_tags_do_not_affect_official_grade") is True, guard)

    trend = model.get("league_watchlist_trend_summary") or {}
    trend_guard = str(trend.get("self_reference_guard_status") or "WARN_ONLY")
    _add(checks, "trend_self_reference_guard_safe", trend_guard == "PASS" or str(panel.get("status")) in {"WARN_ONLY", "DATA_MISSING"}, trend_guard)

    html = HTML.read_text(encoding="utf-8", errors="ignore") if HTML.exists() else ""
    _add(checks, "baseline_only_wording_exists", "当前仅有 baseline 快照，不能判断趋势。" in html, "baseline_only_wording")
    _add(checks, "html_has_league_intel", "联赛情报" in html, "联赛情报")
    _add(checks, "html_has_official_grade_observe_only", "不自动影响 official grade" in html, "official_grade_note")
    _add(checks, "html_has_not_auto_exclude", "不自动排除" in html, "not_auto_exclude")
    _add(checks, "html_has_pending_not_denominator", "不进分母" in html, "pending_not_denominator")
    banned = ["AUTO_EXCLUDE", "BLACKLIST", "RULE_CHANGE_NOW", "THRESHOLD_CHANGE_NOW"]
    _add(checks, "html_no_banned_auto_rule_tokens", all(x not in html for x in banned), banned)
    _add(checks, "league_panel_exists_when_ab_zero_possible", isinstance(panel, dict) and bool(panel), panel.get("status"))

    src = MODEL_BUILDER.read_text(encoding="utf-8")
    _add(checks, "no_api", "requests." not in src and "urlopen(" not in src)
    _add(checks, "no_scan", "scan_and_brief" not in src and "fullscan" not in src)
    _add(checks, "no_qq", "qq_push" not in src.lower() and "send_qq" not in src.lower())
    _add(checks, "no_pending_write", "write_pending" not in src.lower() and "pending_route" not in src)
    _add(checks, "no_validation_recompute", "recompute_validation" not in src.lower() and "recompute(" not in src.lower())
    _add(checks, "no_live_bet_write", "append_live_bet" not in src.lower())
    _add(checks, "no_cron_change", "crontab" not in src.lower())
    _add(checks, "no_sent_marker_write", "sent_marker" not in src.lower())

    blockers = [x["name"] for x in checks if not x["ok"]]
    result = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
        "full_scan_ran": False,
        "validation_recomputed": False,
        "QQ_push": False,
        "pending_written": False,
        "live_bet_written": False,
        "cron_modified": False,
        "sent_marker_written": False,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": result["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
