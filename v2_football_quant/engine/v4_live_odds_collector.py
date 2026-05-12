from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine import net_utils
from engine.execution_cost_model import estimate_execution_cost
from engine.live_capture_profile import load_profile, tier_conf
from engine.data_sources.api_football_live_odds import (
    fetch_fixture_events as api_fetch_fixture_events,
    fetch_fixture_state as api_fetch_fixture_state,
    fetch_fixture_statistics as api_fetch_fixture_statistics,
    fetch_live_odds_paged,
)
from engine.data_sources.market_normalizer import (
    extract_line,
    is_allowed_line,
    is_ht_ou_market_name,
    normalize_line,
)

try:
    from logger import logger
except ModuleNotFoundError:
    from engine.logger import logger

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
SNAP_DIR = BASE_DIR / "data" / "live_odds_snapshots"
EXEC_DIR = BASE_DIR / "data" / "execution"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _as_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_utc_iso(raw: str) -> str:
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return raw
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _walk_live_books(resp: dict) -> list[dict]:
    books = []
    for entry in (resp or {}).get("response", []) or []:
        if "bookmakers" in entry:
            books.extend(entry.get("bookmakers", []) or [])
        elif "odds" in entry:
            books.append({"name": entry.get("bookmaker", "LIVE"), "bets": entry.get("odds", [])})
        elif "bets" in entry:
            books.append({"name": entry.get("bookmaker", "LIVE"), "bets": entry.get("bets", [])})
    return books


def _safe_rows(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    rows = resp.get("response")
    return rows if isinstance(rows, list) else []


def _num(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, str):
        value = value.replace("%", "").strip()
    try:
        return float(value)
    except Exception:
        return 0.0


class V4LiveOddsCollector:
    def __init__(
        self,
        date_str: str,
        interval: int = 30,
        from_minute: int = 0,
        to_minute: int = 20,
        source: str = "api_football",
        raw_save: bool = True,
        normalize: bool = True,
        profile_name: str = "ultra",
        capture_tier: str = "A_candidate",
        task_file: Optional[str] = None,
        budget_aware: bool = False,
        hard_limit: int = 75000,
        soft_limit: int = 65000,
        rate_limit: int = 350,
        api_client: Optional[Callable[[str], Optional[dict]]] = None,
    ):
        self.date_key = _date_key(date_str)
        self.interval = max(5, int(interval))
        self.from_minute = max(0, int(from_minute))
        self.to_minute = max(self.from_minute, int(to_minute))
        self.source = source
        self.raw_save = raw_save
        self.normalize = normalize
        self.profile_name = profile_name
        self.capture_tier = capture_tier
        self.task_file = task_file
        self.budget_aware = budget_aware
        self.hard_limit = hard_limit
        self.soft_limit = soft_limit
        self.rate_limit = rate_limit
        self.api_get = api_client or net_utils.api_get

        self.profile = load_profile(self.profile_name)
        tconf = tier_conf(self.profile, self.capture_tier)
        self.odds_interval_sec = int(tconf.get("odds_interval_sec", self.interval))
        self.state_interval_sec = int(tconf.get("state_interval_sec", self.interval))
        self.events_interval_sec = int(tconf.get("events_interval_sec", self.interval))
        self.stats_interval_sec = int(tconf.get("stats_interval_sec", self.interval))
        self.slice_minutes = [int(x) for x in tconf.get("capture_minutes", [])]

        self.day_dir = SNAP_DIR / self.date_key
        self.raw_path = self.day_dir / "live_odds_raw.jsonl"
        self.norm_path = self.day_dir / "live_odds_normalized.jsonl"
        self.missing_path = self.day_dir / "live_market_missing.jsonl"
        self.exec_path = EXEC_DIR / f"live_execution_sim_{self.date_key}.jsonl"
        self.api_call_log_path = EXEC_DIR / f"api_call_log_{self.date_key}.jsonl"
        self.state_path = MONITOR_DIR / f"v4_capture_runtime_state_{self.date_key}.json"

    def load_watchlist(self) -> list[dict]:
        if self.task_file:
            data = _load_json(Path(self.task_file), {})
            rows = data.get("tasks", []) if isinstance(data, dict) else []
            return [x for x in rows if str(x.get("tier")) == self.capture_tier]
        path = REPORT_DIR / f"live_watchlist_{self.date_key}.json"
        rows = _load_json(path, [])
        if not isinstance(rows, list):
            return []

        filtered = []
        for row in rows:
            market_focus = row.get("market_focus")
            if market_focus != "HT_LIVE_OVER":
                continue
            coverage = (row.get("data_coverage") or {}).get("coverage_level", "")
            if str(coverage).upper() not in ("FULL", "GOOD"):
                continue
            filtered.append(row)
        return filtered

    def _load_runtime_state(self) -> dict:
        return _load_json(self.state_path, {"fixtures": {}, "degrade_events": []})

    def _save_runtime_state(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _log_api_call(self, endpoint: str, endpoint_type: str, ok: bool, http_status: Optional[int] = None) -> None:
        _append_jsonl(self.api_call_log_path, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "date": self.date_key,
            "capture_tier": self.capture_tier,
            "profile": self.profile_name,
            "endpoint": endpoint,
            "endpoint_type": endpoint_type,
            "ok": ok,
            "http_status": http_status,
        })

    def _api_call(self, endpoint: str, endpoint_type: str) -> Optional[dict]:
        resp = self.api_get(endpoint)
        ok = isinstance(resp, dict)
        self._log_api_call(endpoint, endpoint_type, ok=ok)
        return resp

    def fetch_fixture_state(self, fixture_id: int) -> dict:
        item = api_fetch_fixture_state(fixture_id, lambda ep: self._api_call(ep, "fixture_state"))
        data = [item] if item else []
        if not data:
            return {"fixture_id": fixture_id, "state": "API_EMPTY", "minute": None, "elapsed_seconds": None}
        item = data[0]
        fixture = item.get("fixture", {}) or {}
        status = fixture.get("status", {}) or {}
        goals = item.get("goals", {}) or {}
        elapsed = status.get("elapsed")
        minute = int(elapsed or 0) if elapsed is not None else None
        return {
            "fixture_id": fixture_id,
            "state": status.get("short"),
            "minute": minute,
            "elapsed_seconds": int(minute * 60) if minute is not None else None,
            "score_home": int(goals.get("home") or 0),
            "score_away": int(goals.get("away") or 0),
            "kickoff_utc": _to_utc_iso(fixture.get("date") or ""),
            "status_raw": status,
        }

    def fetch_events(self, fixture_id: int) -> dict:
        resp = api_fetch_fixture_events(fixture_id, lambda ep: self._api_call(ep, "events"))
        rows = _safe_rows(resp)
        red_h = 0
        red_a = 0
        event_tags = []
        for e in rows:
            typ = str(e.get("type") or "")
            detail = str(e.get("detail") or "")
            team = (e.get("team") or {}).get("name")
            elapsed = (e.get("time") or {}).get("elapsed")
            low = (typ + " " + detail).lower()
            if any(k in low for k in ("goal", "card", "var", "pen")):
                event_tags.append({"type": typ, "detail": detail, "team": team, "elapsed": elapsed})
            if "card" in typ.lower() and "red" in detail.lower():
                if (e.get("team") or {}).get("id") == (rows[0].get("teams", {}) if isinstance(rows[0], dict) else {}).get("home"):
                    red_h += 1
                # events API 默认不带 home/away mapping；先用名称匹配 fallback
                # 后续在 normalized 里会再从统计补充
        return {
            "event_count": len(rows),
            "event_tags": event_tags[:10],
            "red_cards_home": red_h,
            "red_cards_away": red_a,
            "raw": resp or {},
        }

    def fetch_statistics(self, fixture_id: int) -> dict:
        resp = api_fetch_fixture_statistics(fixture_id, lambda ep: self._api_call(ep, "statistics"))
        rows = _safe_rows(resp)
        out = {
            "shots_home": 0.0,
            "shots_away": 0.0,
            "shots_on_target_home": 0.0,
            "shots_on_target_away": 0.0,
            "corners_home": 0.0,
            "corners_away": 0.0,
            "dangerous_attacks_home": 0.0,
            "dangerous_attacks_away": 0.0,
            "red_cards_home": 0.0,
            "red_cards_away": 0.0,
            "raw": resp or {},
        }
        for idx, team_stats in enumerate(rows[:2]):
            side = "home" if idx == 0 else "away"
            for stat in team_stats.get("statistics", []) or []:
                name = str(stat.get("type") or "").lower()
                value = _num(stat.get("value"))
                if "shots on goal" in name or "shots on target" in name:
                    out[f"shots_on_target_{side}"] = value
                elif "total shots" in name:
                    out[f"shots_{side}"] = value
                elif "corner" in name:
                    out[f"corners_{side}"] = value
                elif "dangerous attacks" in name:
                    out[f"dangerous_attacks_{side}"] = value
                elif "red cards" in name:
                    out[f"red_cards_{side}"] = value
        return out

    def fetch_live_odds(self, fixture_id: int) -> dict:
        return fetch_live_odds_paged(fixture_id, lambda ep: self._api_call(ep, "odds_live"))

    def _budget_usage(self) -> int:
        if not self.api_call_log_path.exists():
            return 0
        n = 0
        with open(self.api_call_log_path, encoding="utf-8") as f:
            for _ in f:
                n += 1
        return n

    def _effective_tier(self) -> str:
        if not self.budget_aware:
            return self.capture_tier
        used = self._budget_usage()
        if used >= self.soft_limit and self.capture_tier == "C_slice":
            return "PAUSED"
        if used >= self.soft_limit and self.capture_tier == "B_shadow":
            return "B_shadow_degraded"
        return self.capture_tier

    def normalize_ht_ou_market(self, raw_odds: dict) -> tuple[list[dict], list[dict]]:
        normalized = []
        misses = []
        books = _walk_live_books(raw_odds)
        if not books:
            return [], [{"missing_reason": "NO_BOOKMAKER_DATA"}]

        for bm in books:
            bookmaker = bm.get("name", "LIVE")
            for bet in bm.get("bets", []) or []:
                market_name = str(bet.get("name") or bet.get("label") or bet.get("market") or "")
                if not is_ht_ou_market_name(market_name):
                    continue

                line_map: dict[float, dict] = {}
                values = bet.get("values", []) or bet.get("odds", []) or []
                for val in values:
                    label = str(val.get("value") or val.get("label") or val.get("name") or "")
                    odd = _as_float(val.get("odd") or val.get("odds") or val.get("price"))
                    if odd is None:
                        continue
                    line = extract_line(label) or extract_line(market_name)
                    if line is None:
                        continue
                    line = normalize_line(line)
                    if not is_allowed_line(line):
                        continue
                    row = line_map.setdefault(line, {"bookmaker": bookmaker, "market_raw_name": market_name, "line": line, "over_odds": None, "under_odds": None})
                    ll = label.lower()
                    if "over" in ll or "大" in label:
                        row["over_odds"] = odd
                    elif "under" in ll or "小" in label:
                        row["under_odds"] = odd

                for line, row in sorted(line_map.items(), key=lambda x: x[0]):
                    if row["over_odds"] is None or row["under_odds"] is None:
                        misses.append({
                            "bookmaker": bookmaker,
                            "market_raw_name": market_name,
                            "line": line,
                            "missing_reason": "ODDS_PAIR_INCOMPLETE",
                        })
                        continue
                    normalized.append(row)

        if not normalized and not misses:
            misses.append({"missing_reason": "NO_HT_OU_MARKET_MATCH"})
        return normalized, misses

    def _capture_status(self, state: dict) -> tuple[bool, str]:
        status = str(state.get("state") or "")
        minute = state.get("minute")
        if status in ("NS", "TBD"):
            return False, "NOT_STARTED"
        if status not in ("1H", "HT"):
            return False, f"STATUS_{status}"
        if minute is None:
            return False, "NO_MINUTE"
        if minute < self.from_minute:
            return False, f"BEFORE_WINDOW_{self.from_minute}"
        if minute > self.to_minute:
            return False, f"AFTER_WINDOW_{self.to_minute}"
        return True, "IN_WINDOW"

    def _base_row(self, fixture: dict, state: dict, stats: dict, now_utc: str) -> dict:
        factors = fixture.get("factors") or {}
        return {
            "schema_version": "v4_live_odds_v1",
            "model_version": "V4.3_live_capture_only",
            "provider": self.source,
            "fixture_id": fixture.get("fixture_id"),
            "league_id": fixture.get("league_id"),
            "league_name": fixture.get("league"),
            "home_team": fixture.get("home"),
            "away_team": fixture.get("away"),
            "kickoff_utc": state.get("kickoff_utc") or _to_utc_iso(fixture.get("kickoff") or ""),
            "snapshot_utc": now_utc,
            "match_minute": state.get("minute"),
            "elapsed_seconds": state.get("elapsed_seconds"),
            "score_home": state.get("score_home"),
            "score_away": state.get("score_away"),
            "shots_home": stats.get("shots_home"),
            "shots_away": stats.get("shots_away"),
            "shots_on_target_home": stats.get("shots_on_target_home"),
            "shots_on_target_away": stats.get("shots_on_target_away"),
            "corners_home": stats.get("corners_home"),
            "corners_away": stats.get("corners_away"),
            "dangerous_attacks_home": stats.get("dangerous_attacks_home"),
            "dangerous_attacks_away": stats.get("dangerous_attacks_away"),
            "red_cards_home": int(stats.get("red_cards_home") or 0),
            "red_cards_away": int(stats.get("red_cards_away") or 0),
            "candidate_reason": {
                "market_focus": fixture.get("market_focus"),
                "best_score": fixture.get("best_score"),
                "time_bin_hotspot": fixture.get("time_bin_hotspot"),
                "lineup_action": fixture.get("lineup_action"),
                "h2h_ht_goal_rate": factors.get("h2h_ht_goal_rate"),
                "coverage_level": (fixture.get("data_coverage") or {}).get("coverage_level"),
            },
            "capture_tier": self.capture_tier,
            "capture_interval_sec": self.interval,
            "api_budget_profile": f"{self.profile_name}_{self.hard_limit}",
            "request_cost_estimate": 1,
            "rate_limit_bucket": "live_odds_high_priority" if self.capture_tier == "A_candidate" else "live_odds_standard",
        }

    def write_raw_snapshot(self, row: dict) -> None:
        _append_jsonl(self.raw_path, row)

    def write_normalized_snapshot(self, row: dict) -> None:
        _append_jsonl(self.norm_path, row)

    def write_missing_market(self, row: dict) -> None:
        _append_jsonl(self.missing_path, row)

    def write_execution_sim(self, row: dict) -> None:
        _append_jsonl(self.exec_path, row)

    def run_once(self) -> dict:
        fixtures = self.load_watchlist()
        runtime = self._load_runtime_state()
        effective_tier = self._effective_tier()
        if effective_tier == "PAUSED":
            return {
                "date": self.date_key,
                "capture_tier": self.capture_tier,
                "status": "PAUSED_BY_BUDGET",
                "budget_used": self._budget_usage(),
                "soft_limit": self.soft_limit,
            }
        captured = 0
        missing = 0
        skipped = 0
        now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        for fx in fixtures:
            fixture_id = int(fx.get("fixture_id"))
            fstate = runtime["fixtures"].setdefault(str(fixture_id), {})
            now_ts = int(time.time())

            need_state = now_ts - int(fstate.get("state_ts", 0)) >= (60 if effective_tier == "B_shadow_degraded" else self.state_interval_sec)
            need_events = now_ts - int(fstate.get("events_ts", 0)) >= (60 if effective_tier == "B_shadow_degraded" else self.events_interval_sec)
            need_stats = now_ts - int(fstate.get("stats_ts", 0)) >= (60 if effective_tier == "B_shadow_degraded" else self.stats_interval_sec)
            need_odds = now_ts - int(fstate.get("odds_ts", 0)) >= (60 if effective_tier == "B_shadow_degraded" else self.odds_interval_sec)

            state = self.fetch_fixture_state(fixture_id) if need_state else (fstate.get("last_state") or {"fixture_id": fixture_id, "state": "CACHE_EMPTY", "minute": None})
            allow, reason = self._capture_status(state)
            stats = self.fetch_statistics(fixture_id) if need_stats else (fstate.get("last_stats") or {})
            events = self.fetch_events(fixture_id) if need_events else (fstate.get("last_events") or {})

            if self.capture_tier == "C_slice" and self.slice_minutes and state.get("minute") is not None:
                m = int(state.get("minute") or 0)
                if m not in self.slice_minutes:
                    allow = False
                    reason = "NOT_SLICE_MINUTE"
            raw_odds = self.fetch_live_odds(fixture_id) if (allow and need_odds) else {}
            raw_row = {
                "snapshot_utc": now_utc,
                "fixture_id": fixture_id,
                "capture_status": "OK" if allow else "SKIP",
                "skip_reason": None if allow else reason,
                "state": state,
                "statistics": stats,
                "events": events,
                "raw_odds": raw_odds,
            }
            if self.raw_save:
                self.write_raw_snapshot(raw_row)

            if not allow:
                skipped += 1
                continue

            normalized_rows, misses = self.normalize_ht_ou_market(raw_odds)
            base = self._base_row(fx, state, stats, now_utc)

            if normalized_rows:
                for m in normalized_rows:
                    row = {
                        **base,
                        "market_source": "api_football_odds_live",
                        "bookmaker": m.get("bookmaker"),
                        "market_raw_name": m.get("market_raw_name"),
                        "market_type": "HT_ASIAN_TOTAL",
                        "line": m.get("line"),
                        "side": "OVER",
                        "over_odds": m.get("over_odds"),
                        "under_odds": m.get("under_odds"),
                        "is_suspended": False,
                        "market_status": "OPEN",
                        "odds_age_seconds": None,
                        "capture_status": "OK",
                        "missing_reason": None,
                    }
                    self.write_normalized_snapshot(row)
                    ev_proxy = 0.01
                    ex = estimate_execution_cost(
                        displayed_odds=float(m.get("over_odds")),
                        ev_gross=ev_proxy,
                        odds_alive_seconds=3.0,
                        latency_seconds=1.5,
                        market_freeze=False,
                    )
                    self.write_execution_sim({
                        "fixture_id": fixture_id,
                        "snapshot_utc": now_utc,
                        "minute": state.get("minute"),
                        "line": m.get("line"),
                        "displayed_odds": m.get("over_odds"),
                        "simulated_fill_odds": ex.simulated_fill_odds,
                        "slippage": ex.slippage,
                        "latency_seconds": ex.latency_seconds,
                        "ev_gross": ev_proxy,
                        "ev_net": ex.ev_net,
                        "conservative_ev": ex.conservative_ev,
                        "fill_probability": ex.fill_probability,
                        "source": "v4_live_odds_collector",
                    })
                    captured += 1
            else:
                missing += 1

            for ms in misses:
                miss_row = {
                    **base,
                    "market_source": "api_football_odds_live",
                    "bookmaker": ms.get("bookmaker"),
                    "market_raw_name": ms.get("market_raw_name"),
                    "market_type": "HT_ASIAN_TOTAL",
                    "line": ms.get("line"),
                    "side": "OVER",
                    "over_odds": None,
                    "under_odds": None,
                    "is_suspended": None,
                    "market_status": "UNKNOWN",
                    "odds_age_seconds": None,
                    "capture_status": "MISSING",
                    "missing_reason": ms.get("missing_reason", "UNKNOWN"),
                }
                self.write_missing_market(miss_row)

            time.sleep(0.05)
            if need_state:
                fstate["state_ts"] = now_ts
                fstate["last_state"] = state
            if need_events:
                fstate["events_ts"] = now_ts
                fstate["last_events"] = events
            if need_stats:
                fstate["stats_ts"] = now_ts
                fstate["last_stats"] = stats
            if need_odds:
                fstate["odds_ts"] = now_ts

        self._save_runtime_state(runtime)
        return {
            "date": self.date_key,
            "capture_tier": self.capture_tier,
            "snapshot_utc": now_utc,
            "watchlist_count": len(fixtures),
            "captured_rows": captured,
            "missing_rows": missing,
            "skipped_fixtures": skipped,
            "raw_path": str(self.raw_path),
            "normalized_path": str(self.norm_path),
            "missing_path": str(self.missing_path),
            "execution_path": str(self.exec_path),
            "api_call_log_path": str(self.api_call_log_path),
            "budget_used": self._budget_usage(),
        }

    def watch_loop(self, max_runs: int = 0):
        runs = 0
        while True:
            result = self.run_once()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            runs += 1
            if max_runs and runs >= max_runs:
                break
            time.sleep(self.interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--watch", action="store_true", help="循环采集")
    parser.add_argument("--once", action="store_true", help="只采集一轮")
    parser.add_argument("--interval", type=int, default=30, help="轮询间隔秒")
    parser.add_argument("--from-minute", type=int, default=0)
    parser.add_argument("--to-minute", type=int, default=20)
    parser.add_argument("--source", default="api_football")
    parser.add_argument("--profile", default="ultra")
    parser.add_argument("--tier", default="A_candidate", choices=["A_candidate", "B_shadow", "C_slice"])
    parser.add_argument("--task-file", default=None)
    parser.add_argument("--budget-aware", action="store_true")
    parser.add_argument("--hard-limit", type=int, default=75000)
    parser.add_argument("--soft-limit", type=int, default=65000)
    parser.add_argument("--rate-limit", type=int, default=350)
    parser.add_argument("--raw-save", choices=["on", "off"], default="on")
    parser.add_argument("--normalize", choices=["on", "off"], default="on")
    parser.add_argument("--max-runs", type=int, default=0)
    args = parser.parse_args()

    collector = V4LiveOddsCollector(
        date_str=args.date,
        interval=args.interval,
        from_minute=args.from_minute,
        to_minute=args.to_minute,
        source=args.source,
        profile_name=args.profile,
        capture_tier=args.tier,
        task_file=args.task_file,
        budget_aware=args.budget_aware,
        hard_limit=args.hard_limit,
        soft_limit=args.soft_limit,
        rate_limit=args.rate_limit,
        raw_save=args.raw_save == "on",
        normalize=args.normalize == "on",
    )

    if args.watch:
        collector.watch_loop(max_runs=args.max_runs)
    else:
        result = collector.run_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
