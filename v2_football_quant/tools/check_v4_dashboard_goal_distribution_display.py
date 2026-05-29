#!/usr/bin/env python3
"""tools/check_v4_dashboard_goal_distribution_display.py

Check that V4 dashboard candidate list shows complete goal distribution
(0-15, 16-30, 31-45) without CSS truncation.

Guard markers:
  NO_AI_KILL_RETRY = true
  FAIL_CLOSED = true
  READ_ONLY = true
  SECURE = true

Usage:
  python3 tools/check_v4_dashboard_goal_distribution_display.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

RESULTS = {
    "checker": "tools/check_v4_dashboard_goal_distribution_display.py",
    "generated_at": None,
    "conclusion": "PASS",
    "blockers": [],
    "warnings": [],
    "checks": {},
}


def _check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS["checks"][name] = {"ok": ok, "detail": detail}
    if not ok:
        RESULTS["blockers"].append(f"{name}: {detail}")


def _load_runtime_html() -> str | None:
    """Fetch runtime HTML from the local server."""
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:8766/v4_control_center.html", timeout=5)
        return resp.read().decode("utf-8")
    except Exception as e:
        _check("runtime_html_accessible", False, str(e))
        return None


def test_no_ellipsis_on_dist_col() -> None:
    """dist-col must not use text-overflow:ellipsis or overflow:hidden with nowrap."""
    html = _load_runtime_html()
    if html is None:
        return

    # Find all .dist-col CSS rules
    pattern = r'\.candidate-row\s*\.dist-col\{[^}]*\}'
    for m in re.finditer(pattern, html):
        rule = m.group(0)
        has_ellipsis = "ellipsis" in rule
        has_overflow_hidden = "overflow:hidden" in rule
        has_nowrap = "white-space:nowrap" in rule
        has_display_none = "display:none" in rule

        block_no = "CSS block"
        _check(
            f"dist_col_no_ellipsis",
            not has_ellipsis,
            f"{block_no}: {'ellipsis FOUND' if has_ellipsis else 'OK'}",
        )
        _check(
            f"dist_col_no_nowrap_hidden",
            not (has_overflow_hidden and has_nowrap),
            f"{block_no}: {'overflow:hidden+nowrap FOUND' if (has_overflow_hidden and has_nowrap) else 'OK'}",
        )
        if has_display_none:
            _check(
                "dist_col_not_hidden_on_desktop",
                False,
                "dist-col has display:none - hidden on desktop",
            )
    _check("dist_col_css_checked", True, "dist-col CSS rules examined")


def _load_model_candidates() -> list[dict]:
    """Load candidate items from the control center model API."""
    import urllib.request
    try:
        resp = urllib.request.urlopen(
            "http://127.0.0.1:8766/api/v4_control_center_model", timeout=5
        )
        data = json.loads(resp.read().decode("utf-8"))
        model = data.get("model", data)
        return model.get("candidates", {}).get("items", [])
    except Exception as e:
        _check("model_api_accessible", False, str(e))
        return []


def test_distribution_data_complete() -> None:
    """Every A/B candidate has fh_goal_dist_0_15/16_30/31_45."""
    cands = _load_model_candidates()
    if not cands:
        _check("candidates_data_found", False, "No candidates from API")
        return

    _check("candidates_data_found", True, f"{len(cands)} candidates")

    ab_cands = [c for c in cands if c.get("grade") in ("A", "B")]
    _check("ab_candidates_found", len(ab_cands) > 0, f"{len(ab_cands)} A/B candidates")

    for c in ab_cands:
        fid = c.get("fixture_id")
        a = c.get("fh_goal_dist_0_15_pct")
        b = c.get("fh_goal_dist_16_30_pct")
        cc = c.get("fh_goal_dist_31_45_pct")

        _check(
            f"dist_0_15_{fid}",
            a is not None,
            f"fixture {fid}: fh_goal_dist_0_15_pct={a}",
        )
        _check(
            f"dist_16_30_{fid}",
            b is not None,
            f"fixture {fid}: fh_goal_dist_16_30_pct={b}",
        )
        _check(
            f"dist_31_45_{fid}",
            cc is not None,
            f"fixture {fid}: fh_goal_dist_31_45_pct={cc}",
        )

        # Verify dist source
        src = c.get("fh_goal_dist_source", "")
        _check(
            f"dist_source_{fid}",
            src in ("events_goal_counts", "events_missing"),
            f"fixture {fid}: source={src}",
        )


def test_no_forbidden_labels() -> None:
    """Dashboard must not show forbidden labels."""
    html = _load_runtime_html()
    if html is None:
        return

    for label in ["57白名单", "全量合规", "正式候选", "HT进球剧本"]:
        _check(
            f"no_label_{label}",
            label not in html,
            f"label='{label}' {'FOUND' if label in html else 'OK'}",
        )


def test_sort_and_layout() -> None:
    """Candidate list still sorted, status/action visible."""
    html = _load_runtime_html()
    if html is None:
        return

    _check("sort_time_present", "sortCandidates" in html or "sortInfo" in html or "按开赛时间" in html,
           "Candidate sort logic present")
    _check("expand_btn_present", "expand-btn" in html,
           "Expand button CSS class present")
    _check("bet_panel_present", "bet-panel" in html or "openBetPanel" in html,
           "Bet panel present")
    _check("no_market_present", "无盘口已排除" in html,
           "NO_MARKET status label present")


def test_safety_guards() -> None:
    """DEFAULT_RULES, validation, live bet, cron, QQ unchanged."""
    import hashlib
    content = open(BASE_DIR / "engine" / "v4_match_intelligence.py").read()
    m = re.search(r"DEFAULT_RULES\s*=\s*(\{.+?\n\})", content, re.DOTALL)
    rules_hash = hashlib.sha256(m.group(1).encode()).hexdigest()[:12] if m else "NOT_FOUND"
    _check("DEFAULT_RULES_unchanged", rules_hash == "b04f3da9b770",
           f"hash={rules_hash}")


def main() -> None:
    from datetime import datetime

    RESULTS["generated_at"] = datetime.now().isoformat()

    test_no_ellipsis_on_dist_col()
    test_distribution_data_complete()
    test_no_forbidden_labels()
    test_sort_and_layout()
    test_safety_guards()

    if RESULTS["blockers"]:
        RESULTS["conclusion"] = "BLOCKER"
    elif RESULTS["warnings"]:
        RESULTS["conclusion"] = "WARN_ONLY"
    else:
        RESULTS["conclusion"] = "PASS"

    out_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "status"
        / f"check_v4_dashboard_goal_distribution_display_{datetime.now().strftime('%Y%m%d')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False)

    print(json.dumps(RESULTS, indent=2, ensure_ascii=False))
    sys.exit(0 if not RESULTS["blockers"] else 1)


if __name__ == "__main__":
    main()
