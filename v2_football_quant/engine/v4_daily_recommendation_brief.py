"""
V4 每日推荐简报（主策略版）
=========================
输出五段：
1) HT A级推荐
2) HT B级推荐
3) HT C级观察
4) HT跳过原因
5) SH观察池（独立）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

REPORT_DIR = BASE_DIR / "data" / "daily_reports"

from engine.v4_match_intelligence import explain_match  # noqa: E402


def _load_records(date_str: str) -> list[dict]:
    key = date_str.replace("-", "")
    p = REPORT_DIR / f"scout_v4_{key}.json"
    if not p.exists():
        raise FileNotFoundError(f"未找到文件: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("results", [])


def _match_name(rec: dict) -> str:
    return f"{rec.get('home','?')} vs {rec.get('away','?')} ({rec.get('league','-')}) #{rec.get('fixture_id','-')}"


def _match_pct(v) -> str:
    try:
        return f"{float(v) * 100:.0f}%"
    except Exception:
        return "-"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--top", type=int, default=20, help="每段最多显示场次")
    args = parser.parse_args()

    records = _load_records(args.date)
    rows = []
    for rec in records:
        intel = explain_match(rec)
        rows.append({"rec": rec, "intel": intel})

    ht_pool = [x for x in rows if (x["intel"].get("ht_recommendation") or {}).get("status", "").startswith("HT_")]
    ht_a = [x for x in ht_pool if (x["intel"].get("ht_recommendation") or {}).get("grade") == "A"]
    ht_b = [x for x in ht_pool if (x["intel"].get("ht_recommendation") or {}).get("grade") == "B"]
    ht_c = [x for x in ht_pool if (x["intel"].get("ht_recommendation") or {}).get("grade") == "C"]
    sh_pool = [x for x in rows if (x["intel"].get("sh_observation") or {}).get("action") == "SH_OBSERVE_ONLY"]
    info_pool = [x for x in rows if x not in ht_pool and x not in sh_pool]
    ht_skip = [
        x for x in ht_pool
        if (x["intel"].get("ht_recommendation") or {}).get("grade") == "SKIP"
    ]

    skip_reasons = Counter()
    for x in ht_skip:
        ht_reason = (x["intel"].get("ht_decision") or {}).get("reason")
        if ht_reason:
            skip_reasons.update([ht_reason])
        else:
            why = x["intel"].get("avoid_if") or []
            skip_reasons.update(why[:2] if why else ["未注明原因"])

    print(f"\nV4_HT 推荐简报 | {args.date}")
    print("=" * 68)
    print(f"总场次: {len(rows)} | HT池: {len(ht_pool)} | A:{len(ht_a)} B:{len(ht_b)} C:{len(ht_c)} SKIP:{len(ht_skip)} | SH观察池: {len(sh_pool)} | 普通情报: {len(info_pool)}")
    print("-" * 68)

    print(f"一、HT A级推荐 ({len(ht_a)})")
    for x in ht_a[: args.top]:
        i = x["intel"]
        hr = i.get("ht_recommendation") or {}
        print(f"- { _match_name(x['rec']) } | A级 | {hr.get('script_type','-')} | HT率 {_match_pct(hr.get('h2h_ht_goal_rate'))}")
    if not ht_a:
        print("- 无")

    print(f"\n二、HT B级推荐 ({len(ht_b)})")
    for x in ht_b[: args.top]:
        i = x["intel"]
        hr = i.get("ht_recommendation") or {}
        print(f"- { _match_name(x['rec']) } | B级 | {hr.get('script_type','-')} | HT率 {_match_pct(hr.get('h2h_ht_goal_rate'))}")
    if not ht_b:
        print("- 无")

    print(f"\n三、HT C级观察 ({len(ht_c)})")
    for x in ht_c[: args.top]:
        i = x["intel"]
        hr = i.get("ht_recommendation") or {}
        print(f"- { _match_name(x['rec']) } | C级观察 | {hr.get('reason','-')}")
    if not ht_c:
        print("- 无")

    print(f"\n四、跳过原因 ({len(ht_skip)})")
    if skip_reasons:
        for reason, cnt in skip_reasons.most_common(10):
            print(f"- {reason}: {cnt}")
    else:
        print("- 无")

    print(f"\n五、SH观察池（不计入HT主推荐） ({len(sh_pool)})")
    for x in sh_pool[: args.top]:
        i = x["intel"]
        print(f"- { _match_name(x['rec']) } | SH观察 | {(i.get('sh_observation') or {}).get('reason','-')}")
    if not sh_pool:
        print("- 无")

    print("\n完成。")


if __name__ == "__main__":
    main()
