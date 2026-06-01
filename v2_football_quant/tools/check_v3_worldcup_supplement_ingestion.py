#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_supplement_ingestion_20260602.json"
SCHEMA = ROOT / "tools/v3_worldcup_supplement_schema.py"
BUILDER = ROOT / "tools/build_v3_worldcup_supplement_ingestion.py"
RPT = ROOT / "data/runtime/v3_worldcup/supplement_reports/v3_worldcup_supplement_coverage_20260602.json"
TEMPLATE_DIR = ROOT / "data/v3_worldcup/supplements/templates"


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
    add(checks, "schema_exists", SCHEMA.exists(), str(SCHEMA))
    need_templates = [
        "caps_goals_minutes_template.json",
        "injuries_template.json",
        "friendly_form_template.json",
        "market_baseline_template.json",
        "club_form_template.json",
        "coach_profiles_template.json",
        "wc_history_template.json",
    ]
    for t in need_templates:
        p = TEMPLATE_DIR / t
        add(checks, f"template_exists:{t}", p.exists(), str(p))
        if p.exists():
            o = _load(p)
            rows = o.get("records") if isinstance(o.get("records"), list) else []
            ds_ok = all((isinstance(x, dict) and str(x.get("data_status")) == "TEMPLATE_ONLY") for x in rows)
            add(checks, f"template_status_template_only:{t}", ds_ok, len(rows))
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    add(checks, "coverage_report_exists", RPT.exists(), str(RPT))
    report = _load(RPT)
    add(checks, "status_legal", str(report.get("status")) in {"SUPPLEMENT_LAYER_READY_TEMPLATE_ONLY", "SUPPLEMENT_LAYER_PARTIAL_READY_WITH_WARN_ONLY"}, report.get("status"))
    add(checks, "blocker_none", report.get("blocker") == "NONE", report.get("blocker"))
    add(checks, "no_fake_present_when_template_only", not (str(report.get("status")) == "SUPPLEMENT_LAYER_READY_TEMPLATE_ONLY" and any((v or {}).get("coverage_status") == "PRESENT" for v in (report.get("coverage_by_category") or {}).values())), report.get("coverage_by_category"))
    g = report.get("safety_guard") or {}
    add(checks, "guard_roster_not_modified", g.get("supplement_does_not_modify_roster") is True, g)
    add(checks, "guard_baseline_not_overridden", g.get("supplement_does_not_override_baseline") is True, g)
    text = json.dumps(report, ensure_ascii=False).lower()
    add(checks, "no_betting_words", all(x not in text for x in ["bet ready", "recommendation_ready", "auto_trade_ready", "auto bet", "locked pick"]), "text_scan")
    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api_no_webfetch", "requests." not in src and "urlopen(" not in src and "http://" not in src and "https://" not in src)
    add(checks, "no_qq_pending_validation_livebet_cron", all(x not in src for x in ["send_qq(", "pending_route(", "recompute_validation(", "append_live_bet(", "crontab"]))
    add(checks, "no_v4_scan", "scan_and_brief" not in src and "fullscan" not in src)
    add(
        checks,
        "no_default_rules_or_threshold_touch",
        "update_default_rules(" not in src and "set_ab_threshold(" not in src and "modify_threshold(" not in src,
    )
    add(checks, "no_touch_outside57_scanner", "v4_outside57_scanner.py" not in src)
    add(checks, "no_secrets", all(x not in src for x in ["api-key", "token=", "secret"]))

    blockers = [c["name"] for c in checks if not c["ok"]]
    out = {"generated_at": datetime.now().isoformat(), "conclusion": "PASS" if not blockers else "BLOCKER", "blockers": blockers, "checks": checks}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
