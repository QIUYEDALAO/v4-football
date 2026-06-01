#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/runtime/status/check_v3_worldcup_final_squad_canonicalization_20260602.json"
SCHEMA = ROOT / "tools/v3_worldcup_final_squad_schema.py"
BUILDER = ROOT / "tools/build_v3_worldcup_final_squad_canonicalization.py"
REPORT = ROOT / "data/runtime/v3_worldcup/final_squads/v3_worldcup_final_squad_canonicalization_20260602.json"
TPL1 = ROOT / "data/v3_worldcup/final_squads/templates/final_squad_template.json"
TPL2 = ROOT / "data/v3_worldcup/final_squads/templates/final_team_list_48_template.json"


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
    add(checks, "template_final_squad_exists", TPL1.exists(), str(TPL1))
    add(checks, "template_team48_exists", TPL2.exists(), str(TPL2))

    t1 = _load(TPL1)
    add(checks, "template_final_squad_status_template_only", ((t1.get("meta") or {}).get("data_status") == "TEMPLATE_ONLY"), (t1.get("meta") or {}).get("data_status"))
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    add(checks, "report_exists", REPORT.exists(), str(REPORT))
    payload = _load(REPORT)

    add(checks, "teams_expected_48", int(payload.get("teams_expected") or 0) == 48, payload.get("teams_expected"))
    add(checks, "teams_detected_46", int(payload.get("teams_detected_in_baseline") or 0) == 46, payload.get("teams_detected_in_baseline"))
    add(checks, "players_total_1375", int(payload.get("players_total_baseline") or 0) == 1375, payload.get("players_total_baseline"))
    add(checks, "status_legal", payload.get("status") in {"FINAL_SQUAD_LAYER_READY_TEMPLATE_ONLY", "FINAL_SQUAD_LAYER_READY_WITH_COVERAGE_WARN_ONLY"}, payload.get("status"))
    add(checks, "blocker_none", payload.get("blocker") == "NONE", payload.get("blocker"))
    add(checks, "not_complete", payload.get("status") != "FINAL_SQUAD_COMPLETE", payload.get("status"))
    add(checks, "dryrun_status_present", bool(payload.get("ingestion_dryrun_status")), payload.get("ingestion_dryrun_status"))

    guard = payload.get("safety_guard") if isinstance(payload.get("safety_guard"), dict) else {}
    add(checks, "baseline_not_final26", guard.get("baseline_pool_not_treated_as_final_26") is True, guard)
    add(checks, "missing_not_fake_filled", guard.get("missing_team_not_filled_by_fake_data") is True, guard)
    add(checks, "no_override_baseline", guard.get("final_squad_does_not_override_baseline") is True, guard)
    add(checks, "no_betting", guard.get("no_betting_recommendations") is True, guard)

    src_builder = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api", "requests." not in src_builder and "urlopen(" not in src_builder)
    add(checks, "no_web_fetch", "http://" not in src_builder and "https://" not in src_builder)
    add(
        checks,
        "no_qq_pending_validation_livebet_cron",
        all(
            x not in src_builder
            for x in [
                "send_qq(",
                "write_pending(",
                "recompute_validation(",
                "append_live_bet(",
                "crontab",
            ]
        ),
    )
    add(checks, "no_v4_scan", "scan_and_brief" not in src_builder and "fullscan" not in src_builder)
    add(checks, "no_default_rules_change", "default_rules =" not in src_builder and "default_rules[" not in src_builder)
    add(checks, "no_ab_thresholds_change", "ab_ratio_min_pct" not in src_builder and "ab_ratio_max_pct" not in src_builder)
    add(checks, "no_touch_outside57_scanner", "v4_outside57_scanner.py" not in src_builder)
    add(checks, "no_secrets", all(x not in src_builder for x in ["api-key", "token=", "secret"]))

    blockers = [x["name"] for x in checks if not x["ok"]]
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "blockers": blockers,
        "checks": checks,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
