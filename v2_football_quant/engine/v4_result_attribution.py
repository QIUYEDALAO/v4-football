"""
V4 赛后归因系统
================
仅用于复盘归因，不参与实时评分。

用法：
  python3 engine/v4_result_attribution.py --date 20260514
  python3 engine/v4_result_attribution.py --date 20260514 --fixture 123456
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine import net_utils
from engine.v4_match_intelligence import explain_match

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"


def _date_key(v: str) -> str:
    return str(v).replace("-", "")


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _api_get(endpoint: str) -> dict:
    return net_utils.api_get(endpoint) or {}


def _first_ht_goal_minute(events: list[dict]) -> tuple[int | None, str]:
    mins = []
    for ev in events:
        et = str(ev.get("type") or "").strip().lower()
        detail = str(ev.get("detail") or "").strip().lower()
        if et != "goal":
            continue
        elapsed = _safe_int((ev.get("time") or {}).get("elapsed"), -1)
        extra = _safe_int((ev.get("time") or {}).get("extra"), 0)
        if elapsed < 0:
            continue
        if elapsed > 45:
            continue
        if "missed" in detail or "cancel" in detail or "disallowed" in detail:
            continue
        # 45+N 记录为 45+N，用于补时噪音识别
        minute = elapsed + (extra if elapsed == 45 and extra > 0 else 0)
        mins.append(minute)
    if not mins:
        return None, "NONE"
    m = min(mins)
    if m <= 15:
        return m, "0_15"
    if m <= 30:
        return m, "16_30"
    return m, "31_45"


def _top_predicted_bucket(pred_bins: dict[str, float]) -> str:
    bins = {
        "0_15": _safe_float(pred_bins.get("0_15"), 0.0),
        "16_30": _safe_float(pred_bins.get("16_30"), 0.0),
        "31_45": _safe_float(pred_bins.get("31_45"), 0.0),
    }
    return max(bins, key=bins.get)


def _event_noise_tags(events: list[dict], first_ht_goal_minute: int | None) -> list[str]:
    tags: set[str] = set()
    for ev in events:
        et = str(ev.get("type") or "").strip().lower()
        detail = str(ev.get("detail") or "").strip().lower()
        elapsed = _safe_int((ev.get("time") or {}).get("elapsed"), -1)
        extra = _safe_int((ev.get("time") or {}).get("extra"), 0)
        minute = elapsed + (extra if elapsed == 45 and extra > 0 else 0)
        in_ht = elapsed >= 0 and elapsed <= 45
        if not in_ht:
            continue

        if et == "card" and ("red card" in detail or "second yellow" in detail):
            tags.add("RED_CARD")
        if et == "goal" and "penalty" in detail:
            tags.add("PENALTY")
        if et == "goal" and "own goal" in detail:
            tags.add("OWN_GOAL")
        if et == "var" and "penalty" in detail:
            tags.add("VAR_PENALTY")
        if et == "subst" and "injury" in detail:
            tags.add("INJURY_SUB")
        if et == "goal" and elapsed == 45 and extra >= 1:
            tags.add("LATE_STOPPAGE_GOAL")
    if first_ht_goal_minute is not None and first_ht_goal_minute <= 3:
        tags.add("EARLY_GOAL_RANDOM")
    return sorted(tags)


def _context_noise_tags(rec: dict) -> list[str]:
    tags: set[str] = set()
    ctx = rec.get("context_observation") or {}
    weather = ctx.get("weather") or {}
    pitch = ctx.get("pitch") or {}
    referee = ctx.get("referee") or {}

    w_text = json.dumps(weather, ensure_ascii=False).lower()
    p_text = json.dumps(pitch, ensure_ascii=False).lower()
    r_text = json.dumps(referee, ensure_ascii=False).lower()

    if "heavy rain" in w_text or "暴雨" in w_text or "大雨" in w_text:
        tags.add("HEAVY_RAIN")
    if "strong wind" in w_text or "大风" in w_text or _safe_float(weather.get("wind_speed"), 0.0) >= 10:
        tags.add("STRONG_WIND")
    temp_c = weather.get("temperature_c")
    if temp_c is not None and _safe_float(temp_c, 99.0) <= 0:
        tags.add("EXTREME_COLD")
    if any(x in p_text for x in ("bad", "poor", "mud", "waterlog", "烂", "湿滑")):
        tags.add("BAD_PITCH")
    if any(x in p_text for x in ("artificial", "turf", "人造草")):
        tags.add("ARTIFICIAL_TURF")
    if _safe_float(referee.get("avg_cards"), 0.0) >= 5.0 or "high card" in r_text or "高牌" in r_text:
        tags.add("REF_CARD_HIGH")
    if _safe_float(referee.get("avg_penalties"), 0.0) >= 0.35 or "high penalty" in r_text or "高点球" in r_text:
        tags.add("REF_PENALTY_HIGH")
    return sorted(tags)


def _model_result(pre_grade: str, ht_goal: bool) -> str:
    if pre_grade in ("A", "B", "C"):
        return "MODEL_HIT" if ht_goal else "MODEL_MISS"
    return "MODEL_SKIP_BACKFIRE" if ht_goal else "MODEL_SKIP_CORRECT"


def _diagnosis(
    pre_grade: str,
    ht_goal: bool,
    event_noise: list[str],
    context_noise: list[str],
    time_bin_source: str,
    pred_bins: dict[str, float],
    sample_size: int,
    coverage_level: str,
) -> str:
    noisy_win_tags = {"PENALTY", "OWN_GOAL", "LATE_STOPPAGE_GOAL", "VAR_PENALTY"}
    noisy_loss_tags = {"RED_CARD", "INJURY_SUB"}
    if sample_size < 3:
        return "DATA_QUALITY_ISSUE"
    if time_bin_source in ("NONE", "", "-"):
        return "DATA_QUALITY_ISSUE"
    if sum(_safe_float(v, 0.0) for v in pred_bins.values()) <= 0:
        return "DATA_QUALITY_ISSUE"
    if coverage_level in ("UNKNOWN", ""):
        return "DATA_QUALITY_ISSUE"

    if pre_grade in ("A", "B", "C") and ht_goal:
        if noisy_win_tags.intersection(event_noise):
            return "NOISY_WIN"
        return "MODEL_VALID"
    if pre_grade in ("A", "B", "C") and not ht_goal:
        if noisy_loss_tags.intersection(event_noise) or context_noise:
            return "NOISY_LOSS"
        return "MODEL_OVERCONFIDENT"
    if pre_grade == "SKIP" and ht_goal:
        if noisy_win_tags.intersection(event_noise) or noisy_loss_tags.intersection(event_noise):
            return "NOISY_WIN"
        return "MODEL_TOO_STRICT"
    if pre_grade == "SKIP" and not ht_goal:
        return "MODEL_VALID"
    return "CONTEXT_CHANGED"


def _format_single(row: dict) -> str:
    pred_peak = _top_predicted_bucket(row.get("predicted_bins") or {})
    return "\n".join(
        [
            "📌 V4 单场复盘",
            "",
            f"{row.get('home')} vs {row.get('away')}",
            "",
            "赛前：",
            f"等级 {row.get('pre_grade')}",
            f"HT评分 {row.get('pre_ht_score')}",
            f"time_bin_source {row.get('time_bin_source')}",
            f"预测剧本：{row.get('script_type')}",
            f"预测时间段（最高）：{pred_peak}",
            "",
            "赛果：",
            f"HT {row.get('ht_scoreline')}",
            f"FT {row.get('ft_scoreline')}",
            f"首球 {row.get('first_ht_goal_minute') if row.get('first_ht_goal_minute') is not None else '-'}'",
            f"命中时间段：{'是' if row.get('bucket_hit') else '否'}",
            "",
            "事件：",
            f"event_noise: {', '.join(row.get('event_noise') or ['无'])}",
            f"context_noise: {', '.join(row.get('context_noise') or ['无'])}",
            "",
            "归因：",
            f"{row.get('model_result')}",
            f"{row.get('diagnosis')}",
            "",
            "结论：",
            row.get("diagnosis_summary", "见诊断标签"),
        ]
    )


def run(date_str: str, fixture_id: int | None = None, sleep_ms: int = 120) -> dict[str, Any]:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if isinstance(scout, dict):
        scout = scout.get("results") or []
    if not isinstance(scout, list) or not scout:
        return {"error": f"scout文件不存在或为空: {scout_path}"}

    out_rows = []
    selected = [r for r in scout if (fixture_id is None or int(r.get("fixture_id") or 0) == int(fixture_id))]
    for rec in selected:
        fid = int(rec.get("fixture_id") or 0)
        if not fid:
            continue
        intel = explain_match(rec)
        ht_rec = intel.get("ht_recommendation") or {}
        pre_grade = str(ht_rec.get("grade") or "SKIP").upper()
        pre_ht_score = _safe_float(ht_rec.get("ht_score"), 0.0)
        pre_market_focus = str(rec.get("market_focus") or "-")
        time_bin_source = str(ht_rec.get("time_bins_source") or "NONE")
        script_type = str(ht_rec.get("script_type") or "-")
        pred_bins = ht_rec.get("time_bins") or {"0_15": 0.0, "16_30": 0.0, "31_45": 0.0}
        predicted_top_bucket = _top_predicted_bucket(pred_bins)
        sample_size = _safe_int(ht_rec.get("sample_size"), 0)
        coverage_level = str(((rec.get("data_coverage") or {}).get("coverage_level") or "")).upper()

        f_resp = _api_get(f"fixtures?id={fid}")
        f_rows = f_resp.get("response") or []
        if not f_rows:
            continue
        item = f_rows[0]
        score = item.get("score") or {}
        ht = score.get("halftime") or {}
        ft = score.get("fulltime") or {}
        ht_home = _safe_int(ht.get("home"), 0)
        ht_away = _safe_int(ht.get("away"), 0)
        ft_home = _safe_int(ft.get("home"), 0)
        ft_away = _safe_int(ft.get("away"), 0)
        ht_goal = (ht_home + ht_away) > 0

        e_resp = _api_get(f"fixtures/events?fixture={fid}")
        events = e_resp.get("response") or []
        first_min, hit_bucket = _first_ht_goal_minute(events)
        bucket_hit = bool(ht_goal and first_min is not None and hit_bucket == predicted_top_bucket)
        event_noise = _event_noise_tags(events, first_min)
        context_noise = _context_noise_tags(rec)

        model_result = _model_result(pre_grade, ht_goal)
        diagnosis = _diagnosis(
            pre_grade=pre_grade,
            ht_goal=ht_goal,
            event_noise=event_noise,
            context_noise=context_noise,
            time_bin_source=time_bin_source,
            pred_bins=pred_bins,
            sample_size=sample_size,
            coverage_level=coverage_level,
        )
        if diagnosis == "MODEL_VALID":
            diag_summary = "模型判断有效，且无明显偶然性干扰。"
        elif diagnosis == "MODEL_OVERCONFIDENT":
            diag_summary = "推荐未中且无明显噪音，模型偏乐观。"
        elif diagnosis == "MODEL_TOO_STRICT":
            diag_summary = "SKIP反杀且无明显噪音，跳过规则偏严。"
        elif diagnosis == "NOISY_WIN":
            diag_summary = "命中包含噪音事件，避免误判为稳定优势。"
        elif diagnosis == "NOISY_LOSS":
            diag_summary = "未命中受噪音事件影响，不宜直接调严规则。"
        elif diagnosis == "DATA_QUALITY_ISSUE":
            diag_summary = "样本/分布/覆盖质量不足，先补数据。"
        else:
            diag_summary = "赛前赛中上下文变化，建议人工复核。"

        row = {
            "fixture_id": fid,
            "date": datetime.strptime(key, "%Y%m%d").strftime("%Y-%m-%d"),
            "home": rec.get("home"),
            "away": rec.get("away"),
            "league": rec.get("league"),
            "pre_grade": pre_grade,
            "pre_ht_score": round(pre_ht_score, 1),
            "pre_market_focus": pre_market_focus,
            "time_bin_source": time_bin_source,
            "script_type": script_type,
            "predicted_bins": {
                "0_15": round(_safe_float(pred_bins.get("0_15"), 0.0), 4),
                "16_30": round(_safe_float(pred_bins.get("16_30"), 0.0), 4),
                "31_45": round(_safe_float(pred_bins.get("31_45"), 0.0), 4),
            },
            "predicted_top_bucket": predicted_top_bucket,
            "ht_goal": ht_goal,
            "ht_scoreline": f"{ht_home}-{ht_away}",
            "ft_scoreline": f"{ft_home}-{ft_away}",
            "first_ht_goal_minute": first_min,
            "hit_bucket": hit_bucket,
            "bucket_hit": bucket_hit,
            "event_noise": event_noise,
            "context_noise": context_noise,
            "model_result": model_result,
            "diagnosis": diagnosis,
            "diagnosis_summary": diag_summary,
        }
        out_rows.append(row)
        time.sleep(max(sleep_ms, 0) / 1000.0)

    out_path: Path | None = None
    if fixture_id is None:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        out_path = ARCHIVE_DIR / f"v4_result_attribution_{key}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for row in out_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "date": key,
        "rows": len(out_rows),
        "output_path": str(out_path) if out_path else None,
        "main_file_written": fixture_id is None,
        "model_result_counts": {},
        "diagnosis_counts": {},
    }
    for row in out_rows:
        summary["model_result_counts"][row["model_result"]] = summary["model_result_counts"].get(row["model_result"], 0) + 1
        summary["diagnosis_counts"][row["diagnosis"]] = summary["diagnosis_counts"].get(row["diagnosis"], 0) + 1

    if fixture_id is not None and out_rows:
        summary["single_report"] = _format_single(out_rows[0])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--fixture", type=int, default=None, help="单场复盘 fixture_id")
    parser.add_argument("--sleep-ms", type=int, default=120, help="API节流毫秒")
    args = parser.parse_args()
    result = run(args.date, fixture_id=args.fixture, sleep_ms=args.sleep_ms)
    if result.get("single_report"):
        print(result["single_report"])
        print("\n" + "-" * 50 + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "single_report"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
