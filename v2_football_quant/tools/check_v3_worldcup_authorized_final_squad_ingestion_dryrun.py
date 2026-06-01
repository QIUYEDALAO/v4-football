#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_authorized_final_squad_ingestion_dryrun_20260602.json"
BUILDER = ROOT / "tools/build_v3_worldcup_authorized_final_squad_ingestion_dryrun.py"
REPORT = ROOT / "data/runtime/v3_worldcup/final_squads/v3_worldcup_authorized_final_squad_ingestion_dryrun_20260602.json"


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
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    add(checks, "report_exists", REPORT.exists(), str(REPORT))
    report = _load(REPORT)

    add(checks, "status_noop", report.get("status") in {"NOOP_SOURCE_FILES_MISSING", "NOOP_NO_AUTHORIZED_FILES_READY"}, report.get("status"))
    add(checks, "blocker_none", report.get("blocker") == "NONE", report.get("blocker"))
    add(checks, "approved_0", int(report.get("approved_sources_count", -1)) == 0, report.get("approved_sources_count"))
    add(checks, "intake_0", int(report.get("intake_files_found", -1)) == 0, report.get("intake_files_found"))
    add(checks, "authorized_0", int(report.get("authorized_files_found", -1)) == 0, report.get("authorized_files_found"))
    add(checks, "ready_0", int(report.get("final_squad_files_ready_for_ingestion", -1)) == 0, report.get("final_squad_files_ready_for_ingestion"))
    add(checks, "parsed_0", int(report.get("dryrun_files_parsed", -1)) == 0, report.get("dryrun_files_parsed"))
    add(checks, "official_not_written", report.get("official_final_squad_written") is False, report.get("official_final_squad_written"))
    add(checks, "noop_true", report.get("no_real_files_noop") is True, report.get("no_real_files_noop"))
    guard = report.get("safety_guard") if isinstance(report.get("safety_guard"), dict) else {}
    add(checks, "unauthorized_not_ingested", guard.get("unauthorized_files_not_ingested") is True, guard)
    add(checks, "dryrun_only", guard.get("dryrun_only") is True, guard)
    add(checks, "not_final26_claim", guard.get("final_squad_complete_not_claimed") is True, guard)

    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_web_fetch", "http://" not in src and "https://" not in src)
    add(checks, "no_qq_pending_validation_livebet_cron", all(x not in src for x in ["send_qq(", "write_pending(", "recompute_validation(", "append_live_bet(", "crontab"]))
    add(checks, "no_v4_scan", "scan_and_brief" not in src and "fullscan" not in src)
    add(checks, "no_default_rules_change", "default_rules =" not in src and "default_rules[" not in src)
    add(checks, "no_ab_thresholds_change", "ab_ratio_min_pct" not in src and "ab_ratio_max_pct" not in src)
    add(checks, "no_touch_outside57", "v4_outside57_scanner.py" not in src)
    add(checks, "no_secrets", all(x not in src for x in ["api-key", "token=", "secret"]))

    blockers = [x["name"] for x in checks if not x["ok"]]
    out = {"generated_at": datetime.now().isoformat(), "conclusion": "PASS" if not blockers else "BLOCKER", "blockers": blockers, "checks": checks}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
