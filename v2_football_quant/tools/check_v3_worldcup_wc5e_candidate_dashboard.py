#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "data/runtime/v3_worldcup/final_squads/v3_wc5d_candidate_review_artifact_20260602.json"
BUILDER = ROOT / "tools/build_v3_worldcup_wc10_war_room.py"
WAR = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
HTML = ROOT / "data/runtime/dashboard/v3_worldcup_wc10_war_room.html"
OUT = ROOT / "data/runtime/status/check_v3_worldcup_wc5e_candidate_dashboard_20260602.json"


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _team_status(teams: list[dict[str, Any]], name: str) -> tuple[str, bool]:
    for t in teams:
        if str(t.get("team_name") or "") == name:
            return str(t.get("candidate_status") or ""), bool(t.get("safe_for_candidate_review"))
    return "", False


def main() -> int:
    checks: list[dict[str, Any]] = []
    add(checks, "wc5d_artifact_exists", ART.exists(), str(ART))
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True, check=False)
    add(checks, "builder_runs", run.returncode == 0, run.stderr or run.stdout[-500:])
    add(checks, "war_json_exists", WAR.exists(), str(WAR))
    add(checks, "dashboard_html_exists", HTML.exists(), str(HTML))

    art = _load(ART)
    war = _load(WAR)
    meta = art.get("meta") if isinstance(art.get("meta"), dict) else {}
    teams = art.get("teams") if isinstance(art.get("teams"), list) else []
    dist = meta.get("status_distribution") if isinstance(meta.get("status_distribution"), dict) else {}

    add(checks, "safe_29", int(meta.get("safe_teams") or 0) == 29, meta.get("safe_teams"))
    add(checks, "hold_19", int(meta.get("hold_teams") or 0) == 19, meta.get("hold_teams"))
    add(checks, "official_false", bool(meta.get("official_final_squad_written")) is False, meta.get("official_final_squad_written"))
    add(checks, "official_confirmed_1", int(dist.get("OFFICIAL_CONFIRMED") or 0) == 1, dist.get("OFFICIAL_CONFIRMED"))
    add(checks, "api_clean_25", int(dist.get("API_CLEAN_CANDIDATE") or 0) == 25, dist.get("API_CLEAN_CANDIDATE"))
    add(checks, "api_wiki_aligned_3", int(dist.get("API_WIKI_ALIGNED_CANDIDATE") or 0) == 3, dist.get("API_WIKI_ALIGNED_CANDIDATE"))
    add(checks, "wiki_overfull_15", int(dist.get("WIKI_PREFERRED_API_POOL_OVERFULL") or 0) == 15, dist.get("WIKI_PREFERRED_API_POOL_OVERFULL"))
    add(checks, "api_incomplete_3", int(dist.get("API_INCOMPLETE_NEED_REVIEW") or 0) == 3, dist.get("API_INCOMPLETE_NEED_REVIEW"))
    add(checks, "provisional_overfull_1", int(dist.get("PROVISIONAL_OVERFULL_NEED_REVIEW") or 0) == 1, dist.get("PROVISIONAL_OVERFULL_NEED_REVIEW"))

    eng = _team_status(teams, "England")
    uzb = _team_status(teams, "Uzbekistan")
    tur = _team_status(teams, "Turkey")
    tur_alt = _team_status(teams, "Turkiye")
    fra = _team_status(teams, "France")
    swe = _team_status(teams, "Sweden")
    hai = _team_status(teams, "Haiti")
    add(checks, "england_safe", eng == ("OFFICIAL_CONFIRMED", True), eng)
    add(checks, "uzbekistan_safe", uzb == ("API_CLEAN_CANDIDATE", True), uzb)
    add(checks, "turkey_hold", tur == ("PROVISIONAL_OVERFULL_NEED_REVIEW", False) or tur_alt == ("PROVISIONAL_OVERFULL_NEED_REVIEW", False), {"Turkey": tur, "Turkiye": tur_alt})
    add(checks, "france_hold", fra == ("API_INCOMPLETE_NEED_REVIEW", False), fra)
    add(checks, "sweden_hold", swe == ("API_INCOMPLETE_NEED_REVIEW", False), swe)
    add(checks, "haiti_hold", hai == ("API_INCOMPLETE_NEED_REVIEW", False), hai)

    csum = war.get("candidate_review_summary") if isinstance(war.get("candidate_review_summary"), dict) else {}
    add(checks, "war_candidate_status", war.get("candidate_review_status") == "CANDIDATE_REVIEW_ONLY", war.get("candidate_review_status"))
    add(checks, "war_official_false", csum.get("official_final_squad_written") is False and csum.get("final_squad_complete") is False, csum)
    add(checks, "war_safe_hold", int(csum.get("teams_safe") or 0) == 29 and int(csum.get("teams_hold") or 0) == 19, csum)

    htxt = HTML.read_text(encoding="utf-8", errors="ignore").lower() if HTML.exists() else ""
    add(checks, "html_has_candidate_block", "candidate review" in htxt and "candidatereviewonly" not in htxt, "candidate review")
    for kw in ["candidate_review_only", "official_final_squad_written", "teams_safe", "teams_hold", "turkey", "不输出投注建议"]:
        add(checks, f"html_has_{kw}", kw in htxt, kw)

    src = BUILDER.read_text(encoding="utf-8", errors="ignore").lower()
    add(checks, "no_api_call", "requests." not in src and "urlopen(" not in src)
    add(checks, "no_web_fetch", "http://" not in src and "https://" not in src)
    add(checks, "no_qq_pending", all(x not in src for x in ["send_qq(", "pending_route("]))
    add(checks, "no_v4_change", "default_rules =" not in src and "ab_ratio_min_pct" not in src and "ab_ratio_max_pct" not in src)

    blockers = [x["name"] for x in checks if not x["ok"]]
    out = {"generated_at": datetime.now().isoformat(), "conclusion": "PASS" if not blockers else "BLOCKER", "blockers": blockers, "checks": checks}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "blockers": blockers, "output": str(OUT)}, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
