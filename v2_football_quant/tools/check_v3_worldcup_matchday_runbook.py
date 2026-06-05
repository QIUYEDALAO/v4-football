#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs/V3_WC_2026_MATCHDAY_RUNBOOK_20260605.md"
SIM_CHECK = ROOT / "tools/check_v3_worldcup_matchday_brief_simulation.py"
LIVE_GUARD = ROOT / "tools/check_v3_worldcup_live_data_readiness_guard.py"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_matchday_runbook_20260605.json"

TIMEPOINTS = ["T-24h", "T-6h", "T-90m", "T-60m", "T-30m"]
OUTPUT_TERMS = ["赔率观察", "首发状态", "当前缺口", "赛前简报"]
WAIT_EVENTS = ["官方首发", "官方伤停确认源", "原生开盘/收盘", "淘汰赛真实对阵"]
MOBILE_SECTIONS = [
    "比赛信息",
    "战备状态",
    "阵容状态",
    "场馆/环境",
    "赔率观察",
    "当前缺口",
    "结论：仅观察，不推荐",
]
REQUIRED_SAFE_TEXT = [
    "WAIT_OFFICIAL_LINEUP",
    "first_seen_odds",
    "last_pre_kickoff_odds",
    "odds_observation_delta",
    "observation_only=true",
    "betting_recommendation=false",
    "affects_v4=false",
    "不调用 live API",
    "不生成预测首发",
    "不生成投注建议",
    "不生成盘口/资金流结论",
    "不影响 V4 official",
]
DISALLOWED_TEXT = [
    "生成预测首发",
    "生成投注建议",
    "生成资金流结论",
    "生成盘口变化结论",
    "调用 live API",
    "推荐下注",
    "投注建议：",
    "资金流信号",
    "盘口结论",
]
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def staged_files() -> list[str]:
    result = git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def has_disallowed_assertion(text: str, phrase: str) -> bool:
    for line in text.splitlines():
        if phrase not in line:
            continue
        if "禁止" in line or "不" in line:
            continue
        return True
    return False


def main() -> int:
    text = RUNBOOK.read_text(encoding="utf-8", errors="ignore") if RUNBOOK.exists() else ""
    failures: list[str] = []

    add(failures, RUNBOOK.exists(), "runbook_missing", str(RUNBOOK.relative_to(ROOT)))
    add(failures, SIM_CHECK.exists(), "brief_checker_missing", str(SIM_CHECK.relative_to(ROOT)))
    add(failures, LIVE_GUARD.exists(), "live_guard_missing", str(LIVE_GUARD.relative_to(ROOT)))
    for item in TIMEPOINTS:
        add(failures, item in text, "timepoint_missing", item)
    for item in OUTPUT_TERMS:
        add(failures, item in text, "output_term_missing", item)
    for item in WAIT_EVENTS:
        add(failures, item in text and "WAIT_EVENT" in text, "wait_event_missing", item)
    for item in MOBILE_SECTIONS:
        add(failures, item in text, "mobile_section_missing", item)
    for item in REQUIRED_SAFE_TEXT:
        add(failures, item in text, "safe_text_missing", item)
    for item in DISALLOWED_TEXT:
        add(failures, not has_disallowed_assertion(text, item), "disallowed_text", item)

    staged = staged_files()
    runtime_staged = [path for path in staged if re.search(r"(^|/)(runtime|cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
    v4_staged = [path for path in staged if re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    secrets = secret_hits([RUNBOOK, Path(__file__).resolve()])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "runbook": str(RUNBOOK.relative_to(ROOT)),
        "timepoints": TIMEPOINTS,
        "outputs": OUTPUT_TERMS,
        "wait_events": WAIT_EVENTS,
        "runtime_staged": runtime_staged,
        "v4_staged": v4_staged,
        "secret_hits": secrets,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
