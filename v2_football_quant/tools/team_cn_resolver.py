#!/usr/bin/env python3
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEAM_CN_MAP = ROOT / "engine/team_cn_map.json"
TEAM_CN_ALIASES = ROOT / "data/config/team_cn_aliases.json"


class TeamCnResolver:
    def __init__(self) -> None:
        self.map_exact: dict[str, str] = {}
        self.map_norm: dict[str, str] = {}
        self.map_by_team_id: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        exact_all: dict[str, str] = {}
        if TEAM_CN_MAP.exists():
            raw = json.loads(TEAM_CN_MAP.read_text(encoding="utf-8"))
            exact = raw.get("exact", {}) if isinstance(raw, dict) else {}
            if isinstance(exact, dict):
                exact_all.update({k: v for k, v in exact.items() if isinstance(k, str) and isinstance(v, str)})
        if TEAM_CN_ALIASES.exists():
            raw2 = json.loads(TEAM_CN_ALIASES.read_text(encoding="utf-8"))
            exact2 = raw2.get("exact", {}) if isinstance(raw2, dict) else {}
            if isinstance(exact2, dict):
                exact_all.update({k: v for k, v in exact2.items() if isinstance(k, str) and isinstance(v, str)})
            by_id = raw2.get("by_team_id", {}) if isinstance(raw2, dict) else {}
            if isinstance(by_id, dict):
                self.map_by_team_id = {str(k): str(v) for k, v in by_id.items() if str(v).strip()}
        self.map_exact = exact_all
        self.map_norm = {self._norm(k): v for k, v in exact_all.items() if isinstance(k, str) and isinstance(v, str)}

    @staticmethod
    def _norm(s: Any) -> str:
        text = str(s or "").strip().replace("_", " ").replace("/", " ").replace(".", " ")
        # strip accent marks (Peñarol -> Penarol)
        text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
        text = text.lower()
        # normalize common suffix noise
        tokens = [tok for tok in text.split() if tok not in {"fc", "cf"}]
        return " ".join(tokens)

    def resolve_one(self, team_name_en: Any, team_cn_hint: Any = None, team_id: Any = None) -> tuple[str, str, bool, str]:
        en = str(team_name_en or "").strip() or "UNKNOWN"
        hint = str(team_cn_hint or "").strip()
        if hint:
            return hint, en, False, "source_hint"
        tid = str(team_id) if team_id is not None else ""
        if tid and tid in self.map_by_team_id:
            return self.map_by_team_id[tid], en, False, "team_id_map"
        if en in self.map_exact:
            return self.map_exact[en], en, False, "exact_map"
        n = self._norm(en)
        if n in self.map_norm:
            return self.map_norm[n], en, False, "norm_map"
        # Keep active display clean: fallback to original EN name when CN is missing.
        return en, en, True, "missing"

    def resolve_match(self,
                      home_team_en: Any,
                      away_team_en: Any,
                      *,
                      home_team_cn_hint: Any = None,
                      away_team_cn_hint: Any = None,
                      team_id: Any = None,
                      league_id: Any = None,
                      country: Any = None,
                      source: Any = None) -> dict[str, Any]:
        h_cn, h_en, h_missing, h_src = self.resolve_one(home_team_en, home_team_cn_hint, team_id=team_id)
        a_cn, a_en, a_missing, a_src = self.resolve_one(away_team_en, away_team_cn_hint, team_id=team_id)
        return {
            "home_team_cn": h_cn,
            "away_team_cn": a_cn,
            "home_team_en": h_en,
            "away_team_en": a_en,
            "team_cn_source": {
                "home": h_src,
                "away": a_src,
                "team_id": team_id,
                "league_id": league_id,
                "country": country,
                "source": source,
            },
            "team_cn_missing": bool(h_missing or a_missing),
        }


def build_missing_team_cn(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_rows = [r for r in rows if r.get("team_cn_missing")]
    return {
        "missing_count": len(missing_rows),
        "missing_rows": missing_rows,
    }


if __name__ == "__main__":
    import argparse
    from datetime import datetime, timezone, timedelta

    TZ = timezone(timedelta(hours=8))
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(TZ).strftime("%Y%m%d"))
    args = parser.parse_args()

    out = ROOT / "data/runtime/status" / f"missing_team_cn_{args.date}.json"
    out.write_text(json.dumps({"date": args.date, "missing_count": 0, "missing_rows": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
