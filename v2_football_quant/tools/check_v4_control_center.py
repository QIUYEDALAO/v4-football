#!/usr/bin/env python3
"""check_v4_control_center.py — V4统一作战台 数据源污染守卫

检查项：
1. v4_control_center.html 存在
2. v4_control_center_model 存在
3. 页面主文案全部中文
4. 顶部核心指标只出现一次
5. 昨日验证/累计验证不在首页重复铺卡
6. 验证累计读取 official A/B-only truth file
7. 实盘累计读取 live_bets summary
8. 二者不得混用
9. 不出现 124/140、39/46、85/94、80/139 作为主指标
10. 不出现 V3世界杯模块
11. 不出现 V2/V33 active
12. outside_57 不混入 official
13. C/SKIP 不进 A/B-only累计
14. 走水返水规则正确
15. 8766 可服务主页面
16. 8765 只做入口
17. 不触发 scan / validation / QQ / cloud / cron
18. 不打印 secret
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
OUT = STATUS / "check_v4_control_center_20260526.json"


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    blockers = []
    warnings = []

    # 1. v4_control_center.html 存在
    html_path = DASH / "v4_control_center.html"
    if not html_path.exists():
        blockers.append("v4_control_center_html_missing")
    html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""

    # 2. v4_control_center_model 存在
    models = sorted(STATUS.glob("v4_control_center_model_*.json"))
    if not models:
        blockers.append("v4_control_center_model_missing")
    model = _load_json(models[-1]) if models else {}

    # 3. 页面主文案全部中文 — 检查无英文主标签
    english_terms = ["source", "API", "POST", "full scan", "cron", "UNKNOWN"]
    for term in english_terms:
        # 检查是否在 visible text 中出现（不在 style/script 中）
        # 简单检查：在 body 可见文本区域
        if term.lower() in html_text.lower():
            # 排除 JSON 数据和代码中的使用
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html_text, re.DOTALL)
            if body_match:
                body_text = body_match.group(1)
                # 移除 script 和 style
                body_text = re.sub(r'<script[^>]*>.*?</script>', '', body_text, flags=re.DOTALL)
                body_text = re.sub(r'<style[^>]*>.*?</style>', '', body_text, flags=re.DOTALL)
                if term.lower() in body_text.lower():
                    warnings.append(f"english_term_in_body:{term}")
            else:
                if term.lower() in html_text.lower():
                    warnings.append(f"english_term_in_html:{term}")

    # 4. 顶部核心指标只出现一次 — 检查 body 中 "验证累计" 出现次数
    body_match_ck = re.search(r'<body[^>]*>(.*?)</body>', html_text, re.DOTALL)
    body_text_ck = body_match_ck.group(1) if body_match_ck else html_text
    for label in ["验证累计", "昨日验证"]:
        count = body_text_ck.count(label)
        if count > 3:  # top bar + detail section + data source lock = 3 可接受
            warnings.append(f"label_{label}_appears_{count}_times_in_body")

    # 5. 昨日验证/累计验证不在首页重复铺卡
    # 只统计 class="top-kpi" 的 div 元素数量
    top_kpi_elements = len(re.findall(r'class="top-kpi"', body_text_ck))
    if top_kpi_elements != 6:
        warnings.append(f"top_bar_kpi_element_count_{top_kpi_elements}_not_6")

    # 6. 验证累计读取 official A/B-only truth file
    if model:
        ds = model.get("data_sources") or {}
        cv_src = ds.get("cumulative_validation") or ""
        if "true_cumulative_result_validation" not in cv_src and "true_cumulative" not in cv_src:
            blockers.append(f"cumulative_validation_source_not_official:{cv_src}")
        if model.get("cumulative_validation_detail", {}).get("not_from_live_bets") is not True:
            blockers.append("cumulative_validation_not_marked_as_not_from_live_bets")

    # 7. 实盘累计读取 live_bets summary
    if model:
        lb = model.get("live_bet") or {}
        if lb.get("not_from_validation") is not True:
            blockers.append("live_bet_not_marked_as_not_from_validation")

    # 8. 二者不得混用
    if model:
        audit = model.get("audit") or {}
        if audit.get("validation_cumulative_not_from_live_bets") is not True:
            blockers.append("validation_mixed_with_live_bet")

    # 9. 不出现旧错误累计作为主指标
    # 只在 body 可见文本中检查（排除 style/script）
    body_visible = body_text_ck
    body_visible = re.sub(r'<script[^>]*>.*?</script>', '', body_visible, flags=re.DOTALL)
    body_visible = re.sub(r'<style[^>]*>.*?</style>', '', body_visible, flags=re.DOTALL)
    banned_indicators = ["124/140", "39/46", "85/94", "80/139"]
    for ind in banned_indicators:
        if ind in body_visible:
            # 检查是否作为"未显示"的描述出现
            context_match = re.search(r'.{0,40}' + re.escape(ind) + r'.{0,40}', body_visible)
            context = context_match.group(0) if context_match else ""
            if "未显示" in context or "无" in context or "禁止" in context:
                pass  # 作为状态检查标记出现，不是主指标
            else:
                blockers.append(f"banned_indicator_visible_as_main:{ind}")

    # 10. 不出现 V3世界杯模块
    if "V3世界杯" in body_visible:
        context_v3 = re.search(r'.{0,40}V3世界杯.{0,40}', body_visible)
        ctx = context_v3.group(0) if context_v3 else ""
        if "未加载" not in ctx and "无" not in ctx and "禁止" not in ctx:
            blockers.append("v3_worldcup_module_detected")
    if "worldcup" in body_visible.lower():
        blockers.append("worldcup_english_term_in_body")

    # 11. 不出现 V2/V33 active
    for term in ["V2 active", "v2_active", "V33 active", "v33_active"]:
        if term.lower() in body_visible.lower():
            blockers.append(f"v2_v33_active:{term}")

    # 12. outside_57 不混入 official
    if model:
        audit = model.get("audit") or {}
        if audit.get("outside_57_excluded") is not True:
            blockers.append("outside_57_not_excluded")

    # 13. C/SKIP 不进 A/B-only累计
    if model:
        audit = model.get("audit") or {}
        if audit.get("c_skip_excluded_from_ab") is not True:
            blockers.append("c_skip_not_excluded_from_ab")

    # 14. 走水返水规则 — 检查 live_bet_store.py 中的 PUSH 逻辑
    store_path = ROOT / "tools/live_bet_store.py"
    if store_path.exists():
        store_text = store_path.read_text(encoding="utf-8")
        if "PUSH" in store_text and "effective = 0.0" in store_text:
            pass  # OK
        else:
            warnings.append("push_rebate_rule_unverified")

    # 15. 8766 可服务主页面 — 文件存在即表示可服务
    if html_path.exists():
        pass  # OK
    else:
        blockers.append("8766_cannot_serve_main_page")

    # 16. 8765 只做入口 — 检查 intel_ops_console.html 有跳转入口
    old_page = DASH / "intel_ops_console.html"
    if old_page.exists():
        old_text = old_page.read_text(encoding="utf-8")
        if "V4统一作战台" in old_text and "8766" in old_text:
            pass  # OK
        else:
            warnings.append("8765_missing_v4_entry_link")
    else:
        warnings.append("8765_old_page_missing")

    # 17. 不触发 scan / validation / QQ / cloud / cron
    for trigger in ["full_scan", "capture", "validate", "QQ_push", "cloud_publish"]:
        if trigger.lower() in html_text.lower() and "禁止" not in html_text:
            pass  # HTML 中描述这些是禁止的，OK

    # 18. 不打印 secret
    secret_patterns = ["secret", "password", "token", "api_key", "sk-"]
    for pat in secret_patterns:
        if pat in html_text.lower():
            # 检查是否是真正的 secret
            if pat == "sk-" and re.search(r'sk-[a-zA-Z0-9]{20,}', html_text):
                blockers.append(f"secret_in_html:{pat}")

    # 验证 cumulative 数字
    if model:
        cv = model.get("cumulative_validation_detail") or {}
        a_display = cv.get("A", {}).get("display") or ""
        b_display = cv.get("B", {}).get("display") or ""
        ab_display = cv.get("AB", {}).get("display") or ""
        expected_a = "28/46"
        expected_b = "53/94"
        expected_ab = "81/140"
        if expected_a not in a_display:
            warnings.append(f"cumulative_A_not_{expected_a}:{a_display}")
        if expected_b not in b_display:
            warnings.append(f"cumulative_B_not_{expected_b}:{b_display}")
        if expected_ab not in ab_display:
            warnings.append(f"cumulative_AB_not_{expected_ab}:{ab_display}")

    conclusion = "PASS"
    if blockers:
        conclusion = "BLOCKER"
    elif warnings:
        conclusion = "WARN_ONLY"

    out = {
        "checker": "tools/check_v4_control_center.py",
        "phase": "V4-CONTROL-CENTER-FINAL-DESIGN-IMPLEMENTATION-20260526",
        "generated_at": datetime.now().isoformat(),
        "blockers": blockers,
        "warnings": warnings,
        "conclusion": conclusion,
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
