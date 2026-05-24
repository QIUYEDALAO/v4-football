#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from team_cn_resolver import TeamCnResolver

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(TZ).strftime("%Y%m%d"))
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    args = parser.parse_args()

    pool_path = STATUS / f"v4_outside_57_observation_pool_{args.date}.json"
    if not pool_path.exists():
        print(json.dumps({"ok": False, "reason": "pool_missing", "path": str(pool_path.relative_to(ROOT))}, ensure_ascii=False, indent=2))
        return 1
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    rows = pool.get("fixtures", []) if isinstance(pool, dict) else []
    if not isinstance(rows, list):
        rows = []

    resolver = TeamCnResolver()
    missing = []
    for r in rows:
        out = resolver.resolve_match(
            r.get("home"),
            r.get("away"),
            home_team_cn_hint=r.get("home_team_cn"),
            away_team_cn_hint=r.get("away_team_cn"),
            team_id=r.get("fixture_id"),
            league_id=r.get("league_id"),
            source="outside_57_pool_builder",
        )
        r["home_team_cn"] = out["home_team_cn"]
        r["away_team_cn"] = out["away_team_cn"]
        r["home_team_en"] = out["home_team_en"]
        r["away_team_en"] = out["away_team_en"]
        r["team_cn_source"] = out["team_cn_source"]
        r["team_cn_missing"] = out["team_cn_missing"]
        if out["team_cn_missing"]:
            missing.append({
                "source": "outside_57_pool_builder",
                "date": args.date,
                "fixture_id": r.get("fixture_id"),
                "home_team_en": out["home_team_en"],
                "away_team_en": out["away_team_en"],
                "home_team_cn": out["home_team_cn"],
                "away_team_cn": out["away_team_cn"],
            })

    if args.mode == "apply":
        pool["fixtures"] = rows
        pool_path.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
        miss_path = STATUS / f"missing_team_cn_{args.date}.json"
        payload = {"date": args.date, "missing_count": len(missing), "missing_rows": missing}
        if miss_path.exists():
            try:
                old = json.loads(miss_path.read_text(encoding="utf-8"))
                prev = old.get("missing_rows", []) if isinstance(old, dict) else []
                payload = {"date": args.date, "missing_count": len(prev + missing), "missing_rows": prev + missing}
            except Exception:
                pass
        miss_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "date": args.date,
        "mode": args.mode,
        "fixtures": len(rows),
        "missing_team_cn": len(missing),
        "pool_path": str(pool_path.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
