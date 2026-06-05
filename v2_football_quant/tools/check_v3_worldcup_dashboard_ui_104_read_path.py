#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "data/runtime/dashboard/v3_worldcup_wc10_war_room.html"
READ_MODEL = ROOT / "data/manual_sources/v3_worldcup/war_room/v3_wc2026_dashboard_104_read_model.json"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_dashboard_ui_104_read_path_20260605.json"

READ_MODEL_URL = "/data/manual_sources/v3_worldcup/war_room/v3_wc2026_dashboard_104_read_model.json"
OLD_WC10_URL = "/data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
OLD_72_SOURCE = "v3_wc_match_cards.json"
APPROVED_V4_UI_TEXT_STAGE = "v2_football_quant/data/runtime/dashboard/v4_control_center.html"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def main() -> int:
    failures: list[str] = []
    html = HTML.read_text(encoding="utf-8", errors="ignore") if HTML.exists() else ""
    model = load_json(READ_MODEL)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).stdout.splitlines() if line.strip()]

    add(failures, HTML.exists(), "dashboard_html_missing", str(HTML))
    add(failures, READ_MODEL.exists(), "dashboard_104_read_model_missing", str(READ_MODEL))
    add(failures, READ_MODEL_URL in html, "ui_not_fetching_dashboard_104_read_model", READ_MODEL_URL)
    add(failures, OLD_WC10_URL not in html, "ui_still_fetches_old_wc10_source", OLD_WC10_URL)
    add(failures, "dashboard_read_model==='V3_WC_2026_DASHBOARD_104_READ_MODEL'" in html, "ui_read_model_branch_missing")
    add(failures, "GROUP_STAGE_ONLY_72" in html, "group_stage_72_label_missing")
    add(failures, "STRUCTURAL_SLOT_PLACEHOLDER" in html, "knockout_placeholder_label_missing")
    add(failures, "STRUCTURAL_ONLY_NO_TEAM_GENERATED" in html, "knockout_no_team_policy_missing")
    add(failures, "READ_CANONICAL_104_OR_GROUP_VIEW_72_NOT_BOTH_AS_COMPLETE" in html, "double_read_guard_missing")
    direct_72_fetch = bool(re.search(r"fetch\([^)]*v3_wc_match_cards\.json", html))
    add(failures, not direct_72_fetch, "ui_reads_72_source_directly", OLD_72_SOURCE)

    add(failures, model.get("dashboard_read_model") == "V3_WC_2026_DASHBOARD_104_READ_MODEL", "read_model_name_unexpected", model.get("dashboard_read_model"))
    add(failures, model.get("canonical_scope") == "FULL_TOURNAMENT_104_INDEX", "canonical_scope_unexpected", model.get("canonical_scope"))
    add(failures, model.get("canonical_card_count") == 104, "canonical_card_count_unexpected", model.get("canonical_card_count"))
    group = model.get("group_stage_view") if isinstance(model.get("group_stage_view"), dict) else {}
    add(failures, group.get("scope") == "GROUP_STAGE_ONLY_72", "group_scope_unexpected", group)
    add(failures, group.get("match_count") == 72, "group_match_count_unexpected", group)
    add(failures, group.get("do_not_treat_as_complete_source") is True, "group_complete_guard_missing", group)
    knockout = model.get("knockout_slots") if isinstance(model.get("knockout_slots"), dict) else {}
    add(failures, knockout.get("count") == 32, "knockout_count_unexpected", knockout)
    add(failures, knockout.get("display_mode") == "STRUCTURAL_SLOT_PLACEHOLDER", "knockout_display_mode_unexpected", knockout)
    add(failures, knockout.get("policy") == "STRUCTURAL_ONLY_NO_TEAM_GENERATED", "knockout_policy_unexpected", knockout)
    safety = model.get("safety") if isinstance(model.get("safety"), dict) else {}
    expected_safety = {
        "observation_only": True,
        "no_starting_xi_generated": True,
        "no_prediction": True,
        "no_injury_judgment": True,
        "betting_recommendation": False,
        "affects_v4": False,
    }
    for key, expected in expected_safety.items():
        add(failures, safety.get(key) is expected, f"safety_{key}_unexpected", safety.get(key))

    runtime_staged = [path for path in staged if re.search(r"(^|/)(cache|logs?|tmp|status)(/|$)|\.log$|\.lock$|\.pid$", path, re.I)]
    v4_staged = [
        path for path in staged
        if path != APPROVED_V4_UI_TEXT_STAGE
        and re.search(r"(^|/)(v4_|V4_|check_v4|build_v4|run_v4|engine/v4|scripts/v4|docs/V4)", path)
    ]
    add(failures, not runtime_staged, "runtime_cache_log_status_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    secrets = secret_hits([HTML, READ_MODEL, Path(__file__).resolve()])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "ui_read_path": READ_MODEL_URL,
        "old_wc10_fetch_present": OLD_WC10_URL in html,
        "direct_72_fetch_present": direct_72_fetch,
        "canonical_card_count": model.get("canonical_card_count"),
        "group_stage_match_count": model.get("group_stage_match_count"),
        "knockout_slot_count": model.get("knockout_slot_count"),
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
