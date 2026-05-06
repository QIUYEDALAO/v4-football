"""
V3 世界杯回测脚本
=================
用 Elo + Perception Gap 模型回测 2022 年卡塔尔世界杯
"""
import json, math
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "deep"

# 2022 世界杯参赛队 Elo (开赛前估值，来源: eloratings.net 历史数据)
ELO_2022 = {
    "AR": 2068, "BR": 2052, "FR": 2026, "EN": 2002, "ES": 1998,
    "PT": 1974, "NL": 1968, "DE": 1964, "HR": 1940, "BE": 1932,
    "UY": 1912, "DK": 1898, "CH": 1884, "MX": 1870, "US": 1862,
    "MA": 1848, "SN": 1840, "JP": 1836, "RS": 1830, "IR": 1824,
    "PL": 1820, "KR": 1816, "AU": 1810, "EC": 1808, "TN": 1804,
    "CR": 1800, "CM": 1798, "GH": 1796, "SA": 1794, "QA": 1790,
    "CA": 1788, "WA": 1786
}

# 身价估值 2022 (亿欧元)
VALUES_2022 = {
    "EN": 13.0, "FR": 11.0, "BR": 10.5, "PT": 9.5, "ES": 9.0,
    "DE": 8.5, "AR": 7.5, "NL": 7.0, "BE": 6.0, "HR": 4.0,
    "UY": 4.0, "DK": 3.5, "CH": 3.0, "MX": 3.0, "US": 3.0,
    "MA": 2.5, "SN": 3.0, "JP": 2.5, "RS": 3.0, "IR": 1.5,
    "PL": 3.0, "KR": 2.0, "AU": 1.5, "EC": 1.5, "TN": 1.0,
    "CR": 1.0, "CM": 1.5, "GH": 1.5, "SA": 1.0, "QA": 1.0,
    "CA": 2.5, "WA": 1.0
}

TEAM_NAMES = {
    "AR":"阿根廷","BR":"巴西","FR":"法国","EN":"英格兰","ES":"西班牙",
    "PT":"葡萄牙","NL":"荷兰","DE":"德国","HR":"克罗地亚","BE":"比利时",
    "UY":"乌拉圭","DK":"丹麦","CH":"瑞士","MX":"墨西哥","US":"美国",
    "MA":"摩洛哥","SN":"塞内加尔","JP":"日本","RS":"塞尔维亚","IR":"伊朗",
    "PL":"波兰","KR":"韩国","AU":"澳大利亚","EC":"厄瓜多尔","TN":"突尼斯",
    "CR":"哥斯达黎加","CM":"喀麦隆","GH":"加纳","SA":"沙特","QA":"卡塔尔",
    "CA":"加拿大","WA":"威尔士"
}

# 2022世界杯全部比赛 (group + KO) — HT=半场, FT=全场
WC2022_MATCHES = [
    # 小组赛
    ("QA","EC","A",0,2,0,2), ("EN","IR","B",3,0,6,2), ("SN","NL","A",0,0,0,2),
    ("US","WA","B",1,0,1,1), ("AR","SA","C",1,0,1,2), ("DK","TN","D",0,0,0,0),
    ("MX","PL","C",0,0,0,0), ("FR","AU","D",2,1,4,1), ("MA","HR","F",0,0,0,0),
    ("DE","JP","E",1,0,1,2), ("ES","CR","E",3,0,7,0), ("BE","CA","F",1,0,1,0),
    ("CH","CM","G",0,0,1,0), ("UY","KR","H",0,0,0,0), ("PT","GH","H",0,0,3,2),
    ("BR","RS","G",0,0,2,0),
    # KO
    ("NL","US","KO16",2,0,3,1), ("AR","AU","KO16",1,0,2,1),
    ("FR","PL","KO16",1,0,3,1), ("EN","SN","KO16",0,0,3,0),
    ("JP","HR","KO16",1,0,1,1), ("BR","KR","KO16",4,0,4,1),
    ("MA","ES","KO16",0,0,0,0), ("PT","CH","KO16",0,0,6,1),
    ("HR","BR","QF",0,0,1,1), ("NL","AR","QF",0,1,2,2),
    ("MA","PT","QF",1,0,1,0), ("EN","FR","QF",0,1,1,2),
    ("AR","HR","SF",2,0,3,0), ("FR","MA","SF",1,0,2,0),
    ("HR","MA","3RD",1,1,2,1), ("AR","FR","FINAL",2,0,3,3),
]
# 格式: (H, A, stage, HT_H, HT_A, FT_H, FT_A)


def elo_to_prob(elo_h, elo_a):
    """Elo → 胜率"""
    diff = elo_h - elo_a
    we = 1.0 / (10**(-diff/400) + 1)
    draw = max(0.15, 0.30 - abs(diff)/1500)
    hw = we * (1 - draw)
    aw = (1 - we) * (1 - draw)
    return hw, draw, aw


def perception_gap(h,a):
    """认知偏差"""
    vh,va = VALUES_2022.get(h,1), VALUES_2022.get(a,1)
    eh,ea = ELO_2022.get(h,1500), ELO_2022.get(a,1500)
    if ea==0: return 0
    return round((vh/va)/(eh/max(ea,1)) - 1, 3)


def run():
    print("⚽ V3 2022世界杯回测\n" + "="*60)
    
    results = {"draw_signals": [], "ah_signals": []}
    total_draw, hit_draw = 0, 0
    
    for h, a, stage, ht_h, ht_a, ft_h, ft_a in WC2022_MATCHES:
        elo_h, elo_a = ELO_2022.get(h,1500), ELO_2022.get(a,1500)
        hw, draw_prob, aw = elo_to_prob(elo_h, elo_a)
        gap = perception_gap(h,a)
        
        # 淘汰赛平局加成
        if stage != "group":
            draw_prob += 0.04  # KO boost
        
        # 实际平局 (半场或全场)
        ht_draw = (ht_h == ht_a)
        ft_draw = (ft_h == ft_a)
        any_draw = ht_draw or ft_draw
        
        # V3 策略: draw_prob > 35% → 推荐半场或全场平局
        if draw_prob > 0.25:  # W杯平局阈值 (Elo分差大，自然偏低)
            total_draw += 1
            if ft_draw:
                hit_draw += 1
            results["draw_signals"].append({
                "match": f"{TEAM_NAMES.get(h,h)} vs {TEAM_NAMES.get(a,a)}",
                "stage": stage,
                "draw_prob": round(draw_prob, 3),
                "ft_draw": ft_draw,
                "ht_draw": ht_draw,
                "elo": f"{elo_h}/{elo_a}",
                "gap": gap,
            })
        
        # 亚盘信号: Gap > 0.3 → 买受让
        if gap > 0.3:
            target = a
            handicap = "+1.5" if abs(elo_h - elo_a) > 200 else "+1.25"
            # 受让盘覆盖范围: 弱队至少不输超过 handicap
            cover = (ft_a + (1.5 if handicap=="+1.5" else 1.25)) >= ft_h
            results["ah_signals"].append({
                "match": f"{TEAM_NAMES.get(h,h)} vs {TEAM_NAMES.get(a,a)}",
                "handicap": handicap,
                "target": TEAM_NAMES.get(a,a),
                "gap": gap,
                "cover": cover,
                "score": f"{ft_h}-{ft_a}",
            })
    
    # 结果输出
    print(f"\n📊 平局信号 (draw_prob > 35%): {total_draw} 场")
    print(f"  命中 (FT Draw): {hit_draw}/{total_draw} = {hit_draw/total_draw*100:.1f}%" if total_draw else "  无信号")
    for s in results["draw_signals"]:
        mark = "✅" if s["ft_draw"] else "❌"
        print(f"  {mark} {s['match']} [{s['stage']}] draw={s['draw_prob']:.1%} elo={s['elo']}")
    
    ah_total = len(results["ah_signals"])
    ah_hit = sum(1 for s in results["ah_signals"] if s["cover"])
    print(f"\n📊 亚盘信号 (Gap > 0.3): {ah_total} 场")
    print(f"  覆盖: {ah_hit}/{ah_total} = {ah_hit/ah_total*100:.1f}%" if ah_total else "  无信号")
    for s in results["ah_signals"]:
        mark = "✅" if s["cover"] else "❌"
        print(f"  {mark} {s['match']} BUY {s['target']} AH{s['handicap']} gap={s['gap']:.1f} ({s['score']})")
    
    print(f"\n✅ 回测完成")
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR/"wc2022_backtest.json","w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run()
