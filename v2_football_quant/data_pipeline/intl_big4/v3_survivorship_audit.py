"""
V3 幸存者偏差审计 (Survivorship Bias Audit)
=============================================
拷问那 88 场极度泡沫区数据：豪门到底有多大概率翻车？

用法:
  python3 data_pipeline/intl_big4/v3_survivorship_audit.py
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MASTER_PATH = BASE_DIR / "engine" / "v3_config" / "intl_big4_master.json"


def run_survivorship_audit():
    with open(MASTER_PATH, "r") as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    df = df.dropna(subset=['squad_value_home', 'squad_value_away', 'elo_home', 'elo_away'])
    df['val_ratio'] = df['squad_value_home'] / df['squad_value_away']
    df['elo_ratio'] = df['elo_home'] / df['elo_away']
    df['perception_gap'] = np.log(df['val_ratio']) - np.log(df['elo_ratio'])

    # 极度泡沫区 (Gap > 1.0 且 赔率显示强队)
    extreme = df[(df['perception_gap'] > 1.0) & (df['psch'] <= 1.45)]

    print("=" * 55)
    print(f"🛡️ V3 幸存者偏差审计 (Perception Gap > 1.0 & PSCH <= 1.45)")
    print("=" * 55)
    print(f"N = {len(extreme)} 场\n")

    wins = len(extreme[extreme['ft_home_goals'] > extreme['ft_away_goals']])
    draws = len(extreme[extreme['ft_home_goals'] == extreme['ft_away_goals']])
    losses = len(extreme[extreme['ft_home_goals'] < extreme['ft_away_goals']])

    print(f"✅ 豪门打穿泡沫: {wins} 场 ({wins/len(extreme)*100:.1f}%)")
    print(f"🤝 平局 (下盘收米): {draws} 场 ({draws/len(extreme)*100:.1f}%)")
    print(f"🔥 爆冷 (下盘收米): {losses} 场 ({losses/len(extreme)*100:.1f}%)")
    print(f"🟢 下盘不败合计: {draws+losses} 场 ({(draws+losses)/len(extreme)*100:.1f}%)")
    print("=" * 55)

    if draws + losses > 0:
        print("\n💥 翻车明细:")
        for _, r in extreme.iterrows():
            if r['ft_home_goals'] <= r['ft_away_goals']:
                print(f"  {r['date']} {r['home_team']} {int(r['ft_home_goals'])}-{int(r['ft_away_goals'])} {r['away_team']} "
                      f"| Gap={r['perception_gap']:.2f} | PS={r['psch']}/{r['pscd']}/{r['psca']}")


if __name__ == "__main__":
    run_survivorship_audit()
