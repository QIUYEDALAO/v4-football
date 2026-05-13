#!/usr/bin/env python3
"""V2 信号层 5 项验证：固定1u回放 / 赔率分组 / 赔率分桶 / 日期分桶 / EV分桶"""
import json, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

PT_DIR = Path(__file__).resolve().parent.parent / "data" / "paper_trading"

all_bets = []
for f in sorted(PT_DIR.glob("verified_*.json")):
    date = f.stem.replace("verified_", "")
    try:
        d = json.load(open(f))
    except Exception:
        continue
    for r in d.get("results", d.get("details", [])):
        if not isinstance(r, dict):
            continue
        r["_date"] = date
        all_bets.append(r)

N = len(all_bets)
hits = sum(1 for b in all_bets if b.get("is_hit"))
misses = N - hits
print(f"═══════════════════════════════════════════")
print(f"  V2_HT_DRAW 信号验证 | {N} 场 | 5/05-5/12")
print(f"═══════════════════════════════════════════")
print(f"  总场次: {N} | 命中: {hits} | 命中率: {hits/N*100:.1f}%")
print()

# ─── 1. 固定 1u 回放 ───
flat_pnl = 0.0
hit_odds_list = []
miss_odds_list = []
all_odds_list = []
daily_flat = defaultdict(lambda: {"pnl": 0.0, "hits": 0, "misses": 0, "total": 0, "odds": []})
running_pnl = []
peak = 0.0
drawdowns = []
max_losing_streak = cur_losing = 0

for b in all_bets:
    odds = float(b.get("placed_odds") or b.get("odds") or 0)
    if not odds:
        continue
    all_odds_list.append(odds)
    date = b.get("_date", "?")
    is_hit = bool(b.get("is_hit"))
    
    # Fixed 1u PnL
    unit_pnl = (odds - 1) if is_hit else -1.0
    flat_pnl += unit_pnl
    daily_flat[date]["pnl"] += unit_pnl
    daily_flat[date]["total"] += 1
    daily_flat[date]["odds"].append(odds)
    
    if is_hit:
        hit_odds_list.append(odds)
        daily_flat[date]["hits"] += 1
        cur_losing = 0
    else:
        miss_odds_list.append(odds)
        daily_flat[date]["misses"] += 1
        cur_losing += 1
        max_losing_streak = max(max_losing_streak, cur_losing)
    
    running_pnl.append(flat_pnl)
    if flat_pnl > peak:
        peak = flat_pnl
    dd = peak - flat_pnl
    drawdowns.append(dd)

max_dd = max(drawdowns) if drawdowns else 0.0
roi = flat_pnl / max(N, 1) * 100

print("═══ 1. 固定 1u 回放 ═══")
print(f"  固定1u PnL: {flat_pnl:+.1f}u")
print(f"  ROI: {roi:.1f}%")
print(f"  最大回撤: {max_dd:.1f}u")
print(f"  最大连黑: {max_losing_streak} 场")
print()

# ─── 2. 命中 vs 未命中赔率 ───
import statistics
h_avg = statistics.mean(hit_odds_list) if hit_odds_list else 0
h_med = statistics.median(hit_odds_list) if hit_odds_list else 0
m_avg = statistics.mean(miss_odds_list) if miss_odds_list else 0
m_med = statistics.median(miss_odds_list) if miss_odds_list else 0
a_avg = statistics.mean(all_odds_list) if all_odds_list else 0
a_med = statistics.median(all_odds_list) if all_odds_list else 0

print("═══ 2. 赔率分组 ═══")
print(f"  命中平均赔率: {h_avg:.2f} (中位 {h_med:.2f})")
print(f"  未命中平均赔率: {m_avg:.2f} (中位 {m_med:.2f})")
print(f"  全样本平均赔率: {a_avg:.2f} (中位 {a_med:.2f})")
print(f"  命中溢价: {h_avg - a_avg:+.2f} {'✅ 命中赔率不低' if h_avg >= a_avg else '⚠️ 命中场赔率偏低'}")
print()

# ─── 3. 赔率区间分桶 ───
buckets = [
    (2.00, 2.30), (2.30, 2.60), (2.60, 2.90),
    (2.90, 3.20), (3.20, 3.50), (3.50, 99.0)
]
print("═══ 3. 赔率区间分桶 ═══")
print(f"  {'区间':>12} {'场次':>5} {'命中':>5} {'命中率':>8} {'1u PnL':>8} {'贡献':>8}")
for lo, hi in buckets:
    bucket_bets = [(b, float(b.get("placed_odds", 0))) for b in all_bets if lo <= float(b.get("placed_odds", 0)) < hi]
    n_b = len(bucket_bets)
    if not n_b:
        continue
    h_b = sum(1 for b, o in bucket_bets if b.get("is_hit"))
    pnl_b = sum((o - 1) if b.get("is_hit") else -1.0 for b, o in bucket_bets)
    print(f"  {lo:.2f}-{hi:.2f} {n_b:>5} {h_b:>5} {h_b/n_b*100:>7.1f}% {pnl_b:>+8.1f} {pnl_b/flat_pnl*100:>+7.0f}%")
print()

# ─── 4. 日期分桶 ───
print("═══ 4. 日期分桶 ═══")
print(f"  {'日期':>10} {'场次':>5} {'命中':>5} {'命中率':>8} {'1u PnL':>8} {'平均赔率':>8} {'连黑':>5}")
for date in sorted(daily_flat.keys()):
    d = daily_flat[date]
    rate = d["hits"] / max(d["total"], 1) * 100
    avg_o = statistics.mean(d["odds"]) if d["odds"] else 0
    # Find max losing streak for this day
    day_losing = 0
    day_max_losing = 0
    for b in all_bets:
        if b.get("_date") != date:
            continue
        if b.get("is_hit"):
            day_losing = 0
        else:
            day_losing += 1
            day_max_losing = max(day_max_losing, day_losing)
    print(f"  {date:>10} {d['total']:>5} {d['hits']:>5} {rate:>7.1f}% {d['pnl']:>+8.1f} {avg_o:>8.2f} {day_max_losing:>5}")
print()

# ─── 5. EV / Edge 分桶 ───
# Read from predictions which have edge_pp / ev_pct
PRED_DIR = Path(__file__).resolve().parent.parent / "data" / "daily_reports"
edge_buckets = defaultdict(lambda: {"total": 0, "hits": 0, "pnl": 0.0, "odds": []})
for f in sorted(PRED_DIR.glob("predictions_*.json")):
    try:
        preds = json.load(open(f))
    except:
        continue
    if not isinstance(preds, list):
        continue
    date = f.stem.replace("predictions_", "")
    for p in preds:
        fid = p.get("fixture_id")
        ev = float(p.get("ev_pct", 0) or 0)
        edge = float(p.get("edge_pp", 0) or 0)
        odds = float(p.get("placed_odds", 0) or 0)
        # Match to verified
        matched = [b for b in all_bets if b.get("fixture_id") == fid and b.get("_date") == date]
        if not matched:
            continue
        b = matched[0]
        is_hit = bool(b.get("is_hit"))
        unit_pnl = (odds - 1) if is_hit else -1.0 if odds else 0
        
        # EV buckets
        ev_bin = "neg" if ev <= 0 else ("0-5%" if ev <= 0.05 else ("5-10%" if ev <= 0.10 else ("10-20%" if ev <= 0.20 else "20%+")))
        edge_buckets[f"EV:{ev_bin}"]["total"] += 1
        edge_buckets[f"EV:{ev_bin}"]["hits"] += 1 if is_hit else 0
        edge_buckets[f"EV:{ev_bin}"]["pnl"] += unit_pnl
        edge_buckets[f"EV:{ev_bin}"]["odds"].append(odds)

print("═══ 5. EV 分桶 ═══")
print(f"  {'EV区间':>12} {'场次':>5} {'命中':>5} {'命中率':>8} {'1u PnL':>8}")
for label in ["EV:neg", "EV:0-5%", "EV:5-10%", "EV:10-20%", "EV:20%+"]:
    d = edge_buckets[label]
    if d["total"]:
        rate = d["hits"] / d["total"] * 100
        print(f"  {label:>12} {d['total']:>5} {d['hits']:>5} {rate:>7.1f}% {d['pnl']:>+8.1f}")

print(f"\n═══════════════════════════════════════════")
print(f"  结论: 信号层{'✅ 正期望' if flat_pnl > 0 else '❌ 负期望'}")
print(f"  固定1u 150场 PnL={flat_pnl:+.1f}u ROI={roi:.1f}% MDD={max_dd:.1f}u 连黑={max_losing_streak}")
print(f"═══════════════════════════════════════════")
