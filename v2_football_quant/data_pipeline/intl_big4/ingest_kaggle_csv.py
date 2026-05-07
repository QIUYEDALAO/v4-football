"""
V3 国际大赛 — Kaggle CSV 一站式解析器 (Phase 1+2 合并)
============================================================
直接将 Kaggle 下载的 World Cup/Euro 数据集 (含 Elo + Pinnacle 赔率) 
转化为 V3 引擎终极底座。

⚠️ 前提: 手动从 Kaggle 下载 CSV 放入本目录，命名为 kaggle_wc_euro_master.csv
  搜索词: "FIFA World Cup matches dataset elo odds"

用法:
  python3 data_pipeline/intl_big4/ingest_kaggle_csv.py

输出: engine/v3_config/intl_big4_master.json (含 Elo, 预留 squad_value null)
"""

import csv
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_CSV_PATH = BASE_DIR / "data_pipeline" / "intl_big4" / "kaggle_wc_euro_master.csv"
OUT_PATH = BASE_DIR / "engine" / "v3_config" / "intl_big4_master.json"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ⚠️ 根据你下载的 Kaggle CSV 实际表头修改这里的映射
COLUMN_MAP = {
    "date": "date",
    "home_team": "home_team",
    "away_team": "away_team",
    "home_goals": "home_score",
    "away_goals": "away_score",
    "psch": "odds_h",
    "pscd": "odds_d",
    "psca": "odds_a",
    "elo_home": "home_elo",
    "elo_away": "away_elo",
}

# 泡沫球队 (身价虚高但实际 Elo 不符的伪豪门)
BUBBLE_TEAMS = {
    "FRANCE", "ENGLAND", "BRAZIL", "ARGENTINA", "GERMANY",
    "SPAIN", "PORTUGAL", "NETHERLANDS", "BELGIUM", "ITALY", "CROATIA"
}


def normalize_team(name: str) -> str:
    return name.strip().replace(" ", "_").upper()


def _safe_float(val):
    try:
        return float(val) if val and val != "" else None
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    try:
        return int(float(val)) if val and val != "" else None
    except (ValueError, TypeError):
        return None


def main():
    if not RAW_CSV_PATH.exists():
        print(f"❌ 找不到原始数据文件: {RAW_CSV_PATH}")
        print()
        print("📋 操作步骤:")
        print("  1. 去 Kaggle 搜索: 'FIFA World Cup matches dataset elo odds'")
        print("  2. 下载 CSV, 重命名为 kaggle_wc_euro_master.csv")
        print(f"  3. 放入: {RAW_CSV_PATH.parent}/")
        print("  4. 修改本脚本的 COLUMN_MAP 以匹配你的 CSV 表头")
        print("  5. 重新运行 python data_pipeline/intl_big4/ingest_kaggle_csv.py")
        return

    out = []
    with open(RAW_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # 打印表头，方便核对 COLUMN_MAP
        headers = reader.fieldnames
        print(f"📋 CSV 表头 ({len(headers)} 列):")
        print(f"   {', '.join(headers[:15])}...")
        print()

        for r in reader:
            h_team = normalize_team(r.get(COLUMN_MAP["home_team"], "UNKNOWN"))
            a_team = normalize_team(r.get(COLUMN_MAP["away_team"], "UNKNOWN"))
            date_str = r.get(COLUMN_MAP["date"], "1970-01-01")

            match = {
                "match_id": f"INTL_{date_str[:10]}_{h_team}_{a_team}",
                "date": date_str,
                "home_team": h_team,
                "away_team": a_team,
                "home_bubble": h_team in BUBBLE_TEAMS,
                "away_bubble": a_team in BUBBLE_TEAMS,
                "ft_home_goals": _safe_int(r.get(COLUMN_MAP["home_goals"])),
                "ft_away_goals": _safe_int(r.get(COLUMN_MAP["away_goals"])),
                "psch": _safe_float(r.get(COLUMN_MAP["psch"])),
                "pscd": _safe_float(r.get(COLUMN_MAP["pscd"])),
                "psca": _safe_float(r.get(COLUMN_MAP["psca"])),
                "elo_home": _safe_float(r.get(COLUMN_MAP["elo_home"])),
                "elo_away": _safe_float(r.get(COLUMN_MAP["elo_away"])),
                # 预留 Transfermarkt 身价槽位
                "squad_value_home": None,
                "squad_value_away": None,
            }
            out.append(match)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 质量报告
    with_ps = sum(1 for m in out if m["psch"])
    with_elo = sum(1 for m in out if m["elo_home"] and m["elo_away"])
    bubble = sum(1 for m in out if m["home_bubble"] != m["away_bubble"])

    print(f"✅ {len(out)} 场 → {OUT_PATH}")
    print(f"   含赔率: {with_ps} ({with_ps/len(out)*100:.0f}%)")
    print(f"   含 Elo:  {with_elo} ({with_elo/len(out)*100:.0f}%)")
    print(f"   泡沫对决: {bubble} 场 (豪门 vs 弱旅)")
    print(f"   身价槽位: 0 (待手动填入 tm_values.json)")


if __name__ == "__main__":
    main()
