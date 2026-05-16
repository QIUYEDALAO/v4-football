"""
V4 赛中统计快照采集 (v2 — 稳定性增强版)
=========================================
仅用于赛后归因增强，不参与实时评分。

v2 变更 (2026-05-17):
  - max-fixtures-per-run: 默认每轮最多处理25个fixture
  - per-fixture时间预算: 单个fixture最多10秒,超时跳过
  - soft deadline: 240秒软退出,不等cron 300s强杀
  - fixture优先级: A>B>C>SKIP>其他, 无分级时按league优先级
  - dangerous_attacks标记为UNSUPPORTED_BY_API
  - 写入status JSON到 data/runtime/status/

用法:
  python3 engine/v4_live_stats_snapshot.py --date 20260514
  python3 engine/v4_live_stats_snapshot.py --date 20260514 --minutes 15,30,45
  python3 engine/v4_live_stats_snapshot.py --date 20260514 --fixture 123456
  python3 engine/v4_live_stats_snapshot.py --date 20260517 --max-fixtures 30
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine import net_utils

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
SNAPSHOT_TOLERANCE_MIN = 3

# ── 稳定性参数 ──
DEFAULT_MAX_FIXTURES = 25          # 每轮最多处理的fixture数
FIXTURE_TIME_BUDGET_SEC = 10.0     # 单个fixture最大耗时(秒)，超时跳过
SOFT_DEADLINE_SEC = 240.0          # 脚本总运行时间软退出点(秒)，不等cron强杀

# ── league优先级(无ht_recommendation时使用) ──
_MAJOR_LEAGUES = frozenset({
    # 五大联赛
    '英超', '西甲', '意甲', '德甲', '法甲',
    # 主流一级
    '英冠', '英甲', '德乙', '西乙', '意乙', '法乙',
    '荷甲', '葡超', '比甲', '俄超', '土超', '瑞士超',
    '日职联', '韩K联', '澳超', '美职业', '墨西联', '巴西甲', '阿甲',
    '挪超', '丹超', '捷克甲', '奥甲',
})

_LOW_PRIORITY_LEAGUES = frozenset({
    'U19', 'U17', 'U21', 'U20', 'U23',
    'U19 Bundesliga', 'AFC U17 Asian Cup',
    'Cup',
    'Liga III', 'II Liga', 'III Liga',
    'Second League', 'Second NL', 'First NL',
    '1. Division',
    'Toppserien',
})


# ── 辅助函数 ──

def _date_key(v: str) -> str:
    return str(v).replace("-", "")


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    if isinstance(v, str):
        v = v.replace("%", "").strip()
    try:
        return float(v)
    except Exception:
        return default


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
    return out


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _api_get(endpoint: str) -> dict[str, Any]:
    return net_utils.api_get(endpoint) or {}


def _safe_rows(resp: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (resp or {}).get("response")
    return rows if isinstance(rows, list) else []


def _fixture_state(fixture_id: int) -> dict[str, Any]:
    rows = _safe_rows(_api_get(f"fixtures?id={fixture_id}"))
    if not rows:
        return {"ok": False, "minute": None, "status": "API_EMPTY"}
    item = rows[0]
    status = (item.get("fixture") or {}).get("status") or {}
    minute = status.get("elapsed")
    return {
        "ok": True,
        "minute": _safe_int(minute, -1) if minute is not None else None,
        "status": str(status.get("short") or ""),
    }


def _stats_snapshot(fixture_id: int) -> dict[str, Any]:
    """
    采集比赛统计快照。
    dangerous_attacks 标记为 UNSUPPORTED_BY_API (API-Football不返回此字段)。
    """
    rows = _safe_rows(_api_get(f"fixtures/statistics?fixture={fixture_id}"))
    if not rows:
        return {
            "stats_available": False,
            "shots_home": 0.0,
            "shots_away": 0.0,
            "shots_on_target_home": 0.0,
            "shots_on_target_away": 0.0,
            "corners_home": 0.0,
            "corners_away": 0.0,
            "dangerous_attacks_home": None,
            "dangerous_attacks_away": None,
            "dangerous_attacks_supported": False,
            "possession_home": 0.0,
            "possession_away": 0.0,
        }

    out = {
        "stats_available": True,
        "shots_home": 0.0,
        "shots_away": 0.0,
        "shots_on_target_home": 0.0,
        "shots_on_target_away": 0.0,
        "corners_home": 0.0,
        "corners_away": 0.0,
        "dangerous_attacks_home": None,
        "dangerous_attacks_away": None,
        "dangerous_attacks_supported": False,
        "possession_home": 0.0,
        "possession_away": 0.0,
    }
    for idx, team_stats in enumerate(rows[:2]):
        side = "home" if idx == 0 else "away"
        for s in team_stats.get("statistics", []) or []:
            name = str(s.get("type") or "").lower()
            val = _safe_float(s.get("value"), 0.0)
            if "total shots" in name:
                out[f"shots_{side}"] = val
            elif "shots on goal" in name or "shots on target" in name:
                out[f"shots_on_target_{side}"] = val
            elif "corner" in name:
                out[f"corners_{side}"] = val
            elif "dangerous attacks" in name:
                # API-Football 当前未返回此字段，保留解析逻辑以备未来兼容
                out[f"dangerous_attacks_{side}"] = val
                out["dangerous_attacks_supported"] = True
            elif "ball possession" in name or "possession" in name:
                out[f"possession_{side}"] = val
    return out


def _fixture_priority(rec: dict[str, Any]) -> int:
    """
    确定fixture处理优先级(数值越大优先级越高)。

    规则:
      5 = A
      4 = B
      3 = C
      2 = SKIP / HT_SKIP
      1 = 主流联赛
      0 = 其他
     -1 = 已知低优先级联赛
    """
    rec_rec = rec.get("ht_recommendation") or ""
    if rec_rec == "A":
        return 5
    if rec_rec == "B":
        return 4
    if rec_rec == "C":
        return 3
    if rec_rec in ("SKIP", "HT_SKIP"):
        return 2

    league = str(rec.get("league") or "")
    if league in _MAJOR_LEAGUES:
        return 1
    if league in _LOW_PRIORITY_LEAGUES:
        return -1
    return 0


def _write_status(status_path: Path, status: dict[str, Any]) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


# ── 主采集逻辑 ──

def run(
    date_str: str,
    minutes: list[int],
    fixture_id: int | None = None,
    sleep_ms: int = 120,
    max_fixtures: int = DEFAULT_MAX_FIXTURES,
    soft_deadline_sec: float = SOFT_DEADLINE_SEC,
) -> dict[str, Any]:
    key = _date_key(date_str)
    start_time = time.time()

    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if isinstance(scout, dict):
        scout = scout.get("results") or []
    if not isinstance(scout, list) or not scout:
        return {"error": f"scout文件不存在或为空: {scout_path}"}

    out_path = ARCHIVE_DIR / f"live_stats_snapshot_{key}.jsonl"
    existing = _load_jsonl(out_path)
    existing_keys = {
        (int(r.get("fixture_id") or 0), int(r.get("minute") or 0))
        for r in existing
        if r.get("fixture_id") is not None and r.get("minute") is not None
    }

    # ── 筛选目标fixture并排序 ──
    selected = [r for r in scout if (fixture_id is None or int(r.get("fixture_id") or 0) == int(fixture_id))]
    selected.sort(key=_fixture_priority, reverse=True)  # 优先级高的先处理

    # ── max-fixtures-per-run 截断 ──
    processed_fixtures = 0
    skipped_due_to_limit = 0
    if fixture_id is None and len(selected) > max_fixtures:
        skipped_due_to_limit = len(selected) - max_fixtures
        selected = selected[:max_fixtures]

    written = 0
    skipped_existing = 0
    skipped_not_reached = 0
    skipped_late = 0
    skipped_state = 0
    skipped_slow_fixture = 0
    skipped_no_stats = 0
    rows_no_stats = 0
    soft_deadline_reached = False
    last_fixture_id = None
    quality_counts = {"ON_TIME": 0, "LATE_ALLOWED": 0, "NO_STATS": 0, "STALE_SKIPPED": 0}

    for rec in selected:
        # ── soft deadline 检查 ──
        elapsed_wall = time.time() - start_time
        if elapsed_wall >= soft_deadline_sec:
            soft_deadline_reached = True
            break

        fid = int(rec.get("fixture_id") or 0)
        if not fid:
            continue

        fixture_start = time.time()
        last_fixture_id = fid

        try:
            st = _fixture_state(fid)
        except Exception:
            skipped_slow_fixture += 1
            continue

        # ── per-fixture 时间预算检查 ──
        if time.time() - fixture_start >= FIXTURE_TIME_BUDGET_SEC:
            skipped_slow_fixture += 1
            continue

        if not st.get("ok"):
            skipped_state += 1
            continue
        status = str(st.get("status") or "")
        elapsed = st.get("minute")
        if elapsed is None or elapsed < 0:
            skipped_state += 1
            continue

        try:
            snapshot = _stats_snapshot(fid)
        except Exception:
            skipped_slow_fixture += 1
            continue

        # ── per-fixture 时间预算检查(第二次API调用后) ──
        if time.time() - fixture_start >= FIXTURE_TIME_BUDGET_SEC:
            skipped_slow_fixture += 1
            continue

        scan_time = datetime.now(timezone.utc).isoformat()
        has_no_stats = not bool(snapshot.get("stats_available"))

        for minute in minutes:
            k = (fid, minute)
            if k in existing_keys:
                skipped_existing += 1
                continue
            if elapsed < minute:
                skipped_not_reached += 1
                continue
            if minute != 45 and elapsed > minute + SNAPSHOT_TOLERANCE_MIN:
                # 禁止用45'累计数据回填15'/30'快照，避免赛后污染
                skipped_late += 1
                quality_counts["STALE_SKIPPED"] += 1
                continue

            if minute == 45 and elapsed > minute + SNAPSHOT_TOLERANCE_MIN:
                snapshot_quality = "LATE_ALLOWED"
            else:
                snapshot_quality = "ON_TIME"

            if has_no_stats:
                snapshot_quality = "NO_STATS"
                rows_no_stats += 1
                skipped_no_stats += 1 if minute == minutes[0] else 0  # 只计一次

            quality_counts[snapshot_quality] += 1

            # ── dangerous_attacks 处理 ──
            da_home = snapshot.get("dangerous_attacks_home")
            da_away = snapshot.get("dangerous_attacks_away")
            da_supported = snapshot.get("dangerous_attacks_supported", False)

            row = {
                "fixture_id": fid,
                "date": key,
                "league": rec.get("league"),
                "home": rec.get("home"),
                "away": rec.get("away"),
                "minute": minute,
                "observed_elapsed_minute": elapsed,
                "snapshot_tolerance_min": SNAPSHOT_TOLERANCE_MIN,
                "snapshot_quality": snapshot_quality,
                "status_short": status,
                "scan_time": scan_time,
                "shots_home": snapshot.get("shots_home", 0.0),
                "shots_away": snapshot.get("shots_away", 0.0),
                "shots_on_target_home": snapshot.get("shots_on_target_home", 0.0),
                "shots_on_target_away": snapshot.get("shots_on_target_away", 0.0),
                "corners_home": snapshot.get("corners_home", 0.0),
                "corners_away": snapshot.get("corners_away", 0.0),
                "dangerous_attacks_home": da_home,
                "dangerous_attacks_away": da_away,
                "dangerous_attacks_supported": da_supported,
                "dangerous_attacks_note": None if da_supported else "UNSUPPORTED_BY_API",
                "possession_home": snapshot.get("possession_home", 0.0),
                "possession_away": snapshot.get("possession_away", 0.0),
                "shots_total": round(_safe_float(snapshot.get("shots_home")) + _safe_float(snapshot.get("shots_away")), 3),
                "shots_on_target_total": round(_safe_float(snapshot.get("shots_on_target_home")) + _safe_float(snapshot.get("shots_on_target_away")), 3),
                "corners_total": round(_safe_float(snapshot.get("corners_home")) + _safe_float(snapshot.get("corners_away")), 3),
                "dangerous_attacks_total": round((
                    _safe_float(da_home if da_home is not None else 0)
                    + _safe_float(da_away if da_away is not None else 0)
                ), 3) if da_supported else None,
                "stats_available": bool(snapshot.get("stats_available")),
                "source": "fixtures/statistics",
            }
            _append_jsonl(out_path, row)
            existing_keys.add(k)
            written += 1

        processed_fixtures += 1
        time.sleep(max(0, sleep_ms) / 1000.0)

    finish_time = time.time()
    elapsed_total = round(finish_time - start_time, 3)
    soft_deadline_reached = soft_deadline_reached or (elapsed_total >= soft_deadline_sec)

    result = {
        "date": key,
        "minutes": minutes,
        "max_fixtures": max_fixtures,
        "snapshot_tolerance_min": SNAPSHOT_TOLERANCE_MIN,
        "fixture_time_budget_sec": FIXTURE_TIME_BUDGET_SEC,
        "soft_deadline_sec": soft_deadline_sec,
        "total_scout_fixtures": len(scout) if isinstance(scout, list) else 0,
        "processed_fixtures": processed_fixtures,
        "skipped_due_to_limit": skipped_due_to_limit,
        "skipped_slow_fixture": skipped_slow_fixture,
        "skipped_existing": skipped_existing,
        "skipped_not_reached": skipped_not_reached,
        "skipped_late": skipped_late,
        "skipped_state": skipped_state,
        "rows_no_stats": rows_no_stats,
        "rows_written": written,
        "snapshot_quality_counts": quality_counts,
        "soft_deadline_reached": soft_deadline_reached,
        "elapsed_seconds": elapsed_total,
        "last_fixture_id": last_fixture_id,
        "output_path": str(out_path),
    }

    # ── 写入 status JSON ──
    status_path = STATUS_DIR / f"v4_live_stats_snapshot_status_{key}.json"
    status = {
        "date": key,
        "started_at": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
        "finished_at": datetime.fromtimestamp(finish_time, tz=timezone.utc).isoformat(),
        "elapsed_seconds": elapsed_total,
        "max_fixtures": max_fixtures,
        "fixture_time_budget_sec": FIXTURE_TIME_BUDGET_SEC,
        "soft_deadline_sec": soft_deadline_sec,
        "soft_deadline_reached": soft_deadline_reached,
        "total_scout_fixtures": len(scout) if isinstance(scout, list) else 0,
        "processed_fixtures": processed_fixtures,
        "skipped_due_to_limit": skipped_due_to_limit,
        "skipped_slow_fixture": skipped_slow_fixture,
        "skipped_no_stats": skipped_no_stats,
        "rows_written": written,
        "snapshot_quality_counts": quality_counts,
        "last_fixture_id": last_fixture_id,
        "output_path": str(out_path),
        "status_path": str(status_path),
    }
    _write_status(status_path, status)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="V4赛中统计快照采集 — 仅用于赛后归因"
    )
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--minutes", default="15,30,45", help="逗号分隔，默认15,30,45")
    parser.add_argument("--fixture", type=int, default=None, help="仅采集单场fixture")
    parser.add_argument("--sleep-ms", type=int, default=120, help="API节流毫秒")
    parser.add_argument("--max-fixtures", type=int, default=DEFAULT_MAX_FIXTURES,
                        help=f"每轮最多处理的fixture数(默认{DEFAULT_MAX_FIXTURES})")
    parser.add_argument("--soft-deadline", type=int, default=int(SOFT_DEADLINE_SEC),
                        help=f"脚本软退出秒数(默认{int(SOFT_DEADLINE_SEC)})")
    args = parser.parse_args()
    minutes = []
    for x in str(args.minutes).split(","):
        x = x.strip()
        if not x:
            continue
        try:
            minutes.append(int(x))
        except Exception:
            continue
    if not minutes:
        minutes = [15, 30, 45]
    result = run(
        args.date,
        sorted(set(minutes)),
        fixture_id=args.fixture,
        sleep_ms=args.sleep_ms,
        max_fixtures=args.max_fixtures,
        soft_deadline_sec=float(args.soft_deadline),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
