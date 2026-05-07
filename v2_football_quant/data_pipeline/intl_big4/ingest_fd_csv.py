"""
V3 国际大赛 — 原始 CSV 清洗与标准化 (Phase 1)
==================================================
将 football-data.co.uk 的 4 届大赛 CSV 吃进系统，
生成统一格式的 intl_big4_master.json。

关键操作:
  - build_match_id(): 跨数据源 JOIN 的统一钥匙
  - normalize_team(): 球队名标准化 (如 "Korea Republic" → "South Korea")
  - 预留 home_elo/away_elo/home_value/away_value null 槽位

用法:
  python3 data_pipeline/intl_big4/ingest_fd_csv.py

输出: engine/v3_config/intl_big4_master.json
"""

import json
import ssl
import time
import urllib.request
import pandas as pd
import io
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = BASE_DIR / "engine" / "v3_config" / "intl_big4_master.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── 数据源 ──
FILES = {
    "WC2018": "1819/WC.csv",
    "WC2022": "2223/WC.csv",
    "EC2020": "2021/EC.csv",
    "EC2024": "2324/EC.csv",
}
BASE_URL = "https://www.football-data.co.uk/mmz4281"

# ── 球队名标准化 (football-data.co.uk → Transfermarkt/Elo 通用名) ──
NAME_NORMALIZE = {
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "USA": "United States",
    "IR Iran": "Iran",
    "Côte d'Ivoire": "Ivory Coast",
    "Czech Republic": "Czechia",
    "Czechia": "Czechia",
    "Bosnia-Herzegovina": "Bosnia",
    "North Macedonia": "North Macedonia",
    "Serbia": "Serbia",
    "Slovakia": "Slovakia",
    "Slovenia": "Slovenia",
}

# ── 泡沫球队标签 ──
BUBBLE_TEAMS = {
    "Brazil", "France", "England", "Germany", "Spain", "Argentina",
    "Portugal", "Netherlands", "Italy", "Belgium", "Croatia"
}

# ── 赛事阶段推断 ──
TOURNAMENT_DATES = {
    "WC2018": ("2018-06-14", "2018-07-15"),
    "WC2022": ("2022-11-20", "2022-12-18"),
    "EC2020": ("2021-06-11", "2021-07-11"),
    "EC2024": ("2024-06-14", "2024-07-14"),
}

GROUP_CUTOFF = {
    "WC2018": "2018-06-28",   # 小组赛最后一天
    "WC2022": "2022-12-02",
    "EC2020": "2021-06-23",
    "EC2024": "2024-06-26",
}


def infer_stage(date_str, tournament):
    """推断比赛阶段: group / knockout / qualifier"""
    dates = TOURNAMENT_DATES.get(tournament)
    if not dates:
        return "unknown"
    
    try:
        # football-data.co.uk 日期格式: dd/mm/yy 或 dd/mm/yyyy
        for fmt in ["%d/%m/%Y", "%d/%m/%y"]:
            try:
                d = datetime.strptime(date_str, fmt)
                break
            except:
                continue
        
        start = datetime.strptime(dates[0], "%Y-%m-%d")
        end = datetime.strptime(dates[1], "%Y-%m-%d")
        cutoff = datetime.strptime(GROUP_CUTOFF.get(tournament, dates[1]), "%Y-%m-%d")
        
        if d < start or d > end:
            return "qualifier"
        if d <= cutoff:
            return "group"
        return "knockout"
    except Exception:
        return "unknown"


def normalize_team(name):
    return NAME_NORMALIZE.get(name, name)


def build_match_id(date_str, home, away, tournament):
    """跨数据源统一 JOIN 钥匙"""
    h = normalize_team(home).lower().replace(" ", "_")
    a = normalize_team(away).lower().replace(" ", "_")
    d = date_str.replace("/", "-")[:10] if date_str else "unknown"
    return f"{tournament}_{d}_{h}_vs_{a}"


def ingest():
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    all_matches = []
    stats = {}

    for tournament, path in FILES.items():
        url = f"{BASE_URL}/{path}"
        print(f"📥 {tournament}...", end=" ")

        req = urllib.request.Request(url, headers={"User-Agent": "V2-Football-Quant/1.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            raw = resp.read()

        for enc in ["latin-1", "utf-8", "cp1252"]:
            try:
                df = pd.read_csv(io.StringIO(raw.decode(enc)))
                break
            except Exception:
                continue

        df = df[df["FTHG"].notna()]
        count = 0

        for idx, row in df.iterrows():
            home = str(row.get("HomeTeam", ""))
            away = str(row.get("AwayTeam", ""))
            date_str = str(row.get("Date", ""))

            match = {
                "match_id": build_match_id(date_str, home, away, tournament),
                "tournament": tournament,
                "date": date_str,
                "stage": infer_stage(date_str, tournament),
                "home": normalize_team(home),
                "away": normalize_team(away),
                "home_bubble": normalize_team(home) in BUBBLE_TEAMS,
                "away_bubble": normalize_team(away) in BUBBLE_TEAMS,
                # 比分
                "FTHG": int(row["FTHG"]),
                "FTAG": int(row["FTAG"]),
            }

            # 半场
            if "HTHG" in df.columns:
                try:
                    match["HTHG"] = int(row["HTHG"]) if pd.notna(row["HTHG"]) else None
                    match["HTAG"] = int(row["HTAG"]) if pd.notna(row["HTAG"]) else None
                except (ValueError, TypeError):
                    match["HTHG"] = match["HTAG"] = None

            # Pinnacle 收盘
            for col, key in [("PSCH", "H"), ("PSCD", "D"), ("PSCA", "A")]:
                if col in df.columns and pd.notna(row.get(col)):
                    match[f"PS_{key}"] = float(row[col])

            # Bet365 备用
            for col, key in [("B365H", "H"), ("B365D", "D"), ("B365A", "A")]:
                if col in df.columns and pd.notna(row.get(col)):
                    match[f"B365_{key}"] = float(row[col])

            # ── 预留 alt-data 槽位 (null 不阻塞) ──
            match["home_elo"] = None
            match["away_elo"] = None
            match["home_value"] = None     # 百万欧元
            match["away_value"] = None

            all_matches.append(match)
            count += 1

        stats[tournament] = count
        print(f"{count} 场 ✅")
        time.sleep(1)

    # ── 保存 ──
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_matches, f, indent=2, ensure_ascii=False)

    # ── 质量报告 ──
    total = len(all_matches)
    with_ps = sum(1 for m in all_matches if m.get("PS_H"))
    with_ht = sum(1 for m in all_matches if m.get("HTHG") is not None)
    group_only = sum(1 for m in all_matches if m["stage"] == "group")
    bubble_matches = sum(1 for m in all_matches if m["home_bubble"] != m["away_bubble"])

    print(f"\n✅ {OUTPUT_PATH}")
    print(f"   总计: {total} 场")
    print(f"   小组赛: {group_only} | 淘汰赛: {total - group_only}")
    print(f"   Pinnacle赔率: {with_ps} ({with_ps/total*100:.0f}%)")
    print(f"   半场数据: {with_ht} ({with_ht/total*100:.0f}%)")
    print(f"   泡沫对决: {bubble_matches} 场 (豪门 vs 弱旅)")
    print(f"   Elo槽位: 0 (待填) | 身价槽位: 0 (待填)")

    if bubble_matches > 0:
        print(f"\n🎯 泡沫焦点矩阵 (前 15 场):")
        print(f"{'赛会':<8} {'日期':<12} {'主队':<20} {'客队':<20} {'比分':<6} {'Pinnacle 1X2'}")
        print("-" * 85)
        for m in all_matches:
            if m["home_bubble"] != m["away_bubble"] and m["stage"] == "group" \
               and m.get("PS_H"):
                print(f"{m['tournament']:<8} {m['date'][:10]:<12} "
                      f"{m['home']:<20} {m['away']:<20} "
                      f"{m['FTHG']}-{m['FTAG']:<4} "
                      f"H={m.get('PS_H','?')} D={m.get('PS_D','?')} A={m.get('PS_A','?')}")


if __name__ == "__main__":
    ingest()
