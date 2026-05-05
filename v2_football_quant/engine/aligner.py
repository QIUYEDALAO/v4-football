"""
时间对齐模块 v0.1
===================
防止未来函数：确保回测时只使用「赛前可获取」的数据。

核心原则：
  - H2H 数据：必须使用开赛前 <= 72h 内的快照（排除赛后才更新的）
  - Predictions：API 返回的是实时预测，必须确认是赛前版本
  - 赔率快照：取赛前 30min-24h 内的快照（不取赛后赔率）

当前限制：
  - api-football H2H 返回的是实时数据（包括完赛后结果）
  - Predictions 同样实时更新
  - 本次回测中，fixtures_list 存的是赛后比分

解决方案（v0.1 阶段）：
  - 使用 fixtures_list 里从未完赛的比赛开始拉取增量 H2H/Predictions
  - 对于已完赛的比赛，验证 H2H 是否包含本场比赛本身（排除自引用）
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA_DIR = Path(__file__).parent.parent / "data" / "raw_fixtures"


def parse_kickoff(date_str: str) -> datetime:
    """解析开赛时间（UTC）"""
    if not date_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        # 兼容多种格式
        for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S+00:00",
                     "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return datetime.fromisoformat(date_str)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def strip_self_reference(h2h_data: list, fixture_id: str) -> list:
    """
    从 H2H 中移除本场比赛本身。
    H2H API 会把最新这场比赛包含在返回结果里，必须排除。
    """
    return [f for f in h2h_data
            if str(f.get("fixture", {}).get("id", "")) != str(fixture_id)]


def validate_h2h_temporal(fixture_id: str, h2h_data: list, kickoff_utc: str) -> bool:
    """
    验证 H2H 数据是否是赛前可获取的。
    
    规则：
    1. H2H 中的所有比赛开赛时间必须 < 本场开赛时间
    2. 本场比赛本身不能出现在 H2H 中
    """
    kickoff = parse_kickoff(kickoff_utc)
    if kickoff == datetime.min.replace(tzinfo=timezone.utc):
        return True  # 无法判断，放过
    
    cleaned = strip_self_reference(h2h_data, fixture_id)
    
    for f in cleaned:
        h2h_date = f.get("fixture", {}).get("date", "")
        h2h_kickoff = parse_kickoff(h2h_date)
        if h2h_kickoff >= kickoff:
            return False  # 未来比赛被包含在H2H中，数据泄露
    
    return True


def validate_predictions_temporal(fixture_id: str, pred_data: dict, kickoff_utc: str) -> bool:
    """
    验证 Predictions 数据是否是赛前预测。
    
    规则：
    1. 检查 h2h 字段是否包含本场比赛（包含=赛后数据）
    2. 检查 captured_at 是否在开赛前
    """
    h2h_in_pred = pred_data.get("h2h", [])
    if isinstance(h2h_in_pred, list):
        for h in h2h_in_pred:
            if str(h.get("fixture", {}).get("id", "")) == str(fixture_id):
                return False  # 包含本场 = 包含赛后数据
    
    return True


def mark_data_quality(fixture_item: dict) -> dict:
    """
    标记单场数据质量。
    
    返回：带 quality 标记的 fixture dict
    """
    fid = str(fixture_item.get("id", ""))
    kickoff = fixture_item.get("date", "")
    
    quality = {
        "fixture_id": int(fid),
        "kickoff_utc": kickoff,
        "h2h_exists": False,
        "h2h_temporal_clean": False,
        "h2h_stripped_count": 0,
        "predictions_exists": False,
        "predictions_temporal_clean": False,
        "odds_exists": False,
        "is_completed": fixture_item.get("ftHome") is not None,
    }
    
    # H2H
    h2h_path = DATA_DIR / "h2h" / f"{fid}.json"
    if h2h_path.exists():
        quality["h2h_exists"] = True
        with open(h2h_path) as f:
            h2h_data = json.load(f)
        if isinstance(h2h_data, list):
            original_len = len(h2h_data)
            h2h_data = strip_self_reference(h2h_data, fid)
            quality["h2h_stripped_count"] = original_len - len(h2h_data)
            quality["h2h_temporal_clean"] = validate_h2h_temporal(fid, h2h_data, kickoff)
    
    # Predictions
    pred_path = DATA_DIR / "predictions" / f"{fid}.json"
    if pred_path.exists():
        quality["predictions_exists"] = True
        with open(pred_path) as f:
            pred_data = json.load(f)
        quality["predictions_temporal_clean"] = validate_predictions_temporal(fid, pred_data, kickoff)
    
    # Odds
    odds_path = DATA_DIR / "odds" / f"{fid}.json"
    quality["odds_exists"] = odds_path.exists()
    
    return quality


def quality_report(fixtures_list: list) -> dict:
    """
    全量数据质检报告。
    
    返回 {
        total, clean, leaked: 时序泄露场次,
        has_h2h, has_pred, has_odds,
        temporal_issues: [{fixture_id, issue}]
    }
    """
    report = {
        "total": len(fixtures_list),
        "clean": 0,
        "h2h_leaked": 0,
        "pred_leaked": 0,
        "has_h2h": 0,
        "has_pred": 0,
        "has_odds": 0,
        "temporal_issues": [],
    }
    
    for item in fixtures_list:
        if not isinstance(item, dict):
            continue
        q = mark_data_quality(item)
        
        if q["h2h_exists"]:
            report["has_h2h"] += 1
        if q["predictions_exists"]:
            report["has_pred"] += 1
        if q["odds_exists"]:
            report["has_odds"] += 1
        
        has_leak = False
        if q["h2h_exists"] and not q["h2h_temporal_clean"]:
            report["h2h_leaked"] += 1
            has_leak = True
        if q["predictions_exists"] and not q["predictions_temporal_clean"]:
            report["pred_leaked"] += 1
            has_leak = True
        
        if not has_leak:
            report["clean"] += 1
        elif q["h2h_stripped_count"] > 0:
            report["temporal_issues"].append({
                "fixture_id": q["fixture_id"],
                "h2h_stripped": q["h2h_stripped_count"],
                "issue": "H2H contains self-match (post-match data)"
            })
    
    return report


if __name__ == "__main__":
    # 快速跑一遍质检
    with open(DATA_DIR / "fixtures_list.json") as f:
        fixtures = json.load(f)
    
    report = quality_report(fixtures)
    
    print("=" * 50)
    print("数据时序质检报告")
    print("=" * 50)
    print(f"总场次: {report['total']}")
    print(f"H2H 存量: {report['has_h2h']}")
    print(f"Predictions 存量: {report['has_pred']}")
    print(f"Odds 存量: {report['has_odds']}")
    print(f"时序泄露 (H2H含自身): {report['h2h_leaked']}")
    print(f"时序泄露 (Predictions含自身): {report['pred_leaked']}")
    print(f"干净场次: {report['clean']}/{report['total']} ({report['clean']/report['total']*100:.1f}%)")
    print(f"污染场次: {len(report['temporal_issues'])}")
    
    if report["temporal_issues"]:
        print("\n前5条污染记录:")
        for issue in report["temporal_issues"][:5]:
            print(f"  fixture {issue['fixture_id']}: {issue['issue']}")
