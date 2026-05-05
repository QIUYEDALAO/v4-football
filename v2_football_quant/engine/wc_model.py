"""
世界杯独立评分模型 v1.0 (MVP — 数据诚实版)
=============================================
仅使用可自动获取、可验证的 3 维度。

核心公式：
  raw_score = stage_weight * 0.40           ← 淘汰赛权重远大于小组赛
            + att_signal * 0.35             ← 进攻信号 (Predictions API)
            + def_weakness * 0.25           ← 防守漏洞 (Predictions API)
            × cross_conf_bonus              ← 跨洲加成 (欧洲vs亚非)

禁用维度：行程疲劳、核心缺阵 → 留给人工审核环节
冻结日期：2026-05-05，世界杯前不再动
"""

import json


def stage_weight(stage: str) -> float:
    return {
        "group": 0.85,
        "round16": 1.15,
        "quarter": 1.20,
        "semi": 1.25,
        "final": 1.20,
        "3rd_place": 1.30,
    }.get(stage, 1.0)


def zero_zero_threshold(stage: str) -> float:
    """0-0防守触发阈值"""
    return 0.40 if stage == "group" else 0.25


def cross_conf_bonus(home_conf: str, away_conf: str) -> float:
    """欧洲队 vs 亚洲/非洲队 → 上半场碾压概率高"""
    eur = "UEFA" in (home_conf, away_conf)
    other = any(c in (home_conf, away_conf) for c in ["AFC", "CAF", "OFC"])
    return 1.15 if eur and other else 1.0


def score_wc(fixture: dict, predictions: dict) -> dict:
    """
    世界杯单场评分。
    
    Args:
        fixture: fixtures_list 条目 {home, away, round, htHome, htAway, ...}
        predictions: predictions API 响应 dict
    
    Returns:
        {total_score, recommended, stage, ...}
    """
    # ——— 提取特征 ———
    teams = predictions.get("teams", {}) or {}
    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}

    att_h = float(str(home.get("last_5", {}).get("att", "50")).rstrip("%") or 50)
    att_a = float(str(away.get("last_5", {}).get("att", "50")).rstrip("%") or 50)
    def_h = float(str(home.get("last_5", {}).get("def", "50")).rstrip("%") or 50)
    def_a = float(str(away.get("last_5", {}).get("def", "50")).rstrip("%") or 50)

    att_signal = ((att_h + att_a) / 2) / 100
    def_weakness = ((def_h + def_a) / 2) / 100

    # ——— 赛制解析 ———
    round_raw = fixture.get("round", "").lower()
    if "round" in round_raw:
        stage = "round16"
    elif "quarter" in round_raw:
        stage = "quarter"
    elif "semi" in round_raw:
        stage = "semi"
    elif "final" in round_raw and "3rd" not in round_raw:
        stage = "final"
    elif "3rd" in round_raw:
        stage = "3rd_place"
    else:
        stage = "group"

    sw = stage_weight(stage)
    zz = zero_zero_threshold(stage)
    cb = cross_conf_bonus("UEFA", "CONMEBOL")  # 简化：可后续接入 confederation API

    # ——— 评分 ———
    raw = (sw * 0.40 + att_signal * 0.35 + def_weakness * 0.25) * cb
    total_score = round(raw * 100, 1)

    # 0-0 防守
    if att_signal < zz:
        total_score = min(total_score, 40)

    # 动态阈值
    threshold = 62 if stage == "group" else 58
    recommended = total_score >= threshold

    # 实际赛果
    ht_goals = (fixture.get("htHome", 0) or 0) + (fixture.get("htAway", 0) or 0)

    return {
        "fixture_id": fixture.get("id"),
        "home": fixture.get("home", ""),
        "away": fixture.get("away", ""),
        "stage": stage,
        "total_score": total_score,
        "threshold": threshold,
        "recommended": recommended,
        "stage_weight": sw,
        "att_signal": round(att_signal * 100),
        "def_weakness": round(def_weakness * 100),
        "actual_ht_goals": ht_goals,
    }


def batch_score(fixtures: list, predictions_map: dict) -> list[dict]:
    results = []
    for fx in fixtures:
        pred = predictions_map.get(str(fx.get("id"))) or predictions_map.get(fx.get("id", 0))
        if pred is None:
            continue
        results.append(score_wc(fx, pred))
    return results


# ===== 验证 =====
if __name__ == "__main__":
    import sys
    from pathlib import Path

    WC_DIR = Path(__file__).parent.parent / "data" / "worldcup"
    RAW_DIR = Path(__file__).parent.parent / "data" / "raw_fixtures"

    with open(WC_DIR / "fixtures_list.json") as f:
        fixtures = json.load(f)

    preds = {}
    for fx in fixtures:
        pp = RAW_DIR / "wc_predictions" / f"{fx['id']}.json"
        if pp.exists():
            with open(pp) as f:
                preds[fx["id"]] = json.load(f)

    results = batch_score(fixtures, preds)

    rec = [r for r in results if r["recommended"]]
    hit = [r for r in rec if r["actual_ht_goals"] > 0]

    print(f"世界杯模型 v1.0 回测")
    print(f"  总场次: {len(results)}")
    print(f"  推荐: {len(rec)} 场")
    print(f"  命中: {len(hit)}/{len(rec)} = {len(hit)/len(rec)*100:.1f}%" if rec else "N/A")

    for stage in ["group", "round16", "quarter", "semi", "final", "3rd_place"]:
        st = [r for r in rec if r["stage"] == stage]
        ht = [r for r in st if r["actual_ht_goals"] > 0]
        if st:
            print(f"    {stage}: {len(ht)}/{len(st)} = {len(ht)/len(st)*100:.0f}%")
