"""
V2 评分引擎 v0.2 (P0 Day 3)
=============================
5维度等权评分（20% each），无赔率依赖。

数据格式：
  - H2H: list of fixtures
  - Predictions: {predictions, league, teams, comparison, h2h}
  - Fixtures: {id, league, date, status, ...}

输出评分 = sum(5维度得分)，满分100
"""

import json
import os
from pathlib import Path
from typing import Union

DATA_DIR = Path(__file__).parent.parent / "data" / "raw_fixtures"


# ═══════════════════════════════════════════════════════════
# 1. H2H 上半场进球率 (20分)
# ═══════════════════════════════════════════════════════════
def strip_self_reference(h2h_list: list, fixture_id: str) -> list:
    """从 H2H 中移除本场比赛自身（防止时序泄露）"""
    return [f for f in h2h_list if str(f.get("fixture", {}).get("id", "")) != str(fixture_id)]

def score_h2h(h2h_data: Union[dict, list], fixture_id: str = None) -> tuple:
    if isinstance(h2h_data, list):
        fixtures = h2h_data
    else:
        fixtures = h2h_data.get("response", []) if isinstance(h2h_data, dict) else []

    # 排除自引用（时序对齐）
    if fixture_id:
        fixtures = strip_self_reference(fixtures, str(fixture_id))

    if not fixtures:
        return 0, {"ht_goal_rate": 0, "total": 0, "ht_goal": 0, "ht_zero": 0, "weighted_rate": 0}

    ht_goal, ht_zero, total_goals = 0, 0, 0
    recent_goal, recent_total = 0, 0

    for i, f in enumerate(fixtures):
        ht = f.get("score", {}).get("halftime", {})
        h = ht.get("home") or 0
        a = ht.get("away") or 0
        if ht.get("home") is not None:
            if h + a > 0:
                ht_goal += 1
                total_goals += h + a
            else:
                ht_zero += 1
            if i < 5:
                recent_total += 1
                if h + a > 0:
                    recent_goal += 1

    total = ht_goal + ht_zero
    rate = ht_goal / total if total > 0 else 0
    recent_rate = recent_goal / recent_total if recent_total > 0 else 0
    weighted_rate = rate * 0.4 + recent_rate * 0.6

    score = weighted_rate * 20
    return round(score, 1), {
        "ht_goal_rate": round(rate * 100, 1),
        "total": total,
        "ht_goal": ht_goal,
        "ht_zero": ht_zero,
        "weighted_rate": round(weighted_rate * 100, 1),
        "ht_avg": round(total_goals / total, 1) if total > 0 else 0,
    }


# ═══════════════════════════════════════════════════════════
# 2. 近期状态 (20分)
# ═══════════════════════════════════════════════════════════
def score_form(pred_data: dict) -> tuple:
    teams = pred_data.get("teams", {}) or {}
    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}

    att_h = float(str(home.get("last_5", {}).get("att", "0")).rstrip("%") or 0)
    att_a = float(str(away.get("last_5", {}).get("att", "0")).rstrip("%") or 0)
    def_h = float(str(home.get("last_5", {}).get("def", "0")).rstrip("%") or 0)
    def_a = float(str(away.get("last_5", {}).get("def", "0")).rstrip("%") or 0)

    att_avg = (att_h + att_a) / 2
    def_gap = (def_h + def_a) / 2

    form_score = (att_avg * 0.7 + def_gap * 0.3) / 100 * 20
    return min(round(form_score, 1), 20), {
        "att_avg": round(att_avg, 1),
        "def_gap": round(def_gap, 1),
    }


# ═══════════════════════════════════════════════════════════
# 3. 泊松分布 (20分)
# ═══════════════════════════════════════════════════════════
def score_poisson(pred_data: dict) -> tuple:
    teams = pred_data.get("teams", {}) or {}
    home_avg = teams.get("home", {}).get("last_5", {}).get("goals", {}).get("for", {}).get("average", 0)
    away_avg = teams.get("away", {}).get("last_5", {}).get("goals", {}).get("for", {}).get("average", 0)

    ht_expected = (float(home_avg or 1.0) + float(away_avg or 1.0)) / 2 * 0.45
    score = min(ht_expected / 3.0 * 20, 20)
    return round(score, 1), {"ht_expected": round(float(ht_expected), 2)}


# ═══════════════════════════════════════════════════════════
# 4. 进球时间分布 (20分) — 用 H2H 上半场进球≥2的比例
# ═══════════════════════════════════════════════════════════
def score_goal_timing(h2h_data: Union[dict, list], fixture_id: str = None) -> tuple:
    if isinstance(h2h_data, list):
        fixtures = h2h_data[:10]
    else:
        fixtures = h2h_data.get("response", [])[:10] if isinstance(h2h_data, dict) else []
    if fixture_id:
        fixtures = [f for f in fixtures if str(f.get("fixture", {}).get("id", "")) != str(fixture_id)]

    early_goal, all_ht_goal = 0, 0
    for f in fixtures:
        ht = f.get("score", {}).get("halftime", {})
        h, a = ht.get("home") or 0, ht.get("away") or 0
        if ht.get("home") is not None and (h + a) > 0:
            all_ht_goal += 1
            if h + a >= 2:
                early_goal += 1

    rate = early_goal / all_ht_goal if all_ht_goal > 0 else 0
    score = rate * 20
    return round(score, 1), {
        "early_goal_rate": round(rate * 100, 1),
        "ht_goal_fixtures": all_ht_goal,
    }


# ═══════════════════════════════════════════════════════════
# 5. AI预测方向 (20分)
# ═══════════════════════════════════════════════════════════
def score_ai_advice(pred_data: dict) -> tuple:
    pp = pred_data.get("predictions", {}) or {}
    advice = (pp.get("advice", "") or "").lower()
    under_over = (pp.get("under_over", "") or "").lower()

    score = 10
    over_kw = ["over", "goal", "btts", "both", "score"]
    under_kw = ["under", "defensive", "low", "few", "tight"]

    if any(kw in advice for kw in over_kw) or any(kw in under_over for kw in over_kw):
        score += 3
    if any(kw in advice for kw in under_kw):
        score -= 5

    return max(0, min(20, score)), {"advice": pp.get("advice", ""), "under_over": pp.get("under_over", "")}


# ═══════════════════════════════════════════════════════════
# 主评分
# ═══════════════════════════════════════════════════════════
def score_match(fixture_data: dict, h2h_data: Union[dict, list], pred_data: dict) -> dict:
    s1, st1 = score_h2h(h2h_data, str(fixture_data.get("id", "")))
    s2, st2 = score_form(pred_data)
    s3, st3 = score_poisson(pred_data)
    s4, st4 = score_goal_timing(h2h_data, str(fixture_data.get("id", "")))
    s5, st5 = score_ai_advice(pred_data)

    total = round(s1 + s2 + s3 + s4 + s5, 1)

    # 预测概率
    ht_prob = st1["ht_goal_rate"] / 100
    att_signal = st2["att_avg"] / 100
    est_prob = ht_prob * 0.5 + att_signal * 0.3 + 0.2
    est_prob = max(0.1, min(0.95, est_prob))

    # 0-0 防守
    zero_warn = est_prob < 0.50
    if zero_warn:
        total = min(total, 40)

    model_odds = round(1 / est_prob, 2)

    # 有效推荐
    recommended = total >= 75 and model_odds > 1.70

    return {
        "total_score": total,
        "dimensions": {
            "h2h": s1, "form": s2, "poisson": s3, "goal_timing": s4, "ai_advice": s5,
        },
        "model_prob": round(est_prob * 100, 1),
        "model_odds": model_odds,
        "zero_zero_warning": zero_warn,
        "is_recommended": recommended,
        "h2h_stats": {k: v for k, v in st1.items() if k != "recent_scores"},
        "form_stats": st2,
        "poisson_stats": st3,
    }


if __name__ == "__main__":
    import sys
    fid = sys.argv[1] if len(sys.argv) > 1 else "1379257"

    with open(DATA_DIR / "h2h" / f"{fid}.json") as f:
        h2h = json.load(f)
    with open(DATA_DIR / "predictions" / f"{fid}.json") as f:
        pred = json.load(f)
    with open(DATA_DIR / "fixtures_list.json") as f:
        fixtures = json.load(f)

    fix = next((x for x in fixtures if isinstance(x, dict) and str(x.get("id")) == str(fid)), None)

    result = score_match(fix or {"id": fid}, h2h, pred)
    print(json.dumps(result, indent=2, ensure_ascii=False))
