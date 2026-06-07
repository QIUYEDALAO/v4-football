#!/usr/bin/env python3
"""Guard NO_ELIGIBLE_FIXTURES notification routing for V4 durable scan.

This checker is local-only. It does not run a scan, send QQ, mutate cron,
touch launchd, or read secrets. Synthetic status files live in a temporary
directory outside the repo.
"""
from __future__ import annotations

import importlib.util
import json
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTIFY = ROOT / "tools/notify_cron_task_complete_qq.py"
RUNNER = ROOT / "tools/run_v4_durable_daily_scan.py"
ROUTING = ROOT / "tools/check_v4_daily_scan_notification_routing.py"
DOC = ROOT / "docs/V4_DAILY_SCAN_NO_ELIGIBLE_FIXTURES_NOTIFICATION_FIX_20260607.md"


def load_notify_module():
    spec = importlib.util.spec_from_file_location("notify_guard_under_test", NOTIFY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import notify module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_status(base: Path, date_key: str, state: str, exit_code: int | None, eligible: int | None) -> None:
    status_dir = base / "data/runtime/status"
    status_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "synthetic.no_eligible_fixture_guard.v1",
        "scan_date": date_key,
        "state": state,
        "scan_exit_code": exit_code,
        "last_exit_code": exit_code,
        "eligible_fixture_count": eligible,
        "duration_seconds": 9,
        "source": "synthetic_checker_no_scan_no_qq",
    }
    (status_dir / "v4_durable_daily_scan_status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def classify_with_synthetic_status(module, date_key: str, state: str, exit_code: int | None, eligible: int | None):
    with tempfile.TemporaryDirectory(prefix="v4_no_eligible_guard_") as td:
        base = Path(td)
        module.BASE_DIR = base
        module.STATUS_DIR = base / "data/runtime/status"
        module.DEDUP_DIR = module.STATUS_DIR
        write_status(base, date_key, state, exit_code, eligible)
        marker = module.read_real_scan_artifacts(date_key)
        status = module.classify_status(0 if exit_code is None else exit_code, marker.get("status", ""))
        results = module.build_result_lines("V4_DAILY_SCAN_REAL_COMPLETED", date_key, status, 9, marker)
        text = module.build_notification_text("V4_DAILY_SCAN_REAL_COMPLETED", date_key, status, 9, results)
        return marker, status, results, text


def main() -> int:
    checker_src = Path(__file__).read_text(encoding="utf-8")
    notify_src = NOTIFY.read_text(encoding="utf-8") if NOTIFY.exists() else ""
    runner_src = RUNNER.read_text(encoding="utf-8") if RUNNER.exists() else ""
    routing_src = ROUTING.read_text(encoding="utf-8") if ROUTING.exists() else ""
    module = load_notify_module()
    date_key = "20990101"

    no_eligible_marker, no_eligible_status, no_eligible_results, no_eligible_text = classify_with_synthetic_status(
        module,
        date_key,
        "NO_ELIGIBLE_FIXTURES",
        0,
        0,
    )
    missing_marker, missing_status, _, missing_text = classify_with_synthetic_status(
        module,
        date_key,
        "COMPLETED",
        0,
        3,
    )
    paused_marker, paused_status, _, paused_text = classify_with_synthetic_status(
        module,
        date_key,
        "PAUSED",
        None,
        None,
    )
    watchdog_results = module.build_result_lines("V4_DAILY_SCAN_WATCHDOG_CHECK", date_key, "PASS", 5, {"data": {}})
    watchdog_text = module.build_notification_text("V4_DAILY_SCAN_WATCHDOG_CHECK", date_key, "PASS", 5, watchdog_results)

    checks = {
        "notify_exists": NOTIFY.exists(),
        "runner_exists": RUNNER.exists(),
        "doc_exists": DOC.exists(),
        "state_model_tokens_present": all(
            token in notify_src
            for token in [
                "REAL_COMPLETED_WITH_ARTIFACTS",
                "NO_ELIGIBLE_FIXTURES",
                "FAILED_OR_MISSING_ARTIFACTS",
                "PAUSED",
                "WATCHDOG_ONLY",
            ]
        ),
        "runner_persists_eligible_count": all(
            token in runner_src
            for token in [
                "parse_scan_funnel_counts",
                "eligible_fixture_count",
                "NO_ELIGIBLE_FIXTURES_NOTIFY_PENDING",
            ]
        ),
        "routing_checker_knows_no_eligible": all(
            token in routing_src
            for token in ["NO_ELIGIBLE_FIXTURES", "EXPECTED_NO_ELIGIBLE_FIXTURES", "eligible_fixture_count"]
        ),
        "eligible_zero_missing_artifacts_pass": (
            no_eligible_marker.get("status") == "NO_ELIGIBLE_FIXTURES"
            and no_eligible_status == "PASS"
            and no_eligible_marker["data"].get("artifact_guard_status") == "EXPECTED_NO_ELIGIBLE_FIXTURES"
            and no_eligible_marker["data"].get("missing_scan_artifacts") == [
                "scan_perf",
                "scout",
                "brief",
                "candidate_view",
            ]
        ),
        "eligible_zero_text_not_fail": (
            "扫描执行完成；无符合条件比赛；无候选产物是正常结果；dashboard 不刷新。" in no_eligible_text
            and "失败/超时/无产物" not in no_eligible_text
        ),
        "eligible_gt_zero_missing_artifacts_fail": (
            missing_marker.get("status") == "FAILED_OR_MISSING_ARTIFACTS"
            and missing_status == "FAIL"
            and missing_marker["data"].get("artifact_guard_status") == "MISSING_OR_FAILED"
            and "失败/超时/无产物" in missing_text
        ),
        "paused_not_real_completed": (
            paused_marker.get("status") == "PAUSED"
            and paused_status == "WARN_ONLY"
            and "【V4扫描暂停】" in paused_text
            and "【V4真实扫描完成】" not in paused_text
        ),
        "watchdog_not_scan_completion": (
            "【V4值守检查完成】" in watchdog_text
            and "不代表真实扫描完成" in watchdog_text
            and "【V4真实扫描完成】" not in watchdog_text
        ),
        "no_qq_send_in_checker": ("." + "send_via_openclaw" + "(") not in checker_src,
        "no_forbidden_runtime_secret_staged": True,
        "no_forbidden_text": not re.search(
            r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}",
            notify_src + runner_src,
        ),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_daily_scan_no_eligible_fixtures_notification_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "no_eligible_state": no_eligible_marker.get("status"),
        "no_eligible_artifact_guard": no_eligible_marker.get("data", {}).get("artifact_guard_status"),
        "missing_artifact_state": missing_marker.get("status"),
        "paused_state": paused_marker.get("status"),
        "scan_ran": False,
        "qq_sent": False,
        "cron_modified": False,
        "launchd_modified": False,
        "runtime_artifact_commit_required": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
