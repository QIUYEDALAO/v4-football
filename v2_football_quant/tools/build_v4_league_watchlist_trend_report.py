#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "data/runtime/validation"
WEEKLY = ROOT / "data/weekly_reports"
MONTHLY = ROOT / "data/monthly_reports"
RUNTIME_SNAP = Path(os.environ.get("V4_LEAGUE_WATCHLIST_SNAPSHOT_DIR") or (ROOT / "data/runtime/league_watchlist_snapshots"))
RUNTIME_TREND = Path(os.environ.get("V4_LEAGUE_WATCHLIST_TREND_DIR") or (ROOT / "data/runtime/league_watchlist_trends"))
WATCHLIST_BUILDER = ROOT / "tools/build_v4_league_watchlist_report.py"

SNAPSHOT_PREFIX = "v4_league_watchlist_snapshot_"
TREND_JSON = RUNTIME_TREND / "v4_league_watchlist_trend_latest.json"
TREND_TXT = RUNTIME_TREND / "v4_league_watchlist_trend_latest.txt"

CHANGE_TYPES = {
    "BASELINE_ONLY",
    "TAG_IMPROVED",
    "TAG_WORSENED",
    "SAMPLE_INCREASED",
    "HIT_RATE_UP",
    "HIT_RATE_DOWN",
    "PENDING_TO_VALIDATED",
    "NEW_PENDING_ONLY",
    "NO_MATERIAL_CHANGE",
    "DATA_GAP",
}
ALLOWED_HINTS = {
    "OBSERVE_ONLY",
    "CONTINUE_MONITORING",
    "LOW_TRUST_OBSERVE_ONLY",
    "LOW_SAMPLE_DO_NOT_CONCLUDE",
    "PENDING_ONLY_NO_DENOMINATOR",
    "DATA_GAP_REVIEW",
    "BASELINE_ONLY_WAIT_NEXT_SNAPSHOT",
}
TAG_ORDER = {
    "KEEP": 0,
    "WATCH": 1,
    "OBSERVE": 2,
    "LOW_SAMPLE_ONLY": 3,
    "DO_NOT_CONCLUDE": 4,
    "PENDING_ONLY": 5,
    "LOW_TRUST_ALERT": 6,
    "DATA_GAP": 7,
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def ensure_current_watchlist() -> dict[str, Any]:
    latest = sorted(WEEKLY.glob("v4_league_watchlist_report_*.json"))
    if latest:
        current = load_json(latest[-1])
        if current:
            return current
    run = subprocess.run(
        ["python3", str(WATCHLIST_BUILDER), "--report-type", "dryrun", "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        return {}
    return load_json(WEEKLY / "v4_league_watchlist_report_dryrun.json")


def flatten_watchlist(watchlist: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = (
        "keep_leagues",
        "watch_leagues",
        "low_trust_alert_leagues",
        "low_sample_leagues",
        "do_not_conclude_leagues",
        "pending_only_leagues",
        "data_gap_leagues",
    )
    out: dict[str, dict[str, Any]] = {}
    for key in keys:
        for row in watchlist.get(key) or []:
            if not isinstance(row, dict):
                continue
            league = str(row.get("league") or "").strip()
            if not league:
                continue
            out[league] = dict(row)
    return out


def current_snapshot_from_watchlist(watchlist: dict[str, Any]) -> dict[str, Any]:
    rows = flatten_watchlist(watchlist)
    now = datetime.now()
    snapshot_date = now.strftime("%Y%m%d")
    snapshot_id = now.strftime("%Y%m%dT%H%M%S%f")
    dist = {}
    for row in rows.values():
        tag = str(row.get("trust_tag") or "DATA_GAP")
        dist[tag] = dist.get(tag, 0) + 1
    return {
        "snapshot_date": snapshot_date,
        "snapshot_id": snapshot_id,
        "generated_at": now.isoformat(),
        "trend_anchor_date": watchlist.get("trend_anchor_date") or "DATA_MISSING",
        "source_ledger_resolved": watchlist.get("source_ledger_resolved") or "NOT_FOUND",
        "total_leagues": int(watchlist.get("total_leagues") or len(rows)),
        "total_validated": int(watchlist.get("total_validated") or 0),
        "total_pending": int(watchlist.get("total_pending") or 0),
        "tag_distribution": dist,
        "leagues": rows,
        "policy_note": "Trend is observation-only and never auto-changes official grade/rules.",
        "safety_guard": {
            "no_official_grade_change": True,
            "no_auto_exclude": True,
            "pending_only_excluded_from_denominator": True,
        },
    }


def _safe_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def find_previous_snapshot(current: dict[str, Any], current_snapshot_path: Path) -> tuple[dict[str, Any], str]:
    current_id = str(current.get("snapshot_id") or "")
    current_gen = _safe_dt(str(current.get("generated_at") or ""))
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for path in sorted(RUNTIME_SNAP.glob(f"{SNAPSHOT_PREFIX}*.json")):
        if path.resolve() == current_snapshot_path.resolve():
            continue
        snap = load_json(path)
        if not snap:
            continue
        prev_id = str(snap.get("snapshot_id") or "")
        prev_gen = _safe_dt(str(snap.get("generated_at") or ""))
        if not prev_id or prev_id == current_id or not prev_gen:
            continue
        if current_gen and prev_gen >= current_gen:
            continue
        snap["snapshot_path"] = str(path)
        candidates.append((prev_gen, snap))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[-1][1], "PASS"

    # fallback from weekly/monthly watchlist reports
    fallback_paths = sorted(WEEKLY.glob("v4_league_watchlist_report_*.json")) + sorted(MONTHLY.glob("v4_league_watchlist_report_*.json"))
    if not fallback_paths:
        return {}, "PASS"
    snap = current_snapshot_from_watchlist(load_json(fallback_paths[-1]))
    if str(snap.get("snapshot_id") or "") == current_id and len(fallback_paths) > 1:
        snap = current_snapshot_from_watchlist(load_json(fallback_paths[-2]))
    prev_id = str(snap.get("snapshot_id") or "")
    prev_gen = _safe_dt(str(snap.get("generated_at") or ""))
    if not prev_id or prev_id == current_id or (current_gen and prev_gen and prev_gen >= current_gen):
        return {}, "PASS"
    snap["snapshot_path"] = "FALLBACK_WATCHLIST_REPORT"
    return snap, "PASS"


def tag_delta(curr: dict[str, int], prev: dict[str, int]) -> dict[str, int]:
    keys = sorted(set(curr) | set(prev))
    return {k: int(curr.get(k, 0)) - int(prev.get(k, 0)) for k in keys}


def choose_change_type(prev: dict[str, Any], curr: dict[str, Any]) -> str:
    pt = str(prev.get("trust_tag") or "DATA_GAP")
    ct = str(curr.get("trust_tag") or "DATA_GAP")
    pv = int(prev.get("validated_count") or 0)
    cv = int(curr.get("validated_count") or 0)
    pp = int(prev.get("pending_count") or 0)
    cp = int(curr.get("pending_count") or 0)
    phr = float(prev.get("hit_rate") or 0.0)
    chr_ = float(curr.get("hit_rate") or 0.0)

    if pt == "PENDING_ONLY" and cv > 0:
        return "PENDING_TO_VALIDATED"
    if ct == "PENDING_ONLY" and pt != "PENDING_ONLY":
        return "NEW_PENDING_ONLY"
    if TAG_ORDER.get(ct, 99) < TAG_ORDER.get(pt, 99):
        return "TAG_IMPROVED"
    if TAG_ORDER.get(ct, 99) > TAG_ORDER.get(pt, 99):
        return "TAG_WORSENED"
    if cv > pv:
        return "SAMPLE_INCREASED"
    if chr_ > phr:
        return "HIT_RATE_UP"
    if chr_ < phr:
        return "HIT_RATE_DOWN"
    if pt == "DATA_GAP" or ct == "DATA_GAP":
        return "DATA_GAP"
    if cp != pp:
        return "SAMPLE_INCREASED"
    return "NO_MATERIAL_CHANGE"


def action_hint_for(change_type: str, current: dict[str, Any]) -> str:
    tag = str(current.get("trust_tag") or "DATA_GAP")
    if change_type == "BASELINE_ONLY":
        return "BASELINE_ONLY_WAIT_NEXT_SNAPSHOT"
    if tag == "LOW_TRUST_ALERT":
        return "LOW_TRUST_OBSERVE_ONLY"
    if tag in {"LOW_SAMPLE_ONLY", "DO_NOT_CONCLUDE"}:
        return "LOW_SAMPLE_DO_NOT_CONCLUDE"
    if tag == "PENDING_ONLY":
        return "PENDING_ONLY_NO_DENOMINATOR"
    if tag == "DATA_GAP":
        return "DATA_GAP_REVIEW"
    if change_type in {"TAG_WORSENED", "HIT_RATE_DOWN"}:
        return "CONTINUE_MONITORING"
    return "OBSERVE_ONLY"


def changed_item(league: str, prev: dict[str, Any], curr: dict[str, Any], baseline_only: bool) -> dict[str, Any]:
    change_type = "BASELINE_ONLY" if baseline_only else choose_change_type(prev, curr)
    item = {
        "league": league,
        "previous_trust_tag": prev.get("trust_tag", "DATA_MISSING"),
        "current_trust_tag": curr.get("trust_tag", "DATA_MISSING"),
        "previous_sample_tag": prev.get("sample_tag", "DATA_MISSING"),
        "current_sample_tag": curr.get("sample_tag", "DATA_MISSING"),
        "previous_validated_count": int(prev.get("validated_count") or 0),
        "current_validated_count": int(curr.get("validated_count") or 0),
        "previous_pending_count": int(prev.get("pending_count") or 0),
        "current_pending_count": int(curr.get("pending_count") or 0),
        "previous_hit_rate": float(prev.get("hit_rate") or 0.0),
        "current_hit_rate": float(curr.get("hit_rate") or 0.0),
        "delta_validated_count": int(curr.get("validated_count") or 0) - int(prev.get("validated_count") or 0),
        "delta_hit_rate": round(float(curr.get("hit_rate") or 0.0) - float(prev.get("hit_rate") or 0.0), 6),
        "change_type": change_type if change_type in CHANGE_TYPES else "NO_MATERIAL_CHANGE",
        "action_hint": action_hint_for(change_type, curr),
    }
    if item["action_hint"] not in ALLOWED_HINTS:
        item["action_hint"] = "OBSERVE_ONLY"
    return item


def build_trend(current: dict[str, Any], previous: dict[str, Any], current_snapshot_path: Path, guard_status: str) -> dict[str, Any]:
    curr_rows = current.get("leagues") or {}
    prev_rows = previous.get("leagues") or {}
    baseline_only = not bool(previous)
    leagues = sorted(set(curr_rows) | set(prev_rows))
    changes = [changed_item(lg, prev_rows.get(lg, {}), curr_rows.get(lg, {}), baseline_only) for lg in leagues]

    if baseline_only:
        changes = []

    trust_changed = [x for x in changes if x["previous_trust_tag"] != x["current_trust_tag"]]
    improved = [x for x in changes if x["change_type"] == "TAG_IMPROVED"]
    worsened = [x for x in changes if x["change_type"] == "TAG_WORSENED"]
    new_low_trust = [x for x in changes if x["previous_trust_tag"] != "LOW_TRUST_ALERT" and x["current_trust_tag"] == "LOW_TRUST_ALERT"]
    resolved_low_trust = [x for x in changes if x["previous_trust_tag"] == "LOW_TRUST_ALERT" and x["current_trust_tag"] != "LOW_TRUST_ALERT"]
    new_low_sample = [x for x in changes if x["current_trust_tag"] in {"LOW_SAMPLE_ONLY", "DO_NOT_CONCLUDE"} and x["previous_trust_tag"] not in {"LOW_SAMPLE_ONLY", "DO_NOT_CONCLUDE"}]
    pending_to_validated = [x for x in changes if x["change_type"] == "PENDING_TO_VALIDATED"]
    new_pending_only = [x for x in changes if x["change_type"] == "NEW_PENDING_ONLY"]
    sample_delta_top = sorted(changes, key=lambda x: x["delta_validated_count"], reverse=True)[:8]
    hit_rate_delta_top = sorted(changes, key=lambda x: abs(x["delta_hit_rate"]), reverse=True)[:8]

    trend = {
        "generated_at": datetime.now().isoformat(),
        "trend_anchor_date": current.get("trend_anchor_date") or "DATA_MISSING",
        "current_snapshot_date": current.get("snapshot_date") or "DATA_MISSING",
        "current_snapshot_id": current.get("snapshot_id") or "DATA_MISSING",
        "current_snapshot_path": str(current_snapshot_path),
        "previous_snapshot_id": previous.get("snapshot_id") if previous else "",
        "previous_snapshot_path": previous.get("snapshot_path") if previous else "",
        "self_reference_guard_status": guard_status,
        "baseline_only": baseline_only,
        "baseline_only_reason": "NO_PREVIOUS_DISTINCT_SNAPSHOT" if baseline_only else "",
        "total_leagues_current": int(current.get("total_leagues") or len(curr_rows)),
        "total_leagues_previous": int(previous.get("total_leagues") or len(prev_rows)) if previous else 0,
        "tag_distribution_current": current.get("tag_distribution") or {},
        "tag_distribution_previous": previous.get("tag_distribution") or {},
        "tag_distribution_delta": tag_delta(current.get("tag_distribution") or {}, previous.get("tag_distribution") or {}) if not baseline_only else {},
        "trust_tag_changed_leagues": trust_changed,
        "improved_leagues": improved,
        "worsened_leagues": worsened,
        "new_low_trust_alert_leagues": new_low_trust,
        "resolved_low_trust_alert_leagues": resolved_low_trust,
        "new_low_sample_leagues": new_low_sample,
        "pending_to_validated_leagues": pending_to_validated,
        "new_pending_only_leagues": new_pending_only,
        "sample_count_delta_top": sample_delta_top,
        "hit_rate_delta_top": hit_rate_delta_top,
        "risk_summary": {
            "tag_worsened_count": len(worsened),
            "tag_improved_count": len(improved),
            "new_low_trust_alert_count": len(new_low_trust),
            "pending_to_validated_count": len(pending_to_validated),
        },
        "policy_note": "趋势仅供观察，不自动修改 official grade。",
        "safety_guard": {
            "no_official_grade_change": True,
            "no_auto_exclude": True,
            "pending_only_excluded_from_denominator": True,
        },
    }
    return trend


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "V4 联赛 Watchlist 滚动趋势监控",
        f"生成时间：{report.get('generated_at')}",
        f"trend_anchor_date：{report.get('trend_anchor_date')}",
        "",
    ]
    if report.get("baseline_only"):
        lines += [
            "当前仅有 baseline 快照，不能判断趋势。",
            f"baseline_only_reason：{report.get('baseline_only_reason') or 'NO_PREVIOUS_DISTINCT_SNAPSHOT'}",
            "",
            "趋势仅供观察，不自动修改 official grade。",
        ]
        return "\n".join(lines)

    risk = report.get("risk_summary") or {}
    lines += [
        "本期变化摘要",
        f"- 标签恶化：{risk.get('tag_worsened_count', 0)}",
        f"- 标签改善：{risk.get('tag_improved_count', 0)}",
        f"- 新增 LOW_TRUST_ALERT：{risk.get('new_low_trust_alert_count', 0)}",
        f"- pending 转 validated：{risk.get('pending_to_validated_count', 0)}",
    ]
    top_sample = report.get("sample_count_delta_top") or []
    if top_sample:
        lines.append(f"- 样本增长最多：{top_sample[0].get('league')} (Δvalidated={top_sample[0].get('delta_validated_count')})")
    top_rate = report.get("hit_rate_delta_top") or []
    if top_rate:
        lines.append(f"- 命中率变化最大：{top_rate[0].get('league')} (Δhit_rate={top_rate[0].get('delta_hit_rate')})")
    lines += [
        "",
        "趋势仅供观察，不自动修改 official grade。",
    ]
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    current_watchlist = ensure_current_watchlist()
    if not current_watchlist:
        print(json.dumps({"status": "BLOCKER", "reason": "CURRENT_WATCHLIST_MISSING"}, ensure_ascii=False, indent=2))
        return 2

    current_snapshot = current_snapshot_from_watchlist(current_watchlist)
    snapshot_path = RUNTIME_SNAP / f"{SNAPSHOT_PREFIX}{current_snapshot['snapshot_id']}.json"
    previous_snapshot, guard_status = find_previous_snapshot(current_snapshot, snapshot_path)
    trend = build_trend(current_snapshot, previous_snapshot, snapshot_path, guard_status)
    write_json(snapshot_path, current_snapshot)
    write_json(TREND_JSON, trend)
    TREND_TXT.parent.mkdir(parents=True, exist_ok=True)
    TREND_TXT.write_text(render_text(trend), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "snapshot_path": str(snapshot_path),
                "trend_json": str(TREND_JSON),
                "trend_txt": str(TREND_TXT),
                "baseline_only": trend.get("baseline_only"),
                "dry_run": bool(args.dry_run),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
