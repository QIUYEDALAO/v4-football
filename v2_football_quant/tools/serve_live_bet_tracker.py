#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

try:
    from live_bet_tracker_schema import build_default_record, validate_record
    from live_bet_settlement import settle
    import live_bet_store as store
    from team_cn_resolver import TeamCnResolver
except ModuleNotFoundError:
    # Support package-style import smoke tests: `import tools.serve_live_bet_tracker`.
    from tools.live_bet_tracker_schema import build_default_record, validate_record
    from tools.live_bet_settlement import settle
    from tools import live_bet_store as store
    from tools.team_cn_resolver import TeamCnResolver

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "data/runtime/dashboard"
STATUS = ROOT / "data/runtime/status"
LIVE = ROOT / "data/runtime/live_bets"
TEAM_RESOLVER = TeamCnResolver()


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ensure_control_center_model() -> Path | None:
    """Best-effort: always refresh control-center model before serving API."""
    builder = ROOT / "tools" / "build_v4_control_center_model.py"
    if builder.exists():
        try:
            subprocess.run([sys.executable, str(builder)], cwd=str(ROOT), timeout=20, check=False, capture_output=True, text=True)
        except Exception:
            pass
    # Always return the latest generated model by mtime to avoid UTC/local date mismatch.
    candidates = sorted(STATUS.glob("v4_control_center_model_*.json"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


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
    def _looks_cn(s: str) -> bool:
        return any('\u4e00' <= ch <= '\u9fff' for ch in (s or ""))

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
            home_cn = resolved.get("home_team_cn") or (r.get("home_cn") or r.get("home_team_cn") or r.get("home") or "")
            away_cn = resolved.get("away_team_cn") or (r.get("away_cn") or r.get("away_team_cn") or r.get("away") or "")
            home_src = (resolved.get("team_cn_source") or {}).get("home")
            away_src = (resolved.get("team_cn_source") or {}).get("away")
            # If upstream put Chinese team names into *_en fields, preserve them as CN display instead of "中文名缺失：...".
            if isinstance(home_cn, str) and home_cn.startswith("中文名缺失：") and _looks_cn(home_en):
                home_cn = home_en
                home_src = "en_field_cn_text"
            if isinstance(away_cn, str) and away_cn.startswith("中文名缺失：") and _looks_cn(away_en):
                away_cn = away_en
                away_src = "en_field_cn_text"
            missing = str(home_cn).startswith("中文名缺失：") or str(away_cn).startswith("中文名缺失：")
            rows.append({
                "fixture_id": r.get("fixture_id"),
                "league": r.get("league") or "",
                "home_cn": home_cn,
                "away_cn": away_cn,
                "home_en": resolved.get("home_team_en") or home_en,
                "away_en": resolved.get("away_team_en") or away_en,
                "kickoff_time": r.get("kickoff_display") or "",
                "v4_grade": r.get("grade") or key[0],
                "v4_script": r.get("script_type") or "",
                "ht_model_score": r.get("ht_score"),
                "playbook_script": r.get("playbook_script") or "",
                "fh_goal_dist_0_15_pct": r.get("fh_goal_dist_0_15_pct"),
                "fh_goal_dist_16_30_pct": r.get("fh_goal_dist_16_30_pct"),
                "fh_goal_dist_31_45_pct": r.get("fh_goal_dist_31_45_pct"),
                "fh_goal_dist_total_pct": r.get("fh_goal_dist_total_pct"),
                "fh_goal_dist_source": r.get("fh_goal_dist_source"),
                "official_source": "official_57",
                "candidate_source_date": source_date,
                "team_cn_source": {
                    "home": home_src,
                    "away": away_src,
                    "team_id": (resolved.get("team_cn_source") or {}).get("team_id"),
                    "league_id": (resolved.get("team_cn_source") or {}).get("league_id"),
                    "country": (resolved.get("team_cn_source") or {}).get("country"),
                    "source": (resolved.get("team_cn_source") or {}).get("source"),
                },
                "team_cn_missing": missing,
            })
    return rows


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict):
    b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(b)))
    handler.end_headers()
    handler.wfile.write(b)


def _append_no_market_exclusion(date: str, rec: dict) -> dict:
    path = LIVE / f"v4_no_market_exclusions_{date}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _append_no_bet_decision(date: str, rec: dict) -> dict:
    LIVE.mkdir(parents=True, exist_ok=True)
    path = LIVE / f"v4_no_bet_decisions_{date}.jsonl"
    existing: list[dict] = []
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                existing.append(json.loads(ln))
            except Exception:
                continue
    # de-dup by fixture_id + reason_code + date (replace previous record)
    fid = str(rec.get("fixture_id") or "")
    reason = str(rec.get("reason_code") or "")
    filtered = [
        x for x in existing
        if not (str(x.get("fixture_id") or "") == fid and str(x.get("reason_code") or "") == reason and str(x.get("date") or "") == date)
    ]
    filtered.append(rec)
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in filtered) + "\n", encoding="utf-8")
    return rec


def _read_json(handler: BaseHTTPRequestHandler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8") or "{}")


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path == "/v4_control_center.html":
            p = DASH / "v4_control_center.html"
            if not p.exists():
                self.send_response(404); self.end_headers(); return
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

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

        if u.path == "/v4_league_hit_rate.html":
            p = DASH / "v4_league_hit_rate.html"
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

        if u.path == "/api/live_bets/history":
            days = int(q.get("days", ["30"])[0] or 30)
            days = max(1, min(days, 90))
            live_rows: list[dict] = []
            no_bet_rows: list[dict] = []

            for p in sorted(LIVE.glob("v4_live_bets_*.jsonl"), reverse=True):
                date = p.stem.replace("v4_live_bets_", "")
                if not (len(date) == 8 and date.isdigit()):
                    continue
                if len({x.get("date") for x in live_rows}) >= days:
                    break
                for r in _read_jsonl(p):
                    rr = dict(r)
                    rr["record_type"] = "BET"
                    rr["record_date"] = str(r.get("date") or r.get("bet_date") or date)
                    live_rows.append(rr)

            for p in sorted(LIVE.glob("v4_no_bet_decisions_*.jsonl"), reverse=True):
                date = p.stem.replace("v4_no_bet_decisions_", "")
                if not (len(date) == 8 and date.isdigit()):
                    continue
                if len({x.get("record_date") for x in no_bet_rows}) >= days:
                    break
                for r in _read_jsonl(p):
                    rr = dict(r)
                    rr["record_type"] = "NO_BET"
                    rr["record_date"] = str(r.get("date") or date)
                    no_bet_rows.append(rr)

            rows = live_rows + no_bet_rows
            rows.sort(key=lambda x: str(x.get("recorded_at") or x.get("updated_at") or x.get("created_at") or x.get("record_date") or ""), reverse=True)
            return _json(self, 200, {"ok": True, "days": days, "rows": rows[:500]})

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

        if u.path == "/api/v4_control_center_model":
            model_path = _ensure_control_center_model()
            if not model_path:
                return _json(self, 404, {"ok": False, "error": "model_not_found"})
            model = _load_json(model_path)
            return _json(self, 200, {"ok": True, "model": model})

        if u.path == "/v4_control_center_model.json":
            candidates = sorted(STATUS.glob("v4_control_center_model_*.json"))
            if not candidates:
                self.send_response(404); self.end_headers(); return
            data = candidates[-1].read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if u.path == "/v4_ab_historical_ledger.html":
            p = DASH / "v4_ab_historical_ledger.html"
            if not p.exists():
                self.send_response(404); self.end_headers(); return
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

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

        if u.path == "/api/v4_live_bet/no_bet":
            date = str(payload.get("date") or datetime.utcnow().strftime("%Y%m%d"))
            fixture_id = str(payload.get("fixture_id") or "").strip()
            if not fixture_id:
                return _json(self, 400, {"ok": False, "error": "fixture_id_required"})
            reason_code = str(payload.get("reason_code") or "").strip().upper()
            allowed = {"EARLY_GOAL", "ODDS_MOVED", "NOT_WATCHED", "MANUAL_SKIP", "MARKET_CLOSED", "OTHER"}
            if reason_code not in allowed:
                return _json(self, 400, {"ok": False, "error": "invalid_reason_code"})
            now = datetime.utcnow().isoformat()
            rec = {
                "schema_version": "v4.no_bet_decision.v1",
                "date": date,
                "recorded_at": now,
                "fixture_id": fixture_id,
                "league": payload.get("league") or "",
                "home": payload.get("home") or payload.get("home_cn") or "",
                "away": payload.get("away") or payload.get("away_cn") or "",
                "grade": payload.get("grade") or "",
                "decision": "NO_BET",
                "reason_code": reason_code,
                "reason_text": payload.get("reason_text") or "",
                "planned_line": payload.get("planned_line") or "",
                "planned_odds": payload.get("planned_odds"),
                "planned_stake": payload.get("planned_stake"),
                "planned_entry_minute": payload.get("planned_entry_minute"),
                "counts_as_bet": False,
                "counts_as_stake": False,
                "counts_as_pnl": False,
                "counts_as_turnover": False,
                "counts_as_validation": False,
                "source": "v4_control_center",
                "note": payload.get("note") or "",
            }
            saved = _append_no_bet_decision(date, rec)
            return _json(self, 200, {"ok": True, "record": saved})

        if u.path == "/api/v4_live_bet/no_market":
            date = str(payload.get("date") or datetime.utcnow().strftime("%Y%m%d"))
            fixture_id = str(payload.get("fixture_id") or "").strip()
            if not fixture_id:
                return _json(self, 400, {"ok": False, "error": "fixture_id_required"})
            now = datetime.utcnow().isoformat()
            rec = {
                "schema_version": "v4.no_market_exclusion.v1",
                "date": date,
                "recorded_at": now,
                "fixture_id": fixture_id,
                "league": payload.get("league") or "",
                "home": payload.get("home") or "",
                "away": payload.get("away") or "",
                "grade": payload.get("grade") or "",
                "exclusion_reason": "no_market",
                "exclusion_source": payload.get("source") or "dashboard_manual",
                "reason_text": payload.get("reason_text") or "无盘口/未开盘",
                "excluded_from_betting": True,
                "excluded_from_validation": True,
                "excluded_from_stats": True,
                "action_status": "NO_MARKET",
                "source": "v4_control_center",
                "note": payload.get("note") or "",
            }
            saved = _append_no_market_exclusion(date, rec)
            return _json(self, 200, {"ok": True, "record": saved})

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
