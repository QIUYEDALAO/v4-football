"""
V4 OpenClaw brief — 开门简报
每天 V4 扫描后自动生成并推送 QQ Bot
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.v4_match_intelligence import explain_match
try:
    from engine.team_cn_map import strict_match as team_name_cn
except Exception:
    def team_name_cn(name: str) -> str:
        return name

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
H2H_DATA_GAP_NOTE = "资料缺口：H2H样本不足，不参与评分。"


def _date_key(date_str: str) -> str:
    return str(date_str).replace("-", "")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _pct(v: Any) -> str:
    try:
        return f"{float(v) * 100:.0f}%"
    except Exception:
        return "-"


def _pct_value(numer: int, denom: int) -> str:
    return f"{(numer / denom * 100):.1f}%" if denom else "0.0%"


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _prev_key(key: str) -> str:
    try:
        d = datetime.strptime(key, "%Y%m%d").date()
        return (d - timedelta(days=1)).strftime("%Y%m%d")
    except Exception:
        return key


def _row_time(rec: dict[str, Any]) -> str:
    kickoff = str(rec.get("kickoff") or rec.get("date") or "")
    if not kickoff:
        return "-"
    try:
        dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return kickoff[-16:-3] if len(kickoff) >= 16 else kickoff


def _collect_rows(scout: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in scout:
        intel = explain_match(rec)
        ht_rec = intel.get("ht_recommendation") or {}
        f = rec.get("factors", {}) or {}
        scores = rec.get("market_scores") or f.get("market_scores") or {}
        grade = str(ht_rec.get("grade") or "SKIP").upper()
        tb = ht_rec.get("time_bins") or {}
        rows.append(
            {
                "fixture_id": rec.get("fixture_id"),
                "home": team_name_cn(rec.get("home") or "-"),
                "away": team_name_cn(rec.get("away") or "-"),
                "league": rec.get("league") or "-",
                "time": _row_time(rec),
                "grade": grade,
                "ht_score": _float(ht_rec.get("ht_score") or scores.get("HT_LIVE_OVER")),
                "h2h_rate": _float(ht_rec.get("h2h_ht_goal_rate") or f.get("h2h_ht_goal_rate")),
                "avg_goals": _float(ht_rec.get("ht_avg_goals") or f.get("h2h_avg_ht_goals")),
                "sample_size": int(_float(ht_rec.get("sample_size") or f.get("h2h_sample_size"))),
                "script_type": ht_rec.get("script_type") or "-",
                "time_bins": {
                    "0_15": _float(tb.get("0_15")),
                    "16_30": _float(tb.get("16_30")),
                    "31_45": _float(tb.get("31_45")),
                },
                "reasons": ht_rec.get("reasons") or [],
                "risks": ht_rec.get("risks") or [],
            }
        )
    rows.sort(key=lambda x: (x["time"], x["league"], x["home"]))
    return rows


def _skip_reason_key(reason: str) -> str:
    s = str(reason)
    if "HT有球率" in s or "有球率" in s:
        return "HT有球率不足"
    if "场均" in s or "进球" in s:
        return "上半场场均进球不足"
    if "11-45" in s or "压力" in s:
        return "11-45分钟压力不足"
    if "样本" in s:
        return "样本不足"
    if "方向" in s or "下半场" in s:
        return "方向更偏下半场"
    if "early_only" in s or "早球" in s:
        return "早球型风险"
    if "pullback" in s or "回调" in s:
        return "回调适配偏弱"
    return s[:24] if s else "其他"


def _format_card(r: dict[str, Any]) -> str:
    tb = r["time_bins"]
    reasons = " / ".join(r["reasons"][:3]) if r["reasons"] else "-"
    risks = " / ".join(r["risks"][:1]) if r["risks"] else "-"
    return (
        f"{r['home']} vs {r['away']}\n"
        f" {r['league']} · {r['time']} · #{r['fixture_id']}\n"
        f" HT评分 {r['ht_score']:.0f} | HT有球率 {_pct(r['h2h_rate'])} | 场均HT进球 {r['avg_goals']:.2f} | 样本 {r['sample_size']}\n"
        f" 剧本：{r['script_type']}\n"
        f" 分布：0-15m {_pct(tb['0_15'])} | 16-30m {_pct(tb['16_30'])} | 31-45m {_pct(tb['31_45'])}\n"
        f" 主因：{reasons}\n"
        f" 风险：{risks}"
    )


def _build_brief_legacy(date_str: str) -> str:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if isinstance(scout, dict):
        scout = scout.get("results") or []
    if not isinstance(scout, list):
        scout = []

    rows = _collect_rows(scout)
    a_rows = [r for r in rows if r["grade"] == "A"]
    b_rows = [r for r in rows if r["grade"] == "B"]
    c_rows = [r for r in rows if r["grade"] == "C"]
    skip_rows = [r for r in rows if r["grade"] == "SKIP"]
    total = len(rows)
    ab_total = len(a_rows) + len(b_rows)
    ab_ratio = _pct_value(ab_total, total)

    skip_counter: Counter[str] = Counter()
    for r in skip_rows:
        reasons = r.get("reasons", [])
        for reason in reasons[:2]:
            skip_counter[_skip_reason_key(reason)] += 1

    sep = "━" * 40
    lines: list[str] = []
    lines.append("【V4 情报系统】")
    lines.append(f"⏰ V4 上半场情报扫描 — {key}")
    lines.append("")
    lines.append("📊 统计概览")
    lines.append(f"🔥 A级强推荐：{len(a_rows)}场")
    lines.append(f"🟢 B级达标推荐：{len(b_rows)}场")
    lines.append(f"👁️ C级观察：{len(c_rows)}场")
    lines.append(f"⚪ HT_SKIP跳过：{len(skip_rows)}场")
    lines.append(f"🌎 全量扫描：{total}场")
    lines.append(f"📊 A+B覆盖率：{ab_ratio}")
    lines.append(sep)

    # A级
    if a_rows:
        for r in a_rows:
            lines.append("")
            lines.append("🔥 A级上半场强推荐")
            lines.append(_format_card(r))
            lines.append(sep)
    else:
        lines.append("")
        lines.append("🔥 A级上半场强推荐：(无)")
        lines.append(sep)

    # B级
    if b_rows:
        for r in b_rows:
            lines.append("")
            lines.append("🟢 B级上半场达标推荐")
            lines.append(_format_card(r))
            lines.append(sep)
    else:
        lines.append("")
        lines.append("🟢 B级上半场达标推荐：(无)")
        lines.append(sep)

    # C级
    lines.append("")
    lines.append(f"👁️ C级观察池：{len(c_rows)}场")
    if c_rows:
        for r in c_rows:
            lines.append(f"{r['home']} vs {r['away']} — {r['league']} {r['time']} | HT{r['ht_score']:.0f} | {_pct(r['h2h_rate'])} | {r['script_type']}")
    else:
        lines.append("(无)")
    lines.append(sep)

    # SKIP
    lines.append("")
    lines.append(f"⚪ 跳过统计：{len(skip_rows)}场")
    if skip_counter:
        for reason, n in skip_counter.most_common(6):
            lines.append(f"- {reason}：{n}场")
    lines.append(sep)

    # 昨日验证 — 仅来源于 V4复盘 guard PASS 结果
    # 禁止使用 validation / attribution 全量样本反推
    prev = _prev_key(key)
    guard_path = STATUS_DIR / f"v4_review_guard_{prev}.json"
    review_qq_path = REPORT_DIR / f"v4_review_qq_{prev}.txt"
    review_struct_path = REPORT_DIR / f"v4_review_structured_{prev}.json"
    guard = _load_json(guard_path, {})
    guard_ok = guard.get("guard_status") == "PASS"
    lines.append("")
    lines.append("📌 昨日验证（V4复盘）")
    if guard_ok and review_qq_path.exists():
        review_text = review_qq_path.read_text(encoding="utf-8")
        # 从 review_qq 提取 A/B/C/SKIP 概况
        ab_match = re.search(r"[🟢🔥]?\s*(A/B|A级|A|推荐)[^：]*[：:]\s*(\d+)场", review_text)
        c_match = re.search(r"[👁️]?\s*(C级|C|观察)[^：]*[：:]\s*(\d+)场", review_text)
        skip_match = re.search(r"[⚪]?\s*(跳过|SKIP)[^：]*[：:]\s*(\d+)场", review_text)
        if ab_match:
            lines.append(f"A/B推荐：{ab_match.group(2)}场")
        if c_match:
            lines.append(f"C级观察：{c_match.group(2)}场")
        if skip_match:
            lines.append(f"跳过：{skip_match.group(2)}场")
        # 从结构化数据读取命中概要
        struct_data = _load_json(review_struct_path, {})
        if struct_data:
            verdict = struct_data.get("verdict_summary") or struct_data.get("summary") or {}
            hit = verdict.get("hits", verdict.get("hit", 0))
            total = verdict.get("total", verdict.get("completed", 0))
            if total > 0:
                pct = round(hit / total * 100, 1)
                lines.append(f"A/B/C 命中率：{hit}/{total}（{pct}%）")
    else:
        guard_status = guard.get("guard_status", "MISSING")
        lines.append(f"V4正式复盘未完成，等待复盘链路（guard_status={guard_status}）")
        # 不生成 A/B/C 命中率
    lines.append(sep)

    # 异常样本 — 仅来自 review_structured，不来自 attribution
    anomaly_rows = []
    struct_data = _load_json(review_struct_path, {})
    if struct_data:
        anomaly_rows = struct_data.get("anomalies", struct_data.get("flagged", [])) or []
    if anomaly_rows:
        lines.append("")
        lines.append("⚠️ 昨日异常样本")
        if anomaly_rows:
            for idx, r in enumerate(anomaly_rows[:3], 1):
                reason = ", ".join((r.get("event_noise") or [])[:2]) or "无明显事件噪音"
                lines.append(
                    f"{idx}. {team_name_cn(r.get('home') or '-')} vs {team_name_cn(r.get('away') or '-')}\n"
                    f"   结果：{r.get('model_result')} | 诊断：{r.get('diagnosis')}\n"
                    f"   干扰：{reason}"
                )
        else:
            lines.append("无明显异常样本")
        lines.append(sep)

    lines.append("")
    if ab_total:
        lines.append(f"今日 V4 有 {ab_total} 场上半场推荐，其中 A级{len(a_rows)}场，B级{len(b_rows)}场。")
    else:
        lines.append("今日 V4 无A/B上半场主推荐。")
    lines.append("")
    lines.append("---")
    lines.append("⚠️ 本简报为V4最终结论。禁止追加任何旧口径/交叉参考/独立分析。")

    out_path = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    return "\n".join(lines)


def _kickoff_label(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return "-"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return s[-16:-3] if len(s) >= 16 else s


def _brief_line(item: dict[str, Any]) -> str:
    home = team_name_cn(str(item.get("home") or item.get("home_team") or "-"))
    away = team_name_cn(str(item.get("away") or item.get("away_team") or "-"))
    league = str(item.get("league") or item.get("league_name") or "-")
    kickoff = _kickoff_label(item.get("kickoff") or item.get("kickoff_time"))
    grade = str(item.get("official_grade") or item.get("grade") or "-").upper()
    rf_score = item.get("rf_shadow_score")
    market_grade = str(item.get("market_adjusted_shadow_grade") or "-").upper()
    reason = str(item.get("official_reason") or item.get("market_adjustment_reason") or "无")
    return (
        f"- {home} vs {away}｜{league}｜{kickoff}｜{grade}\n"
        f"  rf_score={rf_score if rf_score is not None else '-'}｜shadow={market_grade}\n"
        f"  原因：{reason}"
    )


def _build_brief_season_aware(date_str: str, candidate_view_path: Path | None = None) -> str:
    key = _date_key(date_str)
    cv_path = candidate_view_path or (STATUS_DIR / f"v4_official_candidate_view_{key}.json")
    cv = _load_json(cv_path, {})
    if not isinstance(cv, dict):
        cv = {}
    mode = str(cv.get("production_grade_mode") or "season_aware_rf")
    source = str(cv.get("official_grade_source") or "market_adjusted_shadow_grade")

    a_rows_raw = cv.get("A_candidates") or []
    b_rows_raw = cv.get("B_candidates") or []
    a_rows = [
        r for r in a_rows_raw
        if isinstance(r, dict)
        and str(r.get("official_grade") or r.get("grade") or "").upper() == "A"
        and bool(r.get("official_candidate", True))
    ]
    b_rows = [
        r for r in b_rows_raw
        if isinstance(r, dict)
        and str(r.get("official_grade") or r.get("grade") or "").upper() == "B"
        and bool(r.get("official_candidate", True))
    ]
    c_count = int(cv.get("C_count", 0) or 0)
    skip_count = int(cv.get("SKIP_count", 0) or 0)
    skip_rows = [r for r in (cv.get("SKIP_candidates") or []) if isinstance(r, dict)]
    total = int(cv.get("scan_total", len(a_rows) + len(b_rows) + c_count + skip_count) or 0)
    ab_total = len(a_rows) + len(b_rows)
    ab_ratio = _pct_value(ab_total, total)
    skip_counter: Counter[str] = Counter()
    h2h_gap_count = 0
    for row in skip_rows:
        reason = str(row.get("reason") or row.get("skip_reason") or row.get("filter_reason") or "").strip()
        if reason:
            skip_counter[reason] += 1
        if row.get("h2h_data_gap") or row.get("h2h_data_gap_note"):
            h2h_gap_count += 1

    lines: list[str] = []
    lines.append("【V4 情报系统】")
    lines.append(f"V4上半场情报 · {mode} 正式推荐")
    lines.append(f"日期：{key}")
    lines.append(f"production_grade_mode={mode}")
    lines.append(f"official_grade_source={source}")
    lines.append("")
    lines.append("📊 概览")
    lines.append(f"A级强推荐：{len(a_rows)}场")
    lines.append(f"B级达标推荐：{len(b_rows)}场")
    lines.append(f"C级观察：{c_count}场（不进主推荐）")
    lines.append(f"HT_SKIP跳过：{skip_count}场")
    lines.append(f"全量扫描：{total}场｜A+B覆盖率：{ab_ratio}")
    lines.append("━" * 40)

    if a_rows:
        lines.append("🔥 A级强推荐")
        for r in a_rows:
            lines.append(_brief_line(r))
        lines.append("━" * 40)
    else:
        lines.append("🔥 A级强推荐：(无)")
        lines.append("━" * 40)

    if b_rows:
        lines.append("🟢 B级达标推荐")
        for r in b_rows:
            lines.append(_brief_line(r))
        lines.append("━" * 40)
    else:
        lines.append("🟢 B级达标推荐：(无)")
        lines.append("━" * 40)

    if ab_total == 0:
        lines.append("今日无A/B上半场主推荐。")
    else:
        lines.append(f"V4最终结论：今日 A/B 主推荐 {ab_total} 场（A={len(a_rows)}, B={len(b_rows)}）。")
    if skip_count:
        lines.append("")
        lines.append(f"⚪ 跳过归因：{skip_count}场")
        if skip_counter:
            for reason, n in skip_counter.most_common(6):
                lines.append(f"- {reason}：{n}场")
        if h2h_gap_count:
            lines.append(f"- {H2H_DATA_GAP_NOTE}：{h2h_gap_count}场")
    lines.append("风险提示：仅 official A/B 可作为主推荐；C观察、影子条目、演练条目不进入主推荐。")
    lines.append("⚠️ V4最终结论以 official A/B 为准。")

    text = "\n".join(lines)
    out_path = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return text


def build_brief(
    date_str: str,
    production_grade_mode: str = "official_legacy",
    candidate_view_path: Path | None = None,
) -> str:
    mode = str(production_grade_mode or "official_legacy").strip().lower()
    if mode == "season_aware_rf":
        return _build_brief_season_aware(date_str, candidate_view_path=candidate_view_path)
    return _build_brief_legacy(date_str)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument(
        "--production-grade-mode",
        default="official_legacy",
        choices=["official_legacy", "season_aware_rf"],
        help="Brief mode. season_aware_rf reads official A/B from candidate_view.",
    )
    parser.add_argument("--candidate-view-path", default="", help="Optional candidate_view path override")
    args = parser.parse_args()
    cv_path = Path(args.candidate_view_path) if args.candidate_view_path else None
    print(build_brief(args.date, production_grade_mode=args.production_grade_mode, candidate_view_path=cv_path))


if __name__ == "__main__":
    main()
