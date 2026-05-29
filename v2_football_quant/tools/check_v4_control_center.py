#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "data/runtime/dashboard"
STATUS = ROOT / "data/runtime/status"
OUT = STATUS / "v4_control_center_codex_checker_20260526.json"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fetch_json(url: str) -> tuple[bool, dict, str]:
    try:
        raw = urllib.request.urlopen(url, timeout=8).read().decode("utf-8", "ignore")
        obj = json.loads(raw)
        return True, obj, ""
    except Exception as exc:
        return False, {}, str(exc)


def _fetch_text(url: str) -> tuple[bool, str, str]:
    try:
        txt = urllib.request.urlopen(url, timeout=8).read().decode("utf-8", "ignore")
        return True, txt, ""
    except Exception as exc:
        return False, "", str(exc)


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    html_path = DASH / "v4_control_center.html"
    if not html_path.exists():
        blockers.append("html_missing")
        OUT.write_text(json.dumps({"conclusion": "BLOCKER", "blockers": blockers}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(OUT.read_text(encoding="utf-8"))
        return 2

    html = html_path.read_text(encoding="utf-8", errors="ignore")
    ok_api, api_obj, api_err = _fetch_json("http://127.0.0.1:8766/api/v4_control_center_model")
    ok_127, page_127, page_127_err = _fetch_text("http://127.0.0.1:8766/v4_control_center.html")
    ok_8765, page_8765, page_8765_err = _fetch_text("http://127.0.0.1:8765/intel_ops_console.html")

    if not ok_api:
        blockers.append(f"api_model_unavailable:{api_err}")
    if not ok_127:
        blockers.append(f"page_8766_unavailable:{page_127_err}")
    if not ok_8765:
        warnings.append(f"page_8765_unavailable:{page_8765_err}")

    model = api_obj.get("model", api_obj) if isinstance(api_obj, dict) else {}
    if not isinstance(model, dict) or not model:
        blockers.append("model_empty_or_invalid")

    # 1) must have JS binding path
    required_js = [
        "function loadModel",
        "/api/v4_control_center_model",
        "function renderTop",
        "function renderCandidates",
        "function renderSide",
    ]
    for token in required_js:
        if token not in html:
            blockers.append(f"missing_js_binding:{token}")

    # 2) required anchors
    required_ids = [
        "kpiCandidates", "kpiCandidatesHint", "kpiYesterday", "kpiYesterdayHint",
        "kpiCumulative", "kpiCumulativeHint", "kpiPnl", "kpiTurnoverRebate", "kpiTodo", "kpiTodoHint",
        "candidateList", "skipLine",
        "todoBet", "todoSettle", "todoRetry", "todoError",
        "snapBankroll", "snapStake", "snapGross", "snapTurnover", "snapRebate", "snapNet",
        "sysState", "systemToolbarStatus",
    ]
    miss_ids = [x for x in required_ids if f'id="{x}"' not in html and f"id='{x}'" not in html]
    if miss_ids:
        blockers.append(f"missing_dom_ids:{','.join(miss_ids)}")

    # 3) undefined checks (content-level, not raw JS source token)
    html_no_script_style = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html_no_script_style = re.sub(r"<style[^>]*>.*?</style>", "", html_no_script_style, flags=re.DOTALL | re.IGNORECASE)
    plain_text = re.sub(r"<[^>]*>", " ", html_no_script_style)
    if re.search(r"\bundefined\b", plain_text, flags=re.IGNORECASE):
        blockers.append("undefined_in_html_content")
    if isinstance(api_obj, dict) and "undefined" in json.dumps(api_obj, ensure_ascii=False):
        blockers.append("undefined_in_api_json")

    # 4) KPI placeholder guard
    if re.search(r'id="kpi[^"]*"[^>]*>--<', html):
        blockers.append("kpi_placeholder_dash_detected")

    # 5) candidate field completeness
    cand = model.get("candidates", {})
    items = cand.get("items") or ((cand.get("a_candidates") or []) + (cand.get("b_candidates") or []))
    if not isinstance(items, list):
        blockers.append("candidate_items_not_list")
        items = []
    if items:
        need_fields = ["default_line", "default_odds", "default_stake", "default_entry_minute"]
        missing_in_items = [f for f in need_fields if any((f not in it) for it in items if isinstance(it, dict))]
        null_in_items = [f for f in need_fields if any((f in it and it.get(f) is None) for it in items if isinstance(it, dict))]
        if missing_in_items:
            blockers.append(f"candidate_default_fields_missing:{','.join(sorted(set(missing_in_items)))}")
        if null_in_items:
            warnings.append(f"candidate_default_fields_null_for_unbet:{','.join(sorted(set(null_in_items)))}")
    else:
        warnings.append("candidate_items_empty")

    # 6) skip must be summary line and not candidate card
    if "skip-line" not in html:
        blockers.append("skip_summary_line_missing")
    if 'id="skipLine"' in html and re.search(r'id="skipLine"[^>]*class="[^"]*candidate-card', html, re.IGNORECASE):
        blockers.append("skip_rendered_as_candidate_card")

    # 7) source guards
    ds = model.get("data_sources", {})
    cum_src = str(ds.get("cumulative_validation", ""))
    if "true_cumulative_result_validation" not in cum_src:
        blockers.append(f"cumulative_source_not_true_cumulative:{cum_src}")
    if model.get("cumulative_validation_detail", {}).get("not_from_live_bets") is not True:
        blockers.append("cumulative_mixed_with_live_bets")

    # 8) banned stale indicators / module
    merged_text = (page_127 or html)
    for tok in ["124/140", "39/46", "85/94", "80/139", "V3世界杯"]:
        if tok in merged_text:
            blockers.append(f"banned_token_visible:{tok}")

    # 9) style/layout unchanged lightweight guard: key class and CSS tokens exist
    for token in [".topbar", ".kpi-grid", ".primary-layout", ".candidate", ".cand-top", ".nav{"]:
        if token not in html:
            blockers.append(f"layout_css_token_missing:{token}")

    # 10) do not show technical words in body text
    body_text = plain_text
    for word in ["API", "POST", "UNKNOWN", "full scan", "cron", "source", "model", "checker"]:
        if word.lower() in body_text.lower():
            warnings.append(f"technical_word_visible:{word}")

    conclusion = "PASS"
    if blockers:
        conclusion = "BLOCKER"
    elif warnings:
        conclusion = "WARN_ONLY"

    out = {
        "checker": "tools/check_v4_control_center.py",
        "generated_at": datetime.now().isoformat(),
        "conclusion": conclusion,
        "blockers": blockers,
        "warnings": warnings,
        "checks": {
            "api_json_ok": ok_api,
            "page_8766_ok": ok_127,
            "page_8765_ok": ok_8765,
            "model_non_empty": bool(model),
            "anchor_count_required": len(required_ids),
            "anchor_missing_count": len(miss_ids),
            "candidate_items_count": len(items),
        },
        "full_scan_ran": False,
        "validation_recomputed": False,
        "QQ_push": False,
        "cloud_publish": False,
        "cron_modified": False,
        "secrets_printed": False,
        "secrets_committed": False,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if conclusion == "PASS" else (1 if conclusion == "WARN_ONLY" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
