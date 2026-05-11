from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = BASE_DIR / "engine"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _run(cmd: list[str]) -> dict:
    started = datetime.now().isoformat()
    proc = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
    ended = datetime.now().isoformat()
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "started_at": started,
        "ended_at": ended,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def build_steps(date_key: str, phase: str) -> list[list[str]]:
    py = sys.executable
    all_steps = {
        "scan": [py, str(ENGINE_DIR / "v4_runner.py"), "--run_tag", "MASTER", "--lookahead-hours", "24"],
        "ht_live": [py, str(ENGINE_DIR / "live_ht_over_monitor.py"), "--date", date_key, "--once"],
        "ht_verify": [py, str(ENGINE_DIR / "v4_ht_result_verifier.py"), "--date", date_key, "--once"],
        "sh_live": [py, str(ENGINE_DIR / "second_half_evaluator.py"), "--date", date_key, "--once"],
        "sh_verify": [py, str(ENGINE_DIR / "v4_sh_result_verifier.py"), "--date", date_key],
        "daily_review": [py, str(ENGINE_DIR / "v4_review_report.py"), "--date", date_key],
        "calibration": [py, str(ENGINE_DIR / "v4_calibration_report.py"), "--save"],
        "sh_eval": [py, str(ENGINE_DIR / "v4_sh_strategy_eval.py"), "--save"],
        "wf_report": [py, str(ENGINE_DIR / "walk_forward_backtest.py"), "--save"],
        "context_report": [py, str(ENGINE_DIR / "context_marginal_report.py"), "--save"],
    }
    if phase == "full":
        order = ["scan", "ht_live", "ht_verify", "sh_live", "sh_verify", "daily_review", "calibration", "sh_eval", "wf_report", "context_report"]
    elif phase == "prematch":
        order = ["scan", "daily_review"]
    elif phase == "ht":
        order = ["ht_live", "ht_verify", "daily_review", "calibration"]
    elif phase == "sh":
        order = ["sh_live", "sh_verify", "daily_review", "sh_eval"]
    elif phase == "reports":
        order = ["daily_review", "calibration", "sh_eval", "wf_report", "context_report"]
    else:
        raise ValueError(f"Unsupported phase: {phase}")
    return [all_steps[k] for k in order]


def run_master(date_str: str, phase: str) -> dict:
    key = _date_key(date_str)
    steps = build_steps(key, phase)
    results = []
    for cmd in steps:
        res = _run(cmd)
        results.append(res)
        if res["returncode"] != 0:
            break
    ok = all(r["returncode"] == 0 for r in results)
    out = {
        "date": key,
        "phase": phase,
        "ok": ok,
        "executed_steps": len(results),
        "results": results,
        "generated_at": datetime.now().isoformat(),
    }
    out_path = REPORT_DIR / f"v4_master_run_{key}_{phase}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    out["report_path"] = str(out_path)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument(
        "--phase",
        default="full",
        choices=["full", "prematch", "ht", "sh", "reports"],
        help="执行阶段",
    )
    args = parser.parse_args()
    result = run_master(args.date, args.phase)
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

