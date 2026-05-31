#!/usr/bin/env python3
"""engine/v4_qq_formatter.py — V4简报QQ版 v2.1
新版要求：
- A/B全量展开（B级不再截断）
- 每场含开赛时间、联赛、等级、HT评分、HT率、预估、剧本、分布
- B级每场之间有分隔线
- C/SKIP只汇总
- 昨日验证显示正式复盘结果
- 滚动观察含样本数
- 中文队名/联赛名规范化
- 无机器字段
- 无"重点A级前2"
- 有结束标记
"""
import json, sys, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
# Use deterministic Chinese normalizer
try:
    from engine.v4_display_name_normalizer import display_name, find_untranslated, _TEAM_CN as GLOBAL_TEAM_CN, _LEAGUE_CN
except Exception:
    def display_name(n, is_league=False):
        return n
    def find_untranslated(text):
        return []
SEP = "━" * 20
SUB_SEP = "━" * 16
LOCAL_TZ = timezone(timedelta(hours=8))
def _cn(name):
    return display_name(name)
def _league_cn(name):
    return display_name(name, is_league=True)
def _num(kw, full):
    for l in full.split("\n"):
        if kw in l:
            val = l.split("：")[-1].replace("场","").strip()
            if val and val[0].isdigit():
                return val
    return "?"
def _parse_matches(full, bucket_label, bucket_id, end_markers):
    parts = full.split(bucket_label)
    matches = []
    for part in parts[1:]:
        end_pos = len(part)
        for m in end_markers:
            pos = part.find(m)
            if pos >= 0 and pos < end_pos:
                end_pos = pos
        chunk = part[:end_pos]
        lines = chunk.strip().split("\n")
        if len(lines) < 2:
            continue
        match_line = lines[0].strip()
        pair_match = re.match(r"(.+?)\s+vs\s+(.+)", match_line)
        if not pair_match:
            continue
        home = pair_match.group(1).strip()
        away = pair_match.group(2).strip()
        league = ""
        kickoff = ""
        if len(lines) > 1:
            meta = lines[1].strip()
            parts_m = meta.split("·")
            if len(parts_m) >= 3:
                league = parts_m[0].strip()
                kickoff = parts_m[1].strip()
            elif len(parts_m) == 2:
                league = parts_m[0].strip()
                kickoff = parts_m[1].strip()
        full_text = chunk
        ht_m = re.search(r"HT评分 (\d+)", full_text)
        ht_score = ht_m.group(1) if ht_m else ""
        rate_m = re.search(r"HT有球率 (\d+%)", full_text)
        ht_rate = rate_m.group(1) if rate_m else ""
        goal_m = re.search(r"场均HT进球 ([\d.]+)", full_text)
        avg_goal = goal_m.group(1) if goal_m else ""
        script_m = re.search(r"剧本：(.+)", full_text)
        script = script_m.group(1).strip() if script_m else ""
        dist_m = re.search(r"分布：([0-9].+)", full_text)
        dist = dist_m.group(1).strip() if dist_m else ""
        # dist stored raw, cleaned during format_qq_step
        # Normalize: 0-15m 40%/16-30m 30%/31-45m 50%
        matches.append({
            "home": home, "away": away, "league": league, "kickoff": kickoff,
            "bucket": bucket_id, "ht_score": ht_score, "ht_rate": ht_rate,
            "avg_goal": avg_goal, "script": script, "distribution": dist,
        })
    return matches
def _ratio_to_pct(rate_str):
    if not rate_str or rate_str in ("N/A", "?") or "/" not in str(rate_str):
        return rate_str
    parts = str(rate_str).split("/")
    if len(parts) != 2:
        return rate_str
    try:
        n = float(parts[0])
        d = float(parts[1])
        if d == 0:
            return "N/A"
        pct = n / d * 100
        return f"{int(pct)}%" if pct == int(pct) else f"{pct:.1f}%"
    except (ValueError, ZeroDivisionError):
        return rate_str
def _extract_mode_source(full: str) -> tuple[str, str]:
    mode = "season_aware_rf"
    source = "market_adjusted_shadow_grade"
    m = re.search(r"production_grade_mode\s*=\s*([A-Za-z0-9_\-]+)", full)
    if m:
        mode = m.group(1).strip()
    s = re.search(r"official_grade_source\s*=\s*([A-Za-z0-9_\-]+)", full)
    if s:
        source = s.group(1).strip()
    return mode, source


def _parse_official_rows_from_candidate_view(key: str) -> tuple[list[dict], list[dict], dict]:
    cv_path = STATUS_DIR / f"v3v4_dashboard_candidate_view_{key}.json"
    cv = {}
    if cv_path.exists():
        try:
            cv = json.loads(cv_path.read_text(encoding="utf-8"))
        except Exception:
            cv = {}
    if not isinstance(cv, dict):
        cv = {}

    def _row(item: dict) -> dict:
        return {
            "home": str(item.get("home") or item.get("home_team") or "-"),
            "away": str(item.get("away") or item.get("away_team") or "-"),
            "league": str(item.get("league") or item.get("league_name") or "-"),
            "kickoff": str(item.get("kickoff") or item.get("time") or "-"),
            "reason": str(item.get("official_reason") or item.get("market_adjustment_reason") or "无"),
            "rf_score": item.get("rf_shadow_score"),
        }

    a_rows_raw = cv.get("A_candidates") if isinstance(cv.get("A_candidates"), list) else []
    b_rows_raw = cv.get("B_candidates") if isinstance(cv.get("B_candidates"), list) else []
    a_rows = [
        _row(x) for x in a_rows_raw
        if isinstance(x, dict)
        and str(x.get("official_grade") or x.get("grade") or "").upper() == "A"
        and bool(x.get("official_candidate", True))
    ]
    b_rows = [
        _row(x) for x in b_rows_raw
        if isinstance(x, dict)
        and str(x.get("official_grade") or x.get("grade") or "").upper() == "B"
        and bool(x.get("official_candidate", True))
    ]
    return a_rows, b_rows, cv


def _format_official_qq(date_str: str, window: str = "midday") -> str:
    key = date_str.replace("-", "")
    bp = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
    if not bp.exists():
        return "V4简报未生成"
    full = bp.read_text().replace("\r\n", "\n")
    now = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
    window_cn = {"late": "凌晨", "early": "早场", "noon": "午间", "midday": "午间", "evening": "傍晚", "night": "晚间"}
    w_name = window_cn.get(window, window)
    mode, source = _extract_mode_source(full)
    a_rows, b_rows, cv = _parse_official_rows_from_candidate_view(key)
    a_count = int(cv.get("A_count", len(a_rows)) or 0) if isinstance(cv, dict) else len(a_rows)
    b_count = int(cv.get("B_count", len(b_rows)) or 0) if isinstance(cv, dict) else len(b_rows)
    total = int(cv.get("scan_total", 0) or 0) if isinstance(cv, dict) else 0

    lines: list[str] = []
    lines.append("【V4今日正式推荐】")
    lines.append(f"窗口：{w_name}")
    lines.append(f"日期：{key[:4]}-{key[4:6]}-{key[6:]}")
    lines.append(f"生成时间：{now}")
    lines.append(f"production_grade_mode={mode}")
    lines.append(f"official_grade_source={source}")
    lines.append("engine_default_rescue_threshold=73.5")
    if total > 0:
        lines.append(f"扫描{total}场｜A={a_count}｜B={b_count}")
    else:
        lines.append(f"A={a_count}｜B={b_count}")
    lines.append(SEP)

    if a_rows:
        lines.append(f"【A级{len(a_rows)}场】")
        for i, r in enumerate(a_rows, 1):
            lines.append(f"{i}. {_cn(r['home'])} vs {_cn(r['away'])}｜{_league_cn(r['league'])}｜{r['kickoff']}")
            lines.append(f"   原因：{r['reason']}")
        lines.append(SEP)
    else:
        lines.append("【A级0场】")
        lines.append(SEP)

    if b_rows:
        lines.append(f"【B级{len(b_rows)}场】")
        for i, r in enumerate(b_rows, 1):
            lines.append(f"{i}. {_cn(r['home'])} vs {_cn(r['away'])}｜{_league_cn(r['league'])}｜{r['kickoff']}")
            lines.append(f"   原因：{r['reason']}")
            if i < len(b_rows):
                lines.append(SUB_SEP)
        lines.append(SEP)
    else:
        lines.append("【B级0场】")
        lines.append(SEP)

    lines.append("风险提示：仅系统正式候选，不夸大胜率，不建议倍投。")
    lines.append("⚠️ 以 official A/B 为准，非正式观察条目不进入正式推荐。")
    return "\n".join(lines)


def format_qq(date_str: str, window: str = "midday", mode: str = "official_recommendation") -> str:
    mode_norm = str(mode or "official_recommendation").strip().lower()
    if mode_norm == "official_recommendation":
        result = _format_official_qq(date_str, window=window)
        key = date_str.replace("-", "")
        qq_path = REPORT_DIR / f"v4_openclaw_brief_qq_{key}.txt"
        qq_path.write_text(result, encoding="utf-8")
        return result

    key = date_str.replace("-","")
    bp = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
    if not bp.exists():
        return "V4简报未生成"
    full = bp.read_text().replace("\r\n","\n")
    now = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
    a_count = _num("A级强推荐", full)
    b_count = _num("B级达标推荐", full)
    c_count = _num("C级观察", full)
    s_count = _num("HT_SKIP跳过", full)
    total_full = _num("全量扫描", full)
    cov = _num("A+B覆盖率", full)
    # Map window names to Chinese
    window_cn = {"late": "凌晨", "early": "早场", "noon": "午间",
                 "midday": "午间", "evening": "傍晚", "night": "晚间"}
    w_name = window_cn.get(window, window)
    L = []
    L.append(f"【V4模板验收TEST｜非正式推荐】")
    L.append(f"窗口：{w_name}")
    L.append(f"来源日期：{key[:4]}-{key[4:6]}-{key[6:]}")
    L.append(f"生成时间：{now}")
    L.append(f"说明：模板实机验收，不代表今日正式推荐，请勿下注。")
    # Scan stats - distinguish scanned vs scout
    if total_full:
        L.append(f"扫描{total_full}场｜情报{total_full}场｜A{a_count} / B{b_count} / C{c_count} / SKIP{s_count}｜A+B覆盖{cov}")
    else:
        L.append(f"情报E场｜A{a_count} / B{b_count} / C{c_count} / SKIP{s_count}｜A+B覆盖{cov}")
    L.append(SEP)
    # Parse matches
    a_matches = _parse_matches(full, "A级上半场强推荐", "A", ["B级上半场达标推荐", "C级观察池", "━━━"])
    b_matches = _parse_matches(full, "B级上半场达标推荐", "B", ["C级观察池", "━━━"])
    # A section
    if a_matches:
        L.append(f"【A级{a_count}场】")
        for i, m in enumerate(a_matches):
            L.append(f"{i+1}. {_cn(m['home'])} vs {_cn(m['away'])}｜{_league_cn(m['league'])}｜{m['kickoff']}")
            detail = f"HT{m['ht_score']}｜{m['ht_rate']}｜{m['avg_goal']}球｜剧本：{m['script']}"
            if m['distribution']:
                detail += f"\n时段：{m['distribution']}"
            L.append(f"  {detail}")
            if i < len(a_matches) - 1:
                L.append(SUB_SEP)
        L.append(SEP)
    # B section - full list
    if b_matches:
        L.append(f"【B级{b_count}场】")
        for i, m in enumerate(b_matches):
            L.append(f"{i+1}. {_cn(m['home'])} vs {_cn(m['away'])}｜{_league_cn(m['league'])}｜{m['kickoff']}")
            detail = f"HT{m['ht_score']}｜{m['ht_rate']}｜{m['avg_goal']}球｜剧本：{m['script']}"
            if m['distribution']:
                detail += f"\n时段：{m['distribution']}"
            L.append(f"  {detail}")
            if i < len(b_matches) - 1:
                L.append(SUB_SEP)
        L.append(SEP)
    # C - summary
    c_section = full.split("C级观察池")[1].split("跳过统计")[0] if "C级观察池" in full else ""
    c_lines = re.findall(r"(.+?)\s+vs\s+(.+?) —", c_section)
    if c_lines:
        c_sample = " | ".join(f"{_cn(h)} vs {_cn(a)}" for h, a in c_lines[:5])
        L.append(f"【C级{c_count}场】仅观察，不展开。代表：{c_sample} 等{c_count}场。")
        L.append(SEP)
    # SKIP - summary
    skip_section = full.split("跳过统计")[1].split("━━")[0] if "跳过统计" in full else ""
    skip_reasons = re.findall(r"-\s*(.+?)[：:]\s*(\d+)场", skip_section)
    if skip_reasons:
        reasons = " | ".join(f"{k}{v}场" for k, v in skip_reasons[:5])
        L.append(f"【跳过原因】{reasons}")
        L.append(SEP)
    # 昨日验证
    prev_key = _prev_key(key)
    guard_path = STATUS_DIR / f"v4_review_guard_{prev_key}.json"
    guard_ok = False
    if guard_path.exists():
        try:
            gd = json.loads(guard_path.read_text())
            guard_ok = gd.get("guard_status") == "PASS"
        except Exception:
            pass
    L.append("【昨日验证】")
    if guard_ok:
        struct_path = REPORT_DIR / f"v4_review_structured_{prev_key}.json"
        if struct_path.exists():
            try:
                sd = json.loads(struct_path.read_text())
                sc = sd.get("summary", {})
                a_s = sc.get("a", {}); b_s = sc.get("b", {})
                c_s = sc.get("c", {}); s_s = sc.get("skip_backfire", 0)
                L.append(f"A级 {a_s.get('hit',0)}/{a_s.get('total',0)} · {_ratio_to_pct(a_s.get('rate','N/A'))}")
                L.append(f"B级 {b_s.get('hit',0)}/{b_s.get('total',0)} · {_ratio_to_pct(b_s.get('rate','N/A'))}")
                L.append(f"C级 {c_s.get('hit',0)}/{c_s.get('total',0)} · {_ratio_to_pct(c_s.get('rate','N/A'))}")
                skip_den = sc.get('skip_total', 0)
                L.append(f"SKIP反杀 {s_s}/{skip_den} · {_ratio_to_pct(str(s_s) + '/' + str(skip_den))}")
            except Exception:
                L.append("昨日复盘数据存在但读取失败")
        else:
            L.append("昨日复盘数据待加载")
    else:
        L.append("昨日复盘未完成 / guard未通过")
    L.append(SEP)
    # 滚动观察
    L.append("【滚动验证】")
    if guard_ok:
        struct_path = REPORT_DIR / f"v4_review_structured_{prev_key}.json"
        if struct_path.exists():
            try:
                sd = json.loads(struct_path.read_text())
                rs = sd.get("rolling_stats", {})
                ab = rs.get("7d_ab", "")
                c = rs.get("7d_c", "")
                sk = rs.get("7d_skip_backfire", "")
                L.append(f"近7天 A/B：{_ratio_to_pct(ab) if '/' in str(ab) else ab}")
                L.append(f"近7天 C级：{_ratio_to_pct(c) if '/' in str(c) else c}")
                L.append(f"近7天 SKIP反杀：{_ratio_to_pct(sk) if '/' in str(sk) else sk}")
                L.append("样本仅1个复盘日，仅观察，不改规则。")
            except Exception:
                L.append("样本不足，仅观察")
        else:
            L.append("样本不足，仅观察")
    else:
        L.append("样本不足，仅观察")
    L.append(SEP)
    # Conclusion - template-test mode only
    a_n = int(a_count) if a_count.isdigit() else 0
    b_n = int(b_count) if b_count.isdigit() else 0
    total_ab = a_n + b_n
    L.append(f"A/B共{total_ab}场。本消息仅为模板验收，不代表正式推送。")
    L.append("⚠️ V4最终结论以正式推送为准。禁止追加旧口径。")
    L.append("—— V4模板验收TEST结束 ——")
    result = "\n".join(L)
    # Find untranslated names for reporting
    untranslated = find_untranslated(result)
    if untranslated:
        pass  # Log silently - names will be added to alias table later
    qq_path = REPORT_DIR / f"v4_openclaw_brief_qq_{key}.txt"
    qq_path.write_text(result, encoding="utf-8")
    return result
def _prev_key(key):
    from datetime import datetime, timedelta
    try:
        d = datetime.strptime(key, "%Y%m%d").date()
        return (d - timedelta(days=1)).strftime("%Y%m%d")
    except Exception:
        return key
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--window", default="midday")
    p.add_argument("--mode", default="official_recommendation", choices=["official_recommendation", "template_test"])
    a = p.parse_args()
    print(format_qq(a.date, a.window, mode=a.mode))
