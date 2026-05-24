#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from live_bet_tracker_schema import build_default_record, validate_record
from live_bet_settlement import settle
import live_bet_store as store
from team_cn_resolver import TeamCnResolver

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "data/runtime/dashboard"
STATUS = ROOT / "data/runtime/status"
TEAM_RESOLVER = TeamCnResolver()


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resolve_candidate_view(date: str) -> tuple[dict, str, bool]:
    exact = STATUS / f"v3v4_dashboard_candidate_view_{date}.json"
    if exact.exists():
        return _load_json(exact), date, False
    candidates = sorted(STATUS.glob("v3v4_dashboard_candidate_view_*.json"))
    dated = []
    for p in candidates:
        d = p.stem.split("_")[-1]
        if d.isdigit() and d <= date:
            dated.append((d, p))
    if dated:
        d, p = dated[-1]
        return _load_json(p), d, True
    return {}, "", True


def _normalize_candidate_rows(view: dict, source_date: str) -> list[dict]:
    rows = []
    for key in ("A_candidates", "B_candidates"):
        for r in (view.get(key) or []):
            if not isinstance(r, dict):
                continue
            home_en = r.get("home_en") or r.get("home_team_en") or r.get("home") or ""
            away_en = r.get("away_en") or r.get("away_team_en") or r.get("away") or ""
            home_cn_raw = r.get("home_cn") or r.get("home_team_cn") or ""
            away_cn_raw = r.get("away_cn") or r.get("away_team_cn") or ""
            if isinstance(home_cn_raw, str) and home_cn_raw.startswith("中文名缺失："):
                home_cn_raw = ""
            if isinstance(away_cn_raw, str) and away_cn_raw.startswith("中文名缺失："):
                away_cn_raw = ""
            resolved = TEAM_RESOLVER.resolve_match(
                home_team_en=home_en,
                away_team_en=away_en,
                home_team_cn_hint=home_cn_raw,
                away_team_cn_hint=away_cn_raw,
                source=f"candidate_view:{source_date}",
            )
            rows.append({
                "fixture_id": r.get("fixture_id"),
                "league": r.get("league") or "",
                "home_cn": resolved.get("home_team_cn") or (r.get("home_cn") or r.get("home_team_cn") or r.get("home") or ""),
                "away_cn": resolved.get("away_team_cn") or (r.get("away_cn") or r.get("away_team_cn") or r.get("away") or ""),
                "home_en": resolved.get("home_team_en") or home_en,
                "away_en": resolved.get("away_team_en") or away_en,
                "kickoff_time": r.get("kickoff_display") or "",
                "v4_grade": r.get("grade") or key[0],
                "v4_script": r.get("script_type") or "",
                "ht_model_score": r.get("ht_score"),
                "official_source": "official_57",
                "candidate_source_date": source_date,
                "team_cn_source": resolved.get("team_cn_source"),
                "team_cn_missing": resolved.get("team_cn_missing"),
            })
    return rows


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict):
    b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(b)))
    handler.end_headers()
    handler.wfile.write(b)


def _read_json(handler: BaseHTTPRequestHandler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8") or "{}")


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path == "/live_bet_tracker.html":
            p = DASH / "live_bet_tracker.html"
            if not p.exists():
                self.send_response(404); self.end_headers(); return
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if u.path == "/api/live_bets":
            date = q.get("date", [datetime.utcnow().strftime("%Y%m%d")])[0]
            return _json(self, 200, {"ok": True, "date": date, "records": store.get_day_records(date)})

        if u.path == "/api/live_bets/summary":
            date = q.get("date", [datetime.utcnow().strftime("%Y%m%d")])[0]
            return _json(self, 200, {"ok": True, "summary": store.day_summary(date)})

        if u.path == "/api/live_bets/cumulative":
            return _json(self, 200, {"ok": True, "summary": store.cumulative_summary()})

        if u.path == "/api/live_bets/candidates":
            date = q.get("date", [datetime.utcnow().strftime("%Y%m%d")])[0]
            view, source_date, fallback = _resolve_candidate_view(date)
            rows = _normalize_candidate_rows(view, source_date)
            semantics = {
                "book_date": date,
                "candidate_batch_date": source_date or None,
                "note": "扫描批次可早于开赛日；例如 20260524 批次可包含 20260525 凌晨比赛。",
            }
            return _json(self, 200, {
                "ok": True,
                "date": date,
                "candidate_source_date": source_date or None,
                "fallback_used": fallback,
                "semantics": semantics,
                "rows": rows,
            })

        return _json(self, 404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            payload = _read_json(self)
        except Exception as e:
            return _json(self, 400, {"ok": False, "error": f"invalid_json:{e}"})

        if u.path == "/api/live_bets/add":
            rec = build_default_record(payload)
            ok, msg = validate_record(rec)
            if not ok:
                return _json(self, 400, {"ok": False, "error": msg})
            store.add_bet(rec)
            return _json(self, 200, {"ok": True, "record": rec})

        if u.path == "/api/live_bets/update":
            date = str(payload.get("date") or "")
            bet_id = str(payload.get("bet_id") or "")
            patch = payload.get("patch") or {}
            r = store.update_bet(date, bet_id, patch)
            if not r:
                return _json(self, 404, {"ok": False, "error": "bet_not_found"})
            return _json(self, 200, {"ok": True, "record": r})

        if u.path == "/api/live_bets/settle":
            date = str(payload.get("date") or "")
            bet_id = str(payload.get("bet_id") or "")
            ht_goals = int(payload.get("ht_goal_count"))
            stake = float(payload.get("stake"))
            odds = float(payload.get("odds_water"))
            line = str(payload.get("market_line"))
            rebate_rate = float(payload.get("rebate_rate") or 0.025)
            st = settle(stake, odds, line, ht_goals, rebate_rate)
            st["ht_goal_count"] = ht_goals
            r = store.settle_bet(date, bet_id, st)
            if not r:
                return _json(self, 404, {"ok": False, "error": "bet_not_found"})
            return _json(self, 200, {"ok": True, "record": r})

        if u.path == "/api/live_bets/void":
            date = str(payload.get("date") or "")
            bet_id = str(payload.get("bet_id") or "")
            reason = str(payload.get("reason") or "")
            r = store.void_bet(date, bet_id, reason)
            if not r:
                return _json(self, 404, {"ok": False, "error": "bet_not_found"})
            return _json(self, 200, {"ok": True, "record": r})

        return _json(self, 404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt, *args):
        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), H)
    print(f"live_bet_tracker_server running on http://{args.host}:{args.port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
