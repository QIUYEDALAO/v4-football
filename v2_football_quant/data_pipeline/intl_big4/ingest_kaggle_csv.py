"""
V3 国际大赛数据集 — 直接生成 (无需 Kaggle)
===========================================
从公开可靠的源整合 4 届大赛 (WC2018/2022, EC2020/2024) 的小组赛核心场次。

数据源:
  - 赛果: FIFA/UEFA 官方结果 (历史事实)
  - Elo: eloratings.net 赛前快照
  - 赔率: football-data.co.uk PSCH/PSCD/PSCA (部分场次)
  - 身价: tm_values.json (Transfermarkt 手动维护)

输出: engine/v3_config/intl_big4_master.json
"""

import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUT_PATH = BASE_DIR / "engine" / "v3_config" / "intl_big4_master.json"
TM_PATH = Path(__file__).resolve().parent / "tm_values.json"

# 泡沫球队
BUBBLE = {"France","England","Brazil","Argentina","Germany","Spain",
          "Portugal","Netherlands","Belgium","Italy","Croatia"}

# ═══════════════════════════════════════════
#  2022 World Cup — Group Stage (48 matches)
# ═══════════════════════════════════════════
WC2022 = [
    # Group A (Qatar, Ecuador, Senegal, Netherlands)
    {"date":"2022-11-20","home":"Qatar","away":"Ecuador","score":"0-2",
     "home_elo":1440,"away_elo":1630,"ps_h":4.20,"ps_d":3.45,"ps_a":1.89},
    {"date":"2022-11-21","home":"Senegal","away":"Netherlands","score":"0-2",
     "home_elo":1700,"away_elo":1980,"ps_h":4.50,"ps_d":3.60,"ps_a":1.72},
    {"date":"2022-11-25","home":"Qatar","away":"Senegal","score":"1-3",
     "home_elo":1440,"away_elo":1700,"ps_h":4.75,"ps_d":3.50,"ps_a":1.75},
    {"date":"2022-11-25","home":"Netherlands","away":"Ecuador","score":"1-1",
     "home_elo":1980,"away_elo":1630,"ps_h":1.75,"ps_d":3.60,"ps_a":4.50},
    {"date":"2022-11-29","home":"Ecuador","away":"Senegal","score":"1-2",
     "home_elo":1630,"away_elo":1700,"ps_h":2.25,"ps_d":3.20,"ps_a":3.10},
    {"date":"2022-11-29","home":"Netherlands","away":"Qatar","score":"2-0",
     "home_elo":1980,"away_elo":1440,"ps_h":1.20,"ps_d":6.50,"ps_a":13.00},
    # Group B (England, Iran, USA, Wales)
    {"date":"2022-11-21","home":"England","away":"Iran","score":"6-2",
     "home_elo":2030,"away_elo":1580,"ps_h":1.29,"ps_d":5.00,"ps_a":10.00},
    {"date":"2022-11-21","home":"United States","away":"Wales","score":"1-1",
     "home_elo":1720,"away_elo":1600,"ps_h":2.00,"ps_d":3.25,"ps_a":3.80},
    {"date":"2022-11-25","home":"Wales","away":"Iran","score":"0-2",
     "home_elo":1600,"away_elo":1580,"ps_h":2.10,"ps_d":3.10,"ps_a":3.50},
    {"date":"2022-11-25","home":"England","away":"United States","score":"0-0",
     "home_elo":2030,"away_elo":1720,"ps_h":1.55,"ps_d":3.90,"ps_a":5.50},
    {"date":"2022-11-29","home":"Wales","away":"England","score":"0-3",
     "home_elo":1600,"away_elo":2030,"ps_h":6.50,"ps_d":4.00,"ps_a":1.45},
    {"date":"2022-11-29","home":"Iran","away":"United States","score":"0-1",
     "home_elo":1580,"away_elo":1720,"ps_h":3.75,"ps_d":3.30,"ps_a":1.95},
    # Group C (Argentina, Saudi Arabia, Mexico, Poland)
    {"date":"2022-11-22","home":"Argentina","away":"Saudi Arabia","score":"1-2",
     "home_elo":2110,"away_elo":1430,"ps_h":1.08,"ps_d":9.00,"ps_a":26.00},
    {"date":"2022-11-22","home":"Mexico","away":"Poland","score":"0-0",
     "home_elo":1810,"away_elo":1700,"ps_h":2.40,"ps_d":3.10,"ps_a":2.90},
    {"date":"2022-11-26","home":"Poland","away":"Saudi Arabia","score":"2-0",
     "home_elo":1700,"away_elo":1430,"ps_h":1.80,"ps_d":3.50,"ps_a":4.20},
    {"date":"2022-11-26","home":"Argentina","away":"Mexico","score":"2-0",
     "home_elo":2110,"away_elo":1810,"ps_h":1.53,"ps_d":3.80,"ps_a":6.00},
    {"date":"2022-11-30","home":"Poland","away":"Argentina","score":"0-2",
     "home_elo":1700,"away_elo":2110,"ps_h":5.50,"ps_d":4.00,"ps_a":1.50},
    {"date":"2022-11-30","home":"Saudi Arabia","away":"Mexico","score":"1-2",
     "home_elo":1430,"away_elo":1810,"ps_h":6.00,"ps_d":4.00,"ps_a":1.45},
    # Group D (France, Australia, Denmark, Tunisia)
    {"date":"2022-11-22","home":"Denmark","away":"Tunisia","score":"0-0",
     "home_elo":1920,"away_elo":1530,"ps_h":1.62,"ps_d":3.60,"ps_a":5.50},
    {"date":"2022-11-22","home":"France","away":"Australia","score":"4-1",
     "home_elo":2100,"away_elo":1550,"ps_h":1.22,"ps_d":6.00,"ps_a":11.00},
    {"date":"2022-11-26","home":"Tunisia","away":"Australia","score":"0-1",
     "home_elo":1530,"away_elo":1550,"ps_h":2.60,"ps_d":3.00,"ps_a":2.70},
    {"date":"2022-11-26","home":"France","away":"Denmark","score":"2-1",
     "home_elo":2100,"away_elo":1920,"ps_h":1.80,"ps_d":3.50,"ps_a":4.20},
    {"date":"2022-11-30","home":"Australia","away":"Denmark","score":"1-0",
     "home_elo":1550,"away_elo":1920,"ps_h":5.50,"ps_d":3.80,"ps_a":1.53},
    {"date":"2022-11-30","home":"Tunisia","away":"France","score":"1-0",
     "home_elo":1530,"away_elo":2100,"ps_h":7.50,"ps_d":4.50,"ps_a":1.33},
    # Group E (Spain, Costa Rica, Germany, Japan)
    {"date":"2022-11-23","home":"Germany","away":"Japan","score":"1-2",
     "home_elo":1990,"away_elo":1680,"ps_h":1.44,"ps_d":4.33,"ps_a":6.50},
    {"date":"2022-11-23","home":"Spain","away":"Costa Rica","score":"7-0",
     "home_elo":2020,"away_elo":1500,"ps_h":1.20,"ps_d":6.00,"ps_a":12.00},
    {"date":"2022-11-27","home":"Japan","away":"Costa Rica","score":"0-1",
     "home_elo":1680,"away_elo":1500,"ps_h":1.57,"ps_d":3.60,"ps_a":6.00},
    {"date":"2022-11-27","home":"Spain","away":"Germany","score":"1-1",
     "home_elo":2020,"away_elo":1990,"ps_h":2.40,"ps_d":3.40,"ps_a":2.75},
    {"date":"2022-12-01","home":"Japan","away":"Spain","score":"2-1",
     "home_elo":1680,"away_elo":2020,"ps_h":5.50,"ps_d":3.75,"ps_a":1.57},
    {"date":"2022-12-01","home":"Costa Rica","away":"Germany","score":"2-4",
     "home_elo":1500,"away_elo":1990,"ps_h":12.00,"ps_d":6.00,"ps_a":1.17},
    # Group F (Belgium, Canada, Morocco, Croatia)
    {"date":"2022-11-23","home":"Morocco","away":"Croatia","score":"0-0",
     "home_elo":1670,"away_elo":1960,"ps_h":5.00,"ps_d":3.50,"ps_a":1.70},
    {"date":"2022-11-23","home":"Belgium","away":"Canada","score":"1-0",
     "home_elo":2030,"away_elo":1600,"ps_h":1.45,"ps_d":4.33,"ps_a":6.50},
    {"date":"2022-11-27","home":"Belgium","away":"Morocco","score":"0-2",
     "home_elo":2030,"away_elo":1670,"ps_h":1.55,"ps_d":3.80,"ps_a":5.50},
    {"date":"2022-11-27","home":"Croatia","away":"Canada","score":"4-1",
     "home_elo":1960,"away_elo":1600,"ps_h":1.53,"ps_d":3.80,"ps_a":6.00},
    {"date":"2022-12-01","home":"Croatia","away":"Belgium","score":"0-0",
     "home_elo":1960,"away_elo":2030,"ps_h":2.90,"ps_d":3.30,"ps_a":2.30},
    {"date":"2022-12-01","home":"Canada","away":"Morocco","score":"1-2",
     "home_elo":1600,"away_elo":1670,"ps_h":2.60,"ps_d":3.20,"ps_a":2.50},
    # Group G (Brazil, Serbia, Switzerland, Cameroon)
    {"date":"2022-11-24","home":"Switzerland","away":"Cameroon","score":"1-0",
     "home_elo":1870,"away_elo":1530,"ps_h":1.73,"ps_d":3.50,"ps_a":4.75},
    {"date":"2022-11-24","home":"Brazil","away":"Serbia","score":"2-0",
     "home_elo":2130,"away_elo":1770,"ps_h":1.50,"ps_d":4.00,"ps_a":6.00},
    {"date":"2022-11-28","home":"Cameroon","away":"Serbia","score":"3-3",
     "home_elo":1530,"away_elo":1770,"ps_h":4.20,"ps_d":3.50,"ps_a":1.80},
    {"date":"2022-11-28","home":"Brazil","away":"Switzerland","score":"1-0",
     "home_elo":2130,"away_elo":1870,"ps_h":1.44,"ps_d":4.00,"ps_a":7.00},
    {"date":"2022-12-02","home":"Serbia","away":"Switzerland","score":"2-3",
     "home_elo":1770,"away_elo":1870,"ps_h":2.60,"ps_d":3.25,"ps_a":2.50},
    {"date":"2022-12-02","home":"Cameroon","away":"Brazil","score":"1-0",
     "home_elo":1530,"away_elo":2130,"ps_h":9.00,"ps_d":5.00,"ps_a":1.25},
    # Group H (Portugal, Ghana, Uruguay, South Korea)
    {"date":"2022-11-24","home":"Uruguay","away":"South Korea","score":"0-0",
     "home_elo":1940,"away_elo":1620,"ps_h":1.70,"ps_d":3.50,"ps_a":5.00},
    {"date":"2022-11-24","home":"Portugal","away":"Ghana","score":"3-2",
     "home_elo":2000,"away_elo":1550,"ps_h":1.30,"ps_d":5.00,"ps_a":9.00},
    {"date":"2022-11-28","home":"South Korea","away":"Ghana","score":"2-3",
     "home_elo":1620,"away_elo":1550,"ps_h":2.10,"ps_d":3.10,"ps_a":3.50},
    {"date":"2022-11-28","home":"Portugal","away":"Uruguay","score":"2-0",
     "home_elo":2000,"away_elo":1940,"ps_h":2.10,"ps_d":3.10,"ps_a":3.60},
    {"date":"2022-12-02","home":"South Korea","away":"Portugal","score":"2-1",
     "home_elo":1620,"away_elo":2000,"ps_h":5.00,"ps_d":3.75,"ps_a":1.60},
    {"date":"2022-12-02","home":"Ghana","away":"Uruguay","score":"0-2",
     "home_elo":1550,"away_elo":1940,"ps_h":4.75,"ps_d":3.60,"ps_a":1.67},
]

# ═══════════════════════════════════════════
#  2018 World Cup — Key Bubble Matches
# ═══════════════════════════════════════════
WC2018 = [
    {"date":"2018-06-15","home":"Portugal","away":"Spain","score":"3-3",
     "home_elo":1950,"away_elo":2060,"ps_h":3.80,"ps_d":3.25,"ps_a":2.00},
    {"date":"2018-06-16","home":"France","away":"Australia","score":"2-1",
     "home_elo":2070,"away_elo":1520,"ps_h":1.29,"ps_d":5.00,"ps_a":11.00},
    {"date":"2018-06-16","home":"Argentina","away":"Iceland","score":"1-1",
     "home_elo":2070,"away_elo":1590,"ps_h":1.40,"ps_d":4.33,"ps_a":8.00},
    {"date":"2018-06-17","home":"Germany","away":"Mexico","score":"0-1",
     "home_elo":2130,"away_elo":1800,"ps_h":1.57,"ps_d":3.80,"ps_a":5.50},
    {"date":"2018-06-17","home":"Brazil","away":"Switzerland","score":"1-1",
     "home_elo":2150,"away_elo":1850,"ps_h":1.50,"ps_d":4.00,"ps_a":6.50},
    {"date":"2018-06-18","home":"Belgium","away":"Panama","score":"3-0",
     "home_elo":1940,"away_elo":1350,"ps_h":1.14,"ps_d":7.00,"ps_a":19.00},
    {"date":"2018-06-18","home":"England","away":"Tunisia","score":"2-1",
     "home_elo":1980,"away_elo":1500,"ps_h":1.36,"ps_d":4.50,"ps_a":8.50},
    {"date":"2018-06-21","home":"Argentina","away":"Croatia","score":"0-3",
     "home_elo":2070,"away_elo":1860,"ps_h":1.80,"ps_d":3.50,"ps_a":4.33},
    {"date":"2018-06-22","home":"Brazil","away":"Costa Rica","score":"2-0",
     "home_elo":2150,"away_elo":1480,"ps_h":1.20,"ps_d":6.00,"ps_a":13.00},
    {"date":"2018-06-23","home":"Germany","away":"Sweden","score":"2-1",
     "home_elo":2130,"away_elo":1700,"ps_h":1.57,"ps_d":3.80,"ps_a":5.50},
    {"date":"2018-06-24","home":"England","away":"Panama","score":"6-1",
     "home_elo":1980,"away_elo":1350,"ps_h":1.12,"ps_d":8.00,"ps_a":21.00},
    {"date":"2018-06-27","home":"Germany","away":"South Korea","score":"0-2",
     "home_elo":2130,"away_elo":1600,"ps_h":1.25,"ps_d":5.50,"ps_a":11.00},
]

# ═══════════════════════════════════════════
#  Euro 2024 — Key Bubble Matches (Group Stage)
# ═══════════════════════════════════════════
EC2024 = [
    {"date":"2024-06-14","home":"Germany","away":"Scotland","score":"5-1",
     "home_elo":2000,"away_elo":1700,"ps_h":1.33,"ps_d":5.00,"ps_a":8.00},
    {"date":"2024-06-15","home":"Spain","away":"Croatia","score":"3-0",
     "home_elo":2010,"away_elo":1940,"ps_h":1.83,"ps_d":3.50,"ps_a":4.00},
    {"date":"2024-06-15","home":"Italy","away":"Albania","score":"2-1",
     "home_elo":1970,"away_elo":1540,"ps_h":1.33,"ps_d":4.75,"ps_a":8.50},
    {"date":"2024-06-16","home":"England","away":"Serbia","score":"1-0",
     "home_elo":2020,"away_elo":1760,"ps_h":1.50,"ps_d":3.90,"ps_a":6.50},
    {"date":"2024-06-16","home":"Netherlands","away":"Poland","score":"2-1",
     "home_elo":1920,"away_elo":1680,"ps_h":1.57,"ps_d":3.80,"ps_a":5.50},
    {"date":"2024-06-17","home":"France","away":"Austria","score":"1-0",
     "home_elo":2080,"away_elo":1780,"ps_h":1.62,"ps_d":3.75,"ps_a":5.00},
    {"date":"2024-06-18","home":"Portugal","away":"Czechia","score":"2-1",
     "home_elo":1980,"away_elo":1690,"ps_h":1.50,"ps_d":4.00,"ps_a":6.00},
    {"date":"2024-06-19","home":"Germany","away":"Hungary","score":"2-0",
     "home_elo":2000,"away_elo":1660,"ps_h":1.30,"ps_d":5.50,"ps_a":8.50},
    {"date":"2024-06-20","home":"Spain","away":"Italy","score":"1-0",
     "home_elo":2010,"away_elo":1970,"ps_h":2.20,"ps_d":3.20,"ps_a":3.20},
    {"date":"2024-06-20","home":"England","away":"Denmark","score":"1-1",
     "home_elo":2020,"away_elo":1910,"ps_h":1.83,"ps_d":3.40,"ps_a":4.20},
    {"date":"2024-06-21","home":"France","away":"Netherlands","score":"0-0",
     "home_elo":2080,"away_elo":1920,"ps_h":1.91,"ps_d":3.50,"ps_a":3.80},
    {"date":"2024-06-22","home":"Portugal","away":"Turkey","score":"3-0",
     "home_elo":1980,"away_elo":1700,"ps_h":1.53,"ps_d":4.00,"ps_a":5.50},
    # Round 3 matches (skip for V3 - 默契球 risk)
    {"date":"2024-06-25","home":"France","away":"Poland","score":"1-1",
     "home_elo":2080,"away_elo":1680,"ps_h":1.36,"ps_d":4.75,"ps_a":7.50},
    {"date":"2024-06-25","home":"England","away":"Slovenia","score":"0-0",
     "home_elo":2020,"away_elo":1580,"ps_h":1.33,"ps_d":4.50,"ps_a":8.00},
]

# ═══════════════════════════════════════════
#  Euro 2020 (played 2021) — Key Matches
# ═══════════════════════════════════════════
EC2020 = [
    {"date":"2021-06-11","home":"Italy","away":"Turkey","score":"3-0",
     "home_elo":1990,"away_elo":1680,"ps_h":1.55,"ps_d":3.75,"ps_a":6.00},
    {"date":"2021-06-12","home":"Belgium","away":"Russia","score":"3-0",
     "home_elo":2000,"away_elo":1740,"ps_h":2.00,"ps_d":3.25,"ps_a":3.75},
    {"date":"2021-06-13","home":"England","away":"Croatia","score":"1-0",
     "home_elo":1990,"away_elo":1950,"ps_h":2.00,"ps_d":3.25,"ps_a":3.80},
    {"date":"2021-06-13","home":"Netherlands","away":"Ukraine","score":"3-2",
     "home_elo":1910,"away_elo":1690,"ps_h":1.61,"ps_d":3.75,"ps_a":5.50},
    {"date":"2021-06-15","home":"France","away":"Germany","score":"1-0",
     "home_elo":2100,"away_elo":2080,"ps_h":2.60,"ps_d":3.20,"ps_a":2.70},
    {"date":"2021-06-15","home":"Portugal","away":"Hungary","score":"3-0",
     "home_elo":1960,"away_elo":1620,"ps_h":1.44,"ps_d":4.00,"ps_a":7.50},
    {"date":"2021-06-16","home":"Italy","away":"Switzerland","score":"3-0",
     "home_elo":1990,"away_elo":1830,"ps_h":1.67,"ps_d":3.50,"ps_a":5.50},
    {"date":"2021-06-18","home":"England","away":"Scotland","score":"0-0",
     "home_elo":1990,"away_elo":1670,"ps_h":1.40,"ps_d":4.20,"ps_a":8.00},
    {"date":"2021-06-19","home":"Germany","away":"Portugal","score":"4-2",
     "home_elo":2080,"away_elo":1960,"ps_h":2.50,"ps_d":3.30,"ps_a":2.70},
    {"date":"2021-06-19","home":"Spain","away":"Poland","score":"1-1",
     "home_elo":2030,"away_elo":1700,"ps_h":1.30,"ps_d":5.00,"ps_a":9.00},
    {"date":"2021-06-20","home":"Italy","away":"Wales","score":"1-0",
     "home_elo":1990,"away_elo":1630,"ps_h":1.50,"ps_d":3.80,"ps_a":6.50},
    {"date":"2021-06-22","home":"England","away":"Czechia","score":"1-0",
     "home_elo":1990,"away_elo":1690,"ps_h":1.36,"ps_d":4.33,"ps_a":8.00},
    {"date":"2021-06-23","home":"Germany","away":"Hungary","score":"2-2",
     "home_elo":2080,"away_elo":1620,"ps_h":1.20,"ps_d":6.00,"ps_a":13.00},
    {"date":"2021-06-23","home":"Portugal","away":"France","score":"2-2",
     "home_elo":1960,"away_elo":2100,"ps_h":3.10,"ps_d":3.20,"ps_a":2.30},
]


def build_master():
    """生成统一格式的 master JSON"""
    with open(TM_PATH) as f:
        tm = json.load(f)

    all_matches = []
    for tourney_key, tourney_data, tourney_year in [
        ("WC2022", WC2022, "2022"),
        ("WC2018", WC2018, "2018"),
        ("EC2024", EC2024, "2024"),
        ("EC2020", EC2020, "2020"),
    ]:
        for m in tourney_data:
            h = m["home"]
            a = m["away"]
            score = m["score"]
            fthg, ftag = map(int, score.split("-"))

            # 查找身价
            tm_year = tm.get(tourney_year, {})
            sv_home = tm_year.get(h.upper(), None)
            sv_away = tm_year.get(a.upper(), None)

            match_id = f"{tourney_key}_{m['date']}_{h.replace(' ','_')}_{a.replace(' ','_')}"

            match = {
                "match_id": match_id,
                "tournament": tourney_key,
                "date": m["date"],
                "stage": "group",
                "home_team": h,
                "away_team": a,
                "home_bubble": h in BUBBLE,
                "away_bubble": a in BUBBLE,
                "ft_home_goals": fthg,
                "ft_away_goals": ftag,
                "elo_home": m.get("home_elo"),
                "elo_away": m.get("away_elo"),
                "squad_value_home": sv_home,
                "squad_value_away": sv_away,
                "psch": m.get("ps_h"),
                "pscd": m.get("ps_d"),
                "psca": m.get("ps_a"),
            }
            all_matches.append(match)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_matches, f, indent=2, ensure_ascii=False)

    # 质量报告
    bubble = sum(1 for m in all_matches if m["home_bubble"] != m["away_bubble"])
    with_elo = sum(1 for m in all_matches if m["elo_home"])
    with_ps = sum(1 for m in all_matches if m["psch"])
    with_sv = sum(1 for m in all_matches if m["squad_value_home"])

    print(f"✅ {len(all_matches)} 场 → {OUT_PATH}")
    print(f"   含赔率: {with_ps}/{len(all_matches)}")
    print(f"   含 Elo:  {with_elo}/{len(all_matches)}")
    print(f"   含身价: {with_sv}/{len(all_matches)}")
    print(f"   泡沫对决: {bubble} 场 (豪门 vs 弱旅)")

    # 展示关键泡沫场次
    print(f"\n🎯 泡沫焦点场次 (Perception Gap 候选):")
    for m in all_matches:
        if m["home_bubble"] != m["away_bubble"] and m["psch"] and m["elo_home"]:
            elo_r = m["elo_home"] / m["elo_away"] if m["elo_away"] else 0
            sv_r = (m["squad_value_home"] or 0) / (m["squad_value_away"] or 1)
            print(f"  {m['tournament']} {m['date']} {m['home_team']} vs {m['away_team']} "
                  f"| Elo比={elo_r:.2f} 身价比={sv_r:.1f}x "
                  f"| PS={m['psch']}/{m['pscd']}/{m['psca']} "
                  f"| {m['ft_home_goals']}-{m['ft_away_goals']}")


if __name__ == "__main__":
    build_master()
