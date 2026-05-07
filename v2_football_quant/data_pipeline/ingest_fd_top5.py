"""
数据炼油厂: football-data.co.uk 五大联赛历史数据下载与清洗 (Step 1)
===================================================================
自动化下载英、德、意、西、法 过去3-4赛季的 CSV，提取半场进球 + 平博收盘赔率。

用法:
  python3 data_pipeline/ingest_fd_top5.py

输出: data_pipeline/data/top5_fd_raw.json
"""

import pandas as pd
import requests
import json
import time
import ssl
import certifi
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data_pipeline" / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 五大联赛 football-data.co.uk 代码
# E0=英超, E1=英冠(暂不取), D1=德甲, I1=意甲, SP1=西甲, F1=法甲
TOP5_LEAGUES = ['E0', 'D1', 'I1', 'SP1', 'F1']
LEAGUE_NAMES = {'E0': '英超', 'D1': '德甲', 'I1': '意甲', 'SP1': '西甲', 'F1': '法甲'}
SEASONS = ['2324', '2223', '2122', '2021']  # 过去4个赛季

def download_and_clean():
    all_dfs = []
    total_rows = 0
    errors = 0

    for season in SEASONS:
        for league in TOP5_LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            try:
                print(f"  下载 {season} {LEAGUE_NAMES[league]} ({league})...", end=" ")
                ctx = ssl.create_default_context(cafile=certifi.where())
                resp = urllib.request.urlopen(urllib.request.Request(url), context=ctx, timeout=15)
                df = pd.read_csv(resp, usecols=[
                    'Date', 'HomeTeam', 'AwayTeam',
                    'HTHG', 'HTAG',
                    'PSCH', 'PSCD', 'PSCA'
                ])
                df['season'] = season
                df['league_code'] = league
                df['league_name'] = LEAGUE_NAMES[league]
                all_dfs.append(df)
                total_rows += len(df)
                print(f"✅ {len(df)} 场")
            except Exception as e:
                errors += 1
                print(f"❌ {str(e)[:60]}")

            time.sleep(0.5)  # 礼貌请求

    if not all_dfs:
        print("❌ 未获取到任何数据")
        return

    master_df = pd.concat(all_dfs, ignore_index=True)

    # 日期转换
    master_df['Date'] = pd.to_datetime(master_df['Date'], dayfirst=True, errors='coerce')
    master_df = master_df.dropna(subset=['Date'])

    # 剔除无赔率或半场数据的行
    master_df = master_df.dropna(subset=['HTHG', 'HTAG', 'PSCH', 'PSCD', 'PSCA'])

    # 半场结果标签
    def ht_result(row):
        if row['HTHG'] > row['HTAG']: return 'H'
        elif row['HTHG'] == row['HTAG']: return 'D'
        else: return 'A'

    master_df['HT_Result'] = master_df.apply(ht_result, axis=1)

    # 保存
    output_path = OUTPUT_DIR / "top5_fd_raw.json"
    master_df.to_json(output_path, orient='records', indent=2, force_ascii=False)

    print(f"\n✅ 完成: {total_rows} 场原始数据 → {output_path}")
    print(f"   失败: {errors} 个请求")
    print(f"   有效: {len(master_df)} 场 (去空后)")
    print(f"   日期范围: {master_df['Date'].min()} ~ {master_df['Date'].max()}")
    print(f"   联赛分布: {master_df['league_name'].value_counts().to_dict()}")
    print(f"   HT结果分布: {master_df['HT_Result'].value_counts(normalize=True).to_dict()}")

if __name__ == "__main__":
    download_and_clean()
