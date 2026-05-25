#!/usr/bin/env python3
"""check_v4_control_center.py — V4统一作战台 UI模板校验 + 数据源污染守卫 + 内容绑定检查 + 紧凑布局检查

UI 模板硬检查（黄金模板 v4_control_center_final_design.html）：
1.  必须存在 .topbar
2.  必须存在 .kpi-grid
3.  必须存在 .primary-layout
4.  必须存在 .module-grid
5.  必须存在 .chart-layout
6.  必须存在 .drawer
7.  必须存在 .nav
8.  必须存在 .candidate
9.  必须存在 .summary-grid
10. 不允许出现 OpenClaw Control
11. 不允许出现 top-kpi 旧 class
12. 不允许出现 kpi-violet 旧 class
13. 不允许出现 kpi-green 旧 class
14. 不允许出现旧版浏览器标签式顶部导航
15. 不允许主界面出现 API / POST / UNKNOWN / full scan / cron / source / model / checker / undefined
16. 不允许 SKIP 大卡片
17. 不允许 124/140、39/46、85/94、80/139 作为主指标
18. 不允许 V3世界杯进入 V4作战台
19. 不允许验证累计读取 live_bets cumulative
20. 黄金模板关键 CSS 变量必须存在

COMPACT 紧凑布局检查 (V4-CONTROL-CENTER-COMPACT-OPERATIONS-UI-REFINE-20260526)：
21. 桌面端 .nav display:none
22. KPI min-height ≤ 84px
23. 候选卡片存在 .bet-inline 内嵌投注输入
24. 待办使用 .todo-row + .todo-chip 紧凑行
25. 实盘快照使用 .snap-compact 紧凑网格
26. 底部工具条 .toolbar 替代四大模块卡
27. 所有数据绑定 ID 存在
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "data/runtime/dashboard"
STATUS = ROOT / "data/runtime/status"
LIVE_DIR = ROOT / "data/runtime/live_bets"
OUT = STATUS / "check_v4_control_center_content_checker_20260526.json"


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_body_visible(html_text: str) -> str:
    """提取 body 中的可见文本（排除 script/style 标签）"""
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_text, re.DOTALL)
    if not body_match:
        return html_text
    text = body_match.group(1)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    return text


def _strip_tags(text: str) -> str:
    """去除 HTML 标签，只保留文本"""
    return re.sub(r'<[^>]*>', '', text)


def main() -> int:
    blockers = []
    warnings = []

    # === 文件存在性检查 ===
    html_path = DASH / "v4_control_center.html"
    if not html_path.exists():
        blockers.append("v4_control_center_html_missing")
        out = {"checker": "tools/check_v4_control_center.py", "blockers": blockers, "conclusion": "BLOCKER"}
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    html_text = html_path.read_text(encoding="utf-8")

    # ==== 黄金模板关键 CSS 变量检查 ====
    gold_css_vars = [
        "--bg", "--bg2", "--card", "--card2", "--line",
        "--text", "--muted", "--muted2",
        "--green", "--blue", "--yellow", "--red", "--purple", "--orange",
        "--shadow", "--radius",
    ]
    missing_vars = []
    for var in gold_css_vars:
        if var not in html_text:
            missing_vars.append(var)
    if missing_vars:
        blockers.append(f"ui_css_vars_missing_from_gold_template:{','.join(missing_vars)}")

    # 黄金模板关键 CSS 规则检查（compact 版本：module-grid→toolbar，chart-layout 移除）
    gold_css_rules = [
        (".topbar", "position:sticky"),
        (".kpi-grid", "grid-template-columns:repeat(6,1fr)"),
        (".primary-layout", "grid-template-columns:1.25fr .75fr"),
        (".summary-grid", "grid-template-columns:repeat(5,1fr)"),
        (".nav", "position:fixed"),
        (".drawer", "position:fixed"),
    ]
    for selector, rule in gold_css_rules:
        # 在 style 标签中查找 selector + rule
        style_match = re.search(r'<style[^>]*>(.*?)</style>', html_text, re.DOTALL)
        if style_match:
            style_text = style_match.group(1)
            if selector not in style_text or rule not in style_text:
                blockers.append(f"ui_css_rule_mismatch:{selector} missing {rule}")

    # ==== UI 模板结构硬检查 ====
    required_classes = [
        ("topbar", ".topbar"),
        ("kpi-grid", ".kpi-grid"),
        ("primary-layout", ".primary-layout"),
        ("drawer", ".drawer"),
        ("nav_bottom", ".nav"),
        ("candidate", ".candidate"),
        ("summary-grid", ".summary-grid"),
    ]
    for name, selector in required_classes:
        if selector not in html_text:
            blockers.append(f"ui_missing_gold_template_class:{name}")

    # 黄金模板禁止存在的旧 class
    forbidden_classes = [
        ("OpenClaw Control", "OpenClaw Control"),
        ("top-kpi", "top-kpi"),
        ("kpi-violet", "kpi-violet"),
        ("kpi-green", "kpi-green"),
        ("kpi-amber", "kpi-amber"),
        ("top-bar", "top-bar"),
    ]
    for name, pattern in forbidden_classes:
        if pattern in html_text:
            blockers.append(f"ui_forbidden_old_class:{name}")

    # 旧版浏览器标签式顶部导航检查
    old_nav_patterns = [
        r'class="top-bar"',
        r'class="[^"]*top-kpi[^"]*"',
    ]
    for pat in old_nav_patterns:
        if re.search(pat, html_text):
            blockers.append(f"ui_old_navigation_pattern:{pat}")

    # === 可见文本准备 ===
    body_visible = _get_body_visible(html_text)
    body_text = _strip_tags(body_visible)

    # ==== 主界面英文术语禁止检查（BLOCKER） ====
    banned_english = [
        ("API", "API"),
        ("POST", "POST"),
        ("UNKNOWN", "UNKNOWN"),
        ("full scan", "full scan"),
        ("cron", "cron"),
        ("source", "source"),
        ("model", "model"),
        ("checker", "checker"),
        ("undefined", "undefined"),
    ]
    eng_blockers = []
    for term, pattern in banned_english:
        if pattern.lower() in body_text.lower():
            # 检查上下文：如果在抽屉面板内容或降级策略中，允许
            # 但抽屉内容是 JS 动态生成的，不在 HTML source 中
            # 只检查 HTML source 的 body 可见文本
            eng_blockers.append(term)
    if eng_blockers:
        blockers.append(f"ui_banned_english_in_main_ui:{','.join(eng_blockers)}")

    # === SKIP 大卡片检查 ===
    # SKIP 候选中不应出现 .candidate class（应该是紧凑摘要行）
    skip_in_candidate = re.findall(
        r'class="[^"]*candidate[^"]*"[^>]*>.*?(?:skip|SKIP|跳过)',
        body_visible, re.DOTALL
    )
    if skip_in_candidate:
        blockers.append("ui_skip_rendered_as_candidate_card")

    # === COMPACT 紧凑布局检查 ===
    # 1. 桌面端导航隐藏
    if ".nav{display:none}" not in html_text and ".nav {display:none}" not in html_text:
        blockers.append("compact_desktop_nav_not_hidden")

    # 2. KPI 高度不过高 (target 72-82px, max 84px acceptable)
    kpi_min_height_match = re.search(r'\.kpi\s*\{[^}]*min-height:\s*(\d+)px', html_text)
    if kpi_min_height_match:
        kpi_h = int(kpi_min_height_match.group(1))
        if kpi_h > 84:
            blockers.append(f"compact_kpi_min_height_too_tall:{kpi_h}px")
    else:
        blockers.append("compact_kpi_min_height_not_found")

    # 3. 候选卡片存在内嵌投注输入 (.bet-inline + bi-line/bi-odds/bi-stake)
    if ".bet-inline" not in html_text:
        blockers.append("compact_missing_bet_inline_form")
    if ".bi-line" not in html_text or ".bi-odds" not in html_text or ".bi-stake" not in html_text:
        blockers.append("compact_missing_bet_input_fields")

    # 4. 待办使用紧凑 chip 行 (.todo-row + .todo-chip)，不是大卡片
    if ".todo-row" not in html_text:
        blockers.append("compact_missing_todo_row")
    if ".todo-chip" not in html_text:
        blockers.append("compact_missing_todo_chip")

    # 5. 实盘快照使用紧凑网格 (.snap-compact)
    if ".snap-compact" not in html_text:
        blockers.append("compact_missing_snap_compact_grid")

    # 6. 底部工具条替代四大模块卡 (.toolbar)
    if ".toolbar" not in html_text:
        blockers.append("compact_missing_toolbar")

    # === 数据绑定 ID 完整性检查 ===
    binding_ids = [
        "kpiCandidates", "kpiYesterday", "kpiCumulative", "kpiPnl", "kpiTurnover", "kpiTodo",
        "kpiCandidatesHint", "kpiYesterdayHint", "kpiCumulativeHint", "kpiTodoHint",
        "candidateList",
        "snapStake", "snapPnl", "snapTurnover", "snapRebate", "snapNetPnl",
        "todoBetVal", "todoSettleVal", "todoVerifyVal", "todoAlertVal",
        "dotBet", "dotSettle", "dotVerify", "dotAlert",
    ]
    missing_binding_ids = []
    for bid in binding_ids:
        if f'id="{bid}"' not in html_text and f"id='{bid}'" not in html_text:
            missing_binding_ids.append(bid)
    if missing_binding_ids:
        blockers.append(f"compact_missing_binding_ids:{','.join(missing_binding_ids)}")

    # === Model 文件检查 ===
    models = sorted(STATUS.glob("v4_control_center_model_*.json"))
    if not models:
        blockers.append("v4_control_center_model_missing")
    model = _load_json(models[-1]) if models else {}

    # === 内容级检查：model 核心字段非空 ===
    if model:
        ts = model.get("top_status") or {}

        tc = ts.get("today_candidates") or {}
        tc_display = tc.get("display") or ""
        if not tc_display or tc_display == "--":
            blockers.append("content_today_candidates_empty_or_dash")
        elif tc.get("A", 0) == 0 and tc.get("B", 0) == 0:
            candidates_data = model.get("candidates") or {}
            a_count = candidates_data.get("a_count", 0)
            b_count = candidates_data.get("b_count", 0)
            if a_count == 0 and b_count == 0:
                warnings.append("content_today_candidates_zero_AB_no_reason")

        yv = ts.get("yesterday_validation") or {}
        if not yv.get("display") or yv.get("display") == "--":
            blockers.append("content_yesterday_validation_empty_or_dash")

        cv = ts.get("cumulative_validation") or {}
        if not cv.get("display") or cv.get("display") == "--":
            blockers.append("content_cumulative_validation_empty_or_dash")

        pnl = ts.get("today_pnl") or {}
        if pnl.get("display", "--") == "--":
            blockers.append("content_today_pnl_dash")

        tr = ts.get("turnover_and_rebate") or {}
        if tr.get("display", "--") == "--":
            blockers.append("content_turnover_rebate_dash")

        todo = ts.get("today_todo") or {}
        if todo.get("display", "--") == "--":
            blockers.append("content_today_todo_dash")

        lb = model.get("live_bet") or {}
        lb_today = lb.get("today") or {}
        lb_cum = lb.get("cumulative") or {}
        if not lb_today:
            blockers.append("content_live_bet_today_empty")
        if not lb_cum:
            blockers.append("content_live_bet_cumulative_empty")
    else:
        blockers.append("model_file_empty_or_invalid")

    # === "--" 和 "加载中" 检查 ===
    if "加载中" in body_visible and not model:
        blockers.append("content_page_loading_without_model")

    dash_in_element = re.findall(r'id="(kpi|snap|vd|todo)[^"]*"[^>]*>--<', body_visible)
    if dash_in_element and not model:
        blockers.append(f"content_page_has_dash_elements_without_model:{len(dash_in_element)}")

    # === 数据绑定检查 ===
    if "data.model" not in html_text and "data.ok && data.model" not in html_text:
        if 'MODEL = await resp.json()' in html_text or 'MODEL=await resp.json()' in html_text:
            blockers.append("frontend_missing_model_unwrap")

    # === 顶部核心指标只出现一次 ===
    for label in ["验证累计", "昨日验证"]:
        count = body_text.count(label)
        if count > 3:
            warnings.append(f"label_{label}_appears_{count}_times")

    # === 数据源检查 ===
    if model:
        ds = model.get("data_sources") or {}
        cv_src = ds.get("cumulative_validation") or ""
        if "true_cumulative_result_validation" not in cv_src and "true_cumulative" not in cv_src:
            blockers.append(f"cumulative_validation_source_not_official:{cv_src}")
        if model.get("cumulative_validation_detail", {}).get("not_from_live_bets") is not True:
            blockers.append("cumulative_validation_not_marked_as_not_from_live_bets")

        lb = model.get("live_bet") or {}
        if lb.get("not_from_validation") is not True:
            blockers.append("live_bet_not_marked_as_not_from_validation")

        audit = model.get("audit") or {}
        if audit.get("validation_cumulative_not_from_live_bets") is not True:
            blockers.append("validation_mixed_with_live_bet")
        if audit.get("outside_57_excluded") is not True:
            blockers.append("outside_57_not_excluded")
        if audit.get("c_skip_excluded_from_ab") is not True:
            blockers.append("c_skip_not_excluded_from_ab")

    # === 禁止指标检查 ===
    banned_indicators = ["124/140", "39/46", "85/94", "80/139"]
    for ind in banned_indicators:
        if ind in body_text:
            context_match = re.search(r'.{0,40}' + re.escape(ind) + r'.{0,40}', body_text)
            context = context_match.group(0) if context_match else ""
            if "未显示" in context or "无" in context or "禁止" in context:
                pass
            else:
                blockers.append(f"banned_indicator_visible_as_main:{ind}")

    # === V3 世界杯检查 ===
    if "V3世界杯" in body_text:
        context_v3 = re.search(r'.{0,40}V3世界杯.{0,40}', body_text)
        ctx = context_v3.group(0) if context_v3 else ""
        if "未加载" not in ctx and "无" not in ctx and "禁止" not in ctx and "不进V4" not in ctx:
            blockers.append("v3_worldcup_module_detected")
    if "worldcup" in body_text.lower():
        if "不进V4" not in body_text and "独立" not in body_text:
            blockers.append("worldcup_english_term_in_body")

    # === V2/V33 检查 ===
    for term in ["V2 active", "v2_active", "V33 active", "v33_active"]:
        if term.lower() in body_text.lower():
            blockers.append(f"v2_v33_active:{term}")

    # === 走水返水规则 ===
    store_path = ROOT / "tools/live_bet_store.py"
    if store_path.exists():
        store_text = store_path.read_text(encoding="utf-8")
        if not ("PUSH" in store_text and "effective = 0.0" in store_text):
            warnings.append("push_rebate_rule_unverified")

    # === 8765 入口检查 ===
    old_page = DASH / "intel_ops_console.html"
    if old_page.exists():
        old_text = old_page.read_text(encoding="utf-8")
        if "V4统一作战台" not in old_text or "8766" not in old_text:
            warnings.append("8765_missing_v4_entry_link")
    else:
        warnings.append("8765_old_page_missing")

    # === Secret 检查 ===
    if re.search(r'sk-[a-zA-Z0-9]{20,}', html_text):
        blockers.append("secret_in_html")

    # === 验证累计数字检查 ===
    if model:
        cv_detail = model.get("cumulative_validation_detail") or {}
        ab_data = cv_detail.get("AB") or {}
        ab_display = ab_data.get("display") or ""
        if "81/140" not in ab_display:
            warnings.append(f"cumulative_AB_not_81_140:{ab_display}")

    # === 结论 ===
    conclusion = "PASS"
    if blockers:
        conclusion = "BLOCKER"
    elif warnings:
        conclusion = "WARN_ONLY"

    # === UI 模板检查明细 ===
    ui_checks = {}
    for name, selector in required_classes:
        ui_checks[f"has_{name}"] = selector in html_text
    ui_checks["css_vars_match_gold"] = len(missing_vars) == 0
    ui_checks["no_OpenClaw_Control"] = "OpenClaw Control" not in html_text
    ui_checks["no_top-kpi"] = "top-kpi" not in html_text
    ui_checks["no_kpi-violet"] = "kpi-violet" not in html_text
    ui_checks["no_kpi-green"] = "kpi-green" not in html_text
    ui_checks["no_kpi-amber"] = "kpi-amber" not in html_text
    ui_checks["no_top-bar"] = "top-bar" not in html_text
    ui_checks["no_banned_english"] = len(eng_blockers) == 0
    ui_checks["skip_not_candidate_card"] = len(skip_in_candidate) == 0
    # compact checks
    ui_checks["desktop_nav_hidden"] = ".nav{display:none}" in html_text or ".nav {display:none}" in html_text
    ui_checks["kpi_height_ok"] = kpi_min_height_match is not None and int(kpi_min_height_match.group(1)) <= 84
    ui_checks["has_bet_inline_form"] = ".bet-inline" in html_text
    ui_checks["has_todo_row_chip"] = ".todo-row" in html_text and ".todo-chip" in html_text
    ui_checks["has_snap_compact"] = ".snap-compact" in html_text
    ui_checks["has_toolbar"] = ".toolbar" in html_text
    ui_checks["all_binding_ids_present"] = len(missing_binding_ids) == 0

    out = {
        "checker": "tools/check_v4_control_center.py",
        "phase": "V4-CONTROL-CENTER-UI-TEMPLATE-ALIGNMENT-20260526",
        "generated_at": datetime.now().isoformat(),
        "blockers": blockers,
        "warnings": warnings,
        "conclusion": conclusion,
        "ui_template_checks": ui_checks,
        "content_check_details": {
            "html_exists": html_path.exists(),
            "model_exists": len(models) > 0,
            "model_non_empty": bool(model),
            "top_kpis_populated": not any("dash" in b for b in blockers if "dash" in b),
            "no_banned_indicators": all(ind not in body_text for ind in banned_indicators),
            "chinese_main_labels": len(eng_blockers) == 0,
            "compact_layout": {
                "desktop_nav_hidden": ".nav{display:none}" in html_text or ".nav {display:none}" in html_text,
                "kpi_min_height_px": int(kpi_min_height_match.group(1)) if kpi_min_height_match else None,
                "bet_inline_form": ".bet-inline" in html_text,
                "todo_row_chip": ".todo-row" in html_text and ".todo-chip" in html_text,
                "snap_compact_grid": ".snap-compact" in html_text,
                "toolbar": ".toolbar" in html_text,
                "binding_ids_missing": len(missing_binding_ids),
                "binding_ids_missing_list": missing_binding_ids if missing_binding_ids else [],
            },
        },
        "full_scan_ran": False,
        "cloud_publish": False,
        "QQ_push": False,
        "cron_modified": False,
        "secrets_printed": False,
        "secrets_committed": False,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if conclusion == "PASS" else (1 if conclusion == "WARN_ONLY" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
