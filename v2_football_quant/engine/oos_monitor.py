"""
OOS 对抗验证 + 模型衰退监测 v0.1
===================================
P2-4: 时间序列切分验证（非随机，防未来函数）
P2-5: 滚动50场 ROI 监测

分层：
  - Train: 3月-4月初
  - Test: 4月中-5月初（时间后续的OOS）
  - Monitor: 滚动50场窗口

红线：必须严格按时间切分，不能随机抽样
"""

import json, os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data" / "raw_fixtures"


def load_all_records():
    """加载全量回测记录（含排自引用的H2H统计）"""
    with open(DATA_DIR / "fixtures_list.json") as f:
        fixtures = json.load(f)
    
    records = []
    for item in fixtures:
        if not isinstance(item, dict):
            continue
        fid = str(item.get("id", ""))
        h2h_path = DATA_DIR / "h2h" / f"{fid}.json"
        pred_path = DATA_DIR / "predictions" / f"{fid}.json"
        if not (h2h_path.exists() and pred_path.exists()):
            continue
        
        with open(h2h_path) as f:
            h2h = json.load(f)
        with open(pred_path) as f:
            pred = json.load(f)
        
        # 排除自引用
        h2h = [x for x in h2h if str(x.get("fixture", {}).get("id", "")) != fid]
        
        ht_goal, ht_zero = 0, 0
        for ff in h2h:
            ht = ff.get("score", {}).get("halftime", {})
            h = ht.get("home") or 0
            a = ht.get("away") or 0
            if ht.get("home") is not None:
                if h + a > 0:
                    ht_goal += 1
                else:
                    ht_zero += 1
        
        total_h = ht_goal + ht_zero
        h2h_rate = ht_goal / total_h * 100 if total_h > 0 else 0
        
        # 日期
        date_str = item.get("date", "")
        try:
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            continue
        
        ht_actual = (item.get("htHome", 0) or 0) + (item.get("htAway", 0) or 0)
        has_goal = 1 if ht_actual > 0 else 0
        
        # 判定：V38门槛
        meets_v38 = total_h >= 4 and h2h_rate >= 80 and ht_zero <= 2
        
        records.append({
            "fid": int(fid),
            "date": date,
            "date_str": date_str[:10],
            "league": str(item.get("league", "?")),
            "h2h_rate": h2h_rate,
            "h2h_total": total_h,
            "h2h_zero": ht_zero,
            "meets_v38": meets_v38,
            "has_goal": has_goal,
            "ht_goals": ht_actual,
        })
    
    return sorted(records, key=lambda x: x["date"])


def oos_split(records, train_end="2026-04-10"):
    """按时间切分 Train/Test"""
    train_cutoff = datetime.fromisoformat(train_end + "T00:00:00+00:00")
    
    train = [r for r in records if r["date"] < train_cutoff]
    test = [r for r in records if r["date"] >= train_cutoff]
    
    return train, test


def evaluate(records):
    """计算 V38 门槛命中率"""
    total = sum(1 for r in records if r["meets_v38"])
    hits = sum(1 for r in records if r["meets_v38"] and r["has_goal"])
    
    rate = hits / total * 100 if total > 0 else 0
    return {"total": total, "hits": hits, "rate": rate}


def rolling_roi(records, window=50, model_odds=1.85):
    """
    滚动50场 ROI 监测。
    
    输出：每个窗口的 ROI
    """
    # 筛选 V38 门槛场次
    filtered = [r for r in records if r["meets_v38"]]
    
    windows = []
    for i in range(0, len(filtered), window):
        chunk = filtered[i:i + window]
        if len(chunk) < window:
            break
        
        profit = 0
        bets = 0
        for r in chunk:
            bets += 1
            if r["has_goal"]:
                profit += model_odds - 1
            else:
                profit -= 1
        
        roi = profit / bets * 100
        windows.append({
            "start": chunk[0]["date_str"],
            "end": chunk[-1]["date_str"],
            "bets": bets,
            "profit": profit,
            "roi": roi,
        })
    
    return windows


def decay_warning(rolling_results, threshold_pct=-10):
    """模型衰退预警：如果最近一个窗口ROI < threshold，发出警告"""
    if not rolling_results:
        return None
    
    last = rolling_results[-1]
    if last["roi"] < threshold_pct:
        return {
            "warning": True,
            "window": last,
            "message": f"最近50场ROI {last['roi']:.1f}% < {threshold_pct}% — 建议暂停或重新校准"
        }
    return None


if __name__ == "__main__":
    print("=" * 60)
    print("OOS 对抗验证 + 滚动ROI监测")
    print("=" * 60)
    
    records = load_all_records()
    print(f"全量: {len(records)} 场, {records[0]['date_str']} → {records[-1]['date_str']}")
    
    # Train/Test 按时间切分
    train_end = "2026-04-10"
    train, test = oos_split(records, train_end)
    
    tr = evaluate(train)
    te = evaluate(test)
    
    print(f"\n[OOS 对抗验证: Train({train[0]['date_str']}-{train_end}) vs Test({train_end}后)]")
    print(f"  Train: {tr['hits']}/{tr['total']} = {tr['rate']:.1f}%")
    print(f"  Test:  {te['hits']}/{te['total']} = {te['rate']:.1f}%")
    print(f"  稳定性: {'✅ 稳定' if abs(tr['rate'] - te['rate']) < 15 else '⚠️ OOS不一致'}")
    
    # 滚动ROI
    print(f"\n[滚动50场 ROI 监测]")
    filtered = [r for r in records if r["meets_v38"]]
    print(f"  V38门槛场次: {len(filtered)}")
    
    rolling = rolling_roi(records, 50)
    for w in rolling:
        bar = "🟢" if w["roi"] > 5 else ("🟡" if w["roi"] > -5 else "🔴")
        print(f"  {bar} {w['start']} → {w['end']}: {w['bets']}场 ROI {w['roi']:+.1f}%")
    
    # 衰退预警
    warn = decay_warning(rolling)
    if warn:
        print(f"\n  ⚠️ {warn['message']}")
    else:
        print(f"\n  ✅ 无衰退预警")
