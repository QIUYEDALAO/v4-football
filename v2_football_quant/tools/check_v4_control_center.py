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

    if not ok_api:
        model_files = sorted(STATUS.glob("v4_control_center_model_*.json"))
        if model_files:
            api_obj = _load_json(model_files[-1])
            warnings.append(f"api_model_unavailable_using_local_model:{api_err}")
        else:
            blockers.append(f"api_model_unavailable:{api_err}")
    if not ok_127:
        page_127 = html
        warnings.append(f"page_8766_unavailable_using_local_html:{page_127_err}")

    model = api_obj.get("model", api_obj) if isinstance(api_obj, dict) else {}
    if not isinstance(model, dict) or not model:
        blockers.append("model_empty_or_invalid")

    # The Control Center is the only formal dashboard entry. Legacy dashboard
    # names must not flow back into its builder, HTML, or canonical model.
    builder_text = (ROOT / "tools/build_v4_control_center_model.py").read_text(encoding="utf-8", errors="ignore")
    canonical_text = json.dumps(model, ensure_ascii=False)
    forbidden_formal_tokens = ["v3v4_dashboard_candidate_view", "intel_ops_console", "after_scan_refresh"]
    for token in forbidden_formal_tokens:
        if token in builder_text:
            blockers.append(f"legacy_token_in_control_center_builder:{token}")
        if token in html:
            blockers.append(f"legacy_token_in_control_center_html:{token}")
        if token in canonical_text:
            blockers.append(f"legacy_token_in_control_center_model:{token}")

    durable = model.get("durable_runner", {})
    if not isinstance(durable, dict):
        blockers.append("durable_runner_status_not_dict")
        durable = {}
    for field in [
        "runner_installed", "launchd_loaded", "isolated_session_dependency",
        "openclaw_1200_mode", "next_action", "last_scheduled_scan", "last_completed_scan",
        "last_exit_code", "active_lock", "heartbeat_age_seconds",
        "catch_up_required",
    ]:
        if field not in durable:
            blockers.append(f"durable_runner_field_missing:{field}")
    for token in [
        "runner installed/template only", "last scheduled scan", "last completed scan",
        "last exit code", "active lock", "heartbeat age", "catch-up required",
        "isolated session dependency", "OpenClaw 12:00 mode", "launchd loaded", "next action",
    ]:
        if token not in html:
            blockers.append(f"durable_runner_html_missing:{token}")

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
            if any(not str(it.get("market_advice_display") or "").strip() for it in items if isinstance(it, dict)):
                warnings.append(f"candidate_default_fields_null_without_display_fallback:{','.join(sorted(set(null_in_items)))}")
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

    # 11) D2 UX refinement contract
    d2_required = [
        "单场结论",
        "正式等级",
        "盘口证据",
        "近况 / 交锋",
        "赛季阶段",
        "对阵：",
        "原始队名：",
        "暂无真实进球分布。",
        "不支持原因：",
        "联赛长期表现",
        "仅观察，不自动影响评级",
        "长期低命中预警，不自动排除",
        "今日无 official A/B",
        "shadow observation",
        "不推 QQ、不写 pending",
        "投注风控卡",
        "只做展示和入口，不自动下单，不写 live bet",
        "goNav('league')",
        "id=\"navSystem\"",
    ]
    for token in d2_required:
        if token not in html:
            blockers.append(f"d2_ux_token_missing:{token}")
    if "id=\"navError\"" in html or ">异常</button>" in html:
        blockers.append("d2_error_tab_not_merged_into_system")
    for tab_name in ["总览", "联赛", "投注", "验证", "复盘", "系统"]:
        if tab_name not in html:
            blockers.append(f"d2_bottom_tab_missing:{tab_name}")
    audit = model.get("audit", {}) if isinstance(model, dict) else {}
    if audit.get("strategy_changed") is not False:
        blockers.append("audit_strategy_changed_not_false")
    if audit.get("QQ_recommendation_pushed") is not False:
        blockers.append("audit_qq_push_not_false")
    if audit.get("validation_recomputed") is not False:
        blockers.append("audit_validation_recomputed_not_false")
    if audit.get("cron_schedule_modified") is not False:
        blockers.append("audit_cron_modified_not_false")

    # 12) D3 validation review sync contract
    d3_required = [
        "昨日验证复盘摘要",
        "20260531 联赛验证快照",
        "pending/postponed 不作为 miss",
        "不自动修改默认规则、A/B阈值、正式等级",
    ]
    for token in d3_required:
        if token not in html:
            blockers.append(f"d3_validation_sync_token_missing:{token}")
    latest_review = model.get("latest_validation_review", {}) if isinstance(model, dict) else {}
    if latest_review.get("validation_date") != "20260531":
        blockers.append("d3_latest_validation_review_date_not_20260531")
    if (latest_review.get("AB_hit_miss_rate") or {}).get("display") != "25/36 = 69.4%":
        blockers.append("d3_latest_validation_review_ab_rate_mismatch")

    # 13) League ledger A1 fix display contract
    league_a1_required = [
        "延期/未完赛，仅记录，不进分母",
        "样本不足，不下结论，仅观察",
        "样本偏少，仅辅助参考",
        "长期低命中预警，不自动排除",
        "KEEP / WATCH / OBSERVE 仅为展示标签，不自动改评级",
    ]
    for token in league_a1_required:
        if token not in html:
            blockers.append(f"league_a1_display_token_missing:{token}")
    if "official_grade = league" in html or "grade = league" in html:
        blockers.append("league_tag_mixed_into_official_grade")

    # 15) 20260602 readability contract for the real 8766 entrypoint.
    rops = next((x for x in items if isinstance(x, dict) and str(x.get("home_en") or x.get("home")) == "Rops" and str(x.get("away_en") or x.get("away")) == "OLS"), {})
    if rops:
        expected_model = {
            "match_display": "罗瓦涅米RoPS vs 奥卢OLS",
            "original_match": "Rops vs OLS",
            "league_display": "芬甲 / Finland Ykkonen",
            "grade_display": "B级候选",
            "candidate_status_display": "待关注",
            "market_advice_display": "0.75 / 150",
            "technical_audit_display": "RF C，盘后 C",
            "data_gap_display": "进球分布不可用",
        }
        for key, expected in expected_model.items():
            if str(rops.get(key) or "") != expected:
                blockers.append(f"readability_model_{key}_mismatch:{rops.get(key)}")
        if "数据源未返回进球时间分布" not in str(rops.get("unsupported_reason") or rops.get("goal_distribution_missing_reason") or ""):
            blockers.append("readability_model_goal_distribution_reason_missing")
    elif items:
        blockers.append("readability_rops_model_item_missing")

    today = model.get("top_status", {}).get("today_candidates", {})
    if {
        "A": today.get("A"),
        "B": today.get("B"),
        "SKIP": today.get("SKIP"),
        "scan_total": today.get("scan_total"),
    } != {"A": 0, "B": 1, "SKIP": 9, "scan_total": 10}:
        blockers.append(f"canonical_20260602_counts_mismatch:{today}")

    # 14) D4 league intelligence panel contract
    d4_required = [
        "联赛情报",
        "total leagues",
        "LOW_TRUST_ALERT 不自动排除",
        "DO_NOT_CONCLUDE：样本不足，不下结论",
        "PENDING_ONLY：延期/未完赛，仅记录，不进分母",
        "趋势仅供观察，不自动改规则",
        "当前仅有 baseline 快照，不能判断趋势。",
        "趋势快照异常，已阻断展示",
    ]
    for token in d4_required:
        if token not in html:
            blockers.append(f"d4_league_intel_token_missing:{token}")
    lip = model.get("league_intelligence_panel", {}) if isinstance(model, dict) else {}
    if not isinstance(lip, dict) or not lip:
        blockers.append("d4_league_intelligence_panel_missing")

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
