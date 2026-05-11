"""
football-data.co.uk 历史数据导入器（V4增强版）
===========================================
目标：
1) 批量下载多联赛多赛季 CSV
2) 标准化成统一字段，供 V4 回测 / 分层阈值 / walk-forward 使用
3) 输出 JSONL（流式友好）+ 汇总报告

用法：
  python3 data_pipeline/ingest_football_data_history.py
  python3 data_pipeline/ingest_football_data_history.py --seasons 2324,2223,2122 --leagues E0,D1,I1,SP1,F1

输出：
  data/historical/fd_history_matches.jsonl
  data/historical/fd_history_summary.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import ssl
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import certifi

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "historical"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.football-data.co.uk/mmz4281"

DEFAULT_LEAGUES = ["E0", "D1", "I1", "SP1", "F1"]
LEAGUE_NAME_MAP = {
    "E0": "英超",
    "E1": "英冠",
    "D1": "德甲",
    "D2": "德乙",
    "I1": "意甲",
    "I2": "意乙",
    "SP1": "西甲",
    "SP2": "西乙",
    "F1": "法甲",
    "F2": "法乙",
    "N1": "荷甲",
    "P1": "葡超",
    "B1": "比甲",
    "T1": "土超",
}
DEFAULT_SEASONS = ["2526", "2425", "2324", "2223", "2122"]


def _to_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except Exception:
        return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def _pick(row: dict, *keys: str):
    for k in keys:
        if k in row and row[k] not in ("", None):
            return row[k]
    return None


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def _fetch_csv(url: str) -> list[dict]:
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={"User-Agent": "V4-History-Loader/1.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        raw = resp.read()
    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [r for r in reader]


def _normalize_row(row: dict, season: str, league_code: str) -> dict | None:
    date_iso = _parse_date(_pick(row, "Date"))
    home = _pick(row, "HomeTeam")
    away = _pick(row, "AwayTeam")
    if not date_iso or not home or not away:
        return None

    hthg = _to_int(_pick(row, "HTHG"))
    htag = _to_int(_pick(row, "HTAG"))
    fthg = _to_int(_pick(row, "FTHG"))
    ftag = _to_int(_pick(row, "FTAG"))
    if hthg is None or htag is None or fthg is None or ftag is None:
        return None

    sh_home = fthg - hthg
    sh_away = ftag - htag
    sh_goals = max(0, sh_home + sh_away)
    ht_goals = hthg + htag
    ft_goals = fthg + ftag

    # 主流赔率列（不同赛季列名不一致，按优先级挑）
    h_odds = _to_float(_pick(row, "PSCH", "B365H", "AvgH"))
    d_odds = _to_float(_pick(row, "PSCD", "B365D", "AvgD"))
    a_odds = _to_float(_pick(row, "PSCA", "B365A", "AvgA"))

    # O/U 2.5 常见列
    over25 = _to_float(_pick(row, "B365>2.5", "Avg>2.5", "P>2.5"))
    under25 = _to_float(_pick(row, "B365<2.5", "Avg<2.5", "P<2.5"))

    return {
        "source": "football-data.co.uk",
        "season": season,
        "league_code": league_code,
        "league_name": LEAGUE_NAME_MAP.get(league_code, league_code),
        "match_date": date_iso,
        "home_team": home,
        "away_team": away,
        "ht_home_goals": hthg,
        "ht_away_goals": htag,
        "ht_goals": ht_goals,
        "sh_home_goals": sh_home,
        "sh_away_goals": sh_away,
        "sh_goals": sh_goals,
        "ft_home_goals": fthg,
        "ft_away_goals": ftag,
        "ft_goals": ft_goals,
        "ht_result": "H" if hthg > htag else ("D" if hthg == htag else "A"),
        "ft_result": "H" if fthg > ftag else ("D" if fthg == ftag else "A"),
        "odds_h": h_odds,
        "odds_d": d_odds,
        "odds_a": a_odds,
        "odds_over25": over25,
        "odds_under25": under25,
    }


def ingest(seasons: list[str], leagues: list[str], sleep_sec: float = 0.35) -> dict:
    out_rows: list[dict] = []
    errors: list[dict] = []
    request_count = 0
    for season in seasons:
        for league in leagues:
            url = f"{BASE_URL}/{season}/{league}.csv"
            request_count += 1
            try:
                print(f"下载 {season}/{league} ...", end=" ")
                rows = _fetch_csv(url)
                normalized = []
                for r in rows:
                    nr = _normalize_row(r, season, league)
                    if nr:
                        normalized.append(nr)
                out_rows.extend(normalized)
                print(f"OK {len(normalized)} 场")
            except Exception as exc:
                errors.append({"season": season, "league": league, "url": url, "error": str(exc)})
                print(f"FAIL {str(exc)[:80]}")
            time.sleep(sleep_sec)

    out_path = OUT_DIR / "fd_history_matches.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    league_dist: dict[str, int] = {}
    for r in out_rows:
        key = r["league_code"]
        league_dist[key] = league_dist.get(key, 0) + 1

    summary = {
        "generated_at": datetime.now().isoformat(),
        "source": "football-data.co.uk",
        "requests": request_count,
        "seasons": seasons,
        "leagues": leagues,
        "rows_total": len(out_rows),
        "errors": errors,
        "error_count": len(errors),
        "league_distribution": league_dist,
        "output_jsonl": str(out_path),
    }
    summary_path = OUT_DIR / "fd_history_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", default=",".join(DEFAULT_SEASONS), help="如 2526,2425,2324")
    parser.add_argument("--leagues", default=",".join(DEFAULT_LEAGUES), help="如 E0,D1,I1,SP1,F1")
    parser.add_argument("--sleep", type=float, default=0.35, help="请求间隔秒")
    args = parser.parse_args()

    seasons = [x.strip() for x in args.seasons.split(",") if x.strip()]
    leagues = [x.strip() for x in args.leagues.split(",") if x.strip()]
    summary = ingest(seasons=seasons, leagues=leagues, sleep_sec=args.sleep)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

