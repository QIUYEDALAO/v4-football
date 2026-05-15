#!/usr/bin/env python3
"""engine/v2_window_worker.py — V2窗口检查器 worker（子进程）

不做了：全量扫描、每天生成日报、全量拉赔率。
只做：检查哪些比赛进入了关键窗口，只处理那些比赛。

调用方：v2_window_checker_with_watchdog.py (supervisor)
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOCAL_TZ = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "data" / "state"


def get_stage(minutes_to_ko: int) -> str:
    if minutes_to_ko < 0:
        return "STARTED_OR_CLOSED"
    if minutes_to_ko <= 15:
        return "T_MINUS_15M"
    if minutes_to_ko <= 45:
        return "T_MINUS_45M"
    if minutes_to_ko <= 90:
        return "T_MINUS_90M"
    if minutes_to_ko <= 180:
        return "T_MINUS_3H"
    if minutes_to_ko <= 360:
        return "T_MINUS_6H"
    if minutes_to_ko <= 720:
        return "T_MINUS_12H"
    return "FAR_FUTURE"


def load_state(today_str: str) -> tuple[set, dict]:
    state_file = STATE_DIR / f"selected_fixtures_{today_str}.json"
    if not state_file.exists():
        return set(), {}
    with open(state_file) as f:
        sp = json.load(f)
    if isinstance(sp, dict):
        selected = set(sp.get("selected_fixture_ids", []))
        fixtures = sp.get("fixtures", {}) or {}
    else:
        selected = set(sp)
        fixtures = {}
    return selected, fixtures


def write_state(today_str: str, selected: set, fixtures: dict) -> None:
    state_file = STATE_DIR / f"selected_fixtures_{today_str}.json"
    state = {
        "selected_fixture_ids": sorted(selected),
        "fixtures": fixtures,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(state_file, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    today_str = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    now_local = datetime.now(LOCAL_TZ)

    selected, fixtures = load_state(today_str)

    if not fixtures:
        print("WINDOW_STATUS=SKIPPED_NO_ACTIVE_WINDOW")
        print("REASON=无建池数据")
        sys.exit(0)

    # ── 遍历所有比赛，分类入窗口 ──
    window_summary = {
        "T_MINUS_12H": 0,
        "T_MINUS_6H": 0,
        "T_MINUS_3H": 0,
        "T_MINUS_90M": 0,
        "T_MINUS_45M": 0,
        "T_MINUS_15M": 0,
        "FAR_FUTURE": 0,
        "STARTED_OR_CLOSED": 0,
    }
    new_locks = []

    for fid_str, fstate in fixtures.items():
        # 已锁定或已取消锁定 → 跳过
        if fstate.get("locked_stage") or fstate.get("lock_cancelled"):
            continue

        ko_str = fstate.get("kickoff_time") or fstate.get("last_seen_time", "")
        if not ko_str:
            continue

        try:
            ko_str_clean = ko_str.replace("Z", "+00:00")
            ko_dt = datetime.fromisoformat(ko_str_clean)
            if ko_dt.tzinfo is None:
                ko_dt = ko_dt.replace(tzinfo=LOCAL_TZ)
            else:
                ko_dt = ko_dt.astimezone(LOCAL_TZ)
        except Exception:
            continue

        minutes_to_ko = int((ko_dt - now_local).total_seconds() / 60)
        stage = get_stage(minutes_to_ko)

        if stage in window_summary:
            window_summary[stage] += 1

        # ── T-90 / T-45：检查是否可锁定 ──
        if stage in ("T_MINUS_90M", "T_MINUS_45M") and fid_str not in selected:
            odds_D = fstate.get("last_seen_odds_D")
            if odds_D and 2.00 <= odds_D <= 2.90:
                lock_time = datetime.now(timezone.utc).isoformat()
                fstate["locked_stage"] = stage
                fstate["locked_odds_D"] = odds_D
                fstate["locked_time"] = lock_time
                fstate["lock_cancelled"] = False
                fstate["lock_cancel_reason"] = None
                fstate["final_observed_odds_D"] = odds_D
                fstate["final_odds_status"] = "LOCKED_IN_BAND"
                selected.add(fid_str)
                new_locks.append(fid_str)

        # ── T-15m：只记录最终价格 ──
        if stage == "T_MINUS_15M":
            fstate["final_odds_status"] = "FINAL_RECORD"
            fstate["final_observed_odds_D"] = fstate.get("last_seen_odds_D")

    # ── 写回状态文件 ──
    write_state(today_str, selected, fixtures)

    # ── 判定 WINDOW_STATUS ──
    has_early = (window_summary["T_MINUS_12H"] + window_summary["T_MINUS_6H"]) > 0
    has_candidate = window_summary["T_MINUS_3H"] > 0
    has_lock_window = (window_summary["T_MINUS_90M"] + window_summary["T_MINUS_45M"]) > 0
    has_final = window_summary["T_MINUS_15M"] > 0
    has_any = has_early or has_candidate or has_lock_window or has_final

    has_future = (window_summary["T_MINUS_12H"] + window_summary["T_MINUS_6H"] +
                  window_summary["T_MINUS_3H"] + window_summary["T_MINUS_90M"] +
                  window_summary["T_MINUS_45M"] + window_summary["T_MINUS_15M"] +
                  window_summary["FAR_FUTURE"]) > 0
    started_only = window_summary["STARTED_OR_CLOSED"] > 0 and not has_future

    if started_only:
        window_status = "SKIPPED_STARTED_OR_CLOSED"
        reason = f"{window_summary['STARTED_OR_CLOSED']}场已开赛或窗口关闭，本轮不处理"
    elif not has_any:
        window_status = "SKIPPED_NO_ACTIVE_WINDOW"
        reason = "未来比赛存在但无进入关键窗口"
    elif has_lock_window and len(new_locks) > 0:
        window_status = "DONE_BET_LOCKED"
        reason = f"T-90/T-45 符合赔率带，新增 {len(new_locks)} 场锁定"
    elif has_lock_window and len(new_locks) == 0:
        window_status = "DONE_NO_BET_LOCKED"
        reason = "T-90/T-45 有比赛但无符合赔率带"
    elif has_final and not has_early and not has_candidate and not has_lock_window:
        window_status = "DONE_FINAL_RECORD"
        reason = f"FINAL_RECORD：{window_summary['T_MINUS_15M']} 场"
    else:
        window_status = "DONE_WATCH_ONLY"
        reason = "WATCH_EARLY / CANDIDATE 窗口无新锁定"

    # ── 输出结构化结果 ──
    print(f"WINDOW_STATUS={window_status}")
    print(f"REASON={reason}")
    print(f"WINDOW_SUMMARY={json.dumps(window_summary, ensure_ascii=False)}")
    print(f"NEW_LOCKS={json.dumps(new_locks, ensure_ascii=False)}")
    print(f"LOCKED_TOTAL={len(selected)}")
    print(f"WATCH_EARLY={window_summary['T_MINUS_12H'] + window_summary['T_MINUS_6H']}")
    print(f"CANDIDATE={window_summary['T_MINUS_3H']}")
    print(f"FINAL_RECORD={window_summary['T_MINUS_15M']}")
    print(f"ODDS_OUT=0")


if __name__ == "__main__":
    main()
