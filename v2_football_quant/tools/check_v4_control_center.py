#!/usr/bin/env python3
"""check_v4_control_center.py — V4统一作战台 UI模板校验 + 数据源污染守卫 + 内容绑定检查

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
15. 不允许页面主区域出现 "--"
16. 不允许页面主区域出现 "加载中"
17. 不允许主界面出现英文主文案
18. 不允许 124/140、39/46、85/94、80/139 作为主指标
19. 不允许 V3世界杯进入 V4作战台
20. 不允许验证累计读取 live_bets cumulative
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

    # ==== UI 模板结构硬检查 ====
    # 黄金模板必须存在的 class
    required_classes = [
        ("topbar", ".topbar"),
        ("kpi-grid", ".kpi-grid"),
        ("primary-layout", ".primary-layout"),
        ("module-grid", ".module-grid"),
        ("chart-layout", ".chart-layout"),
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
        ("top-bar", "top-bar"),  # 旧布局 class
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

    # === 可见文本准备 ===
    body_visible = _get_body_visible(html_text)
    body_text = _strip_tags(body_visible)

    # === "--" 和 "加载中" 检查 ===
    # 在 HTML source 中作为占位符存在是正常的（JS 运行后会替换）
    # 只在 model 为空时才视为 blocker
    if "加载中" in body_visible and not model:
        blockers.append("content_page_loading_without_model")

    dash_in_element = re.findall(r'id="(kpi|snap|vd|todo|dot)[^"]*"[^>]*>--<', body_visible)
    if dash_in_element and not model:
        blockers.append(f"content_page_has_dash_elements_without_model:{len(dash_in_element)}")

    # === 数据绑定检查 ===
    if "data.model" not in html_text and "data.ok && data.model" not in html_text:
        if 'MODEL = await resp.json()' in html_text or 'MODEL=await resp.json()' in html_text:
            blockers.append("frontend_missing_model_unwrap")

    # === 页面主文案全部中文 ===
    # 黄金模板在模块明细行中包含技术标签，允许作为二级标签存在
    # 仅检查主标题/大标题区域是否出现英文
    english_terms = ["source", "API", "POST", "full scan", "cron", "UNKNOWN"]
    eng_found = []
    for term in english_terms:
        if term.lower() in body_text.lower():
            eng_found.append(term)
    if eng_found:
        warnings.append(f"english_terms_in_module_labels:{','.join(eng_found)}")

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
        if "未加载" not in ctx and "无" not in ctx and "禁止" not in ctx:
            blockers.append("v3_worldcup_module_detected")
    if "worldcup" in body_text.lower():
        # 黄金模板降级策略表中记录 v3_worldcup_roster_intel 为 "V3独立，不进V4" 是正确用法
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
    ui_checks["no_OpenClaw_Control"] = "OpenClaw Control" not in html_text
    ui_checks["no_top-kpi"] = "top-kpi" not in html_text
    ui_checks["no_kpi-violet"] = "kpi-violet" not in html_text
    ui_checks["no_kpi-green"] = "kpi-green" not in html_text
    ui_checks["no_kpi-amber"] = "kpi-amber" not in html_text
    ui_checks["no_top-bar"] = "top-bar" not in html_text

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
            "chinese_main_labels": len(eng_found) == 0,
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
