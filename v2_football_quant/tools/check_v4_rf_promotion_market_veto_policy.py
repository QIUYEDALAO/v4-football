#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from engine.rf_shadow_fields import build_rf_shadow_grade_layer  # noqa: E402
from tools.build_v4_rf_shadow_to_official_promotion_dryrun import compute_dryrun_grade  # noqa: E402


def _assert(cond: bool, ok_msg: str, err_msg: str, errors: list[str]) -> None:
    if cond:
        print(f"  ✅ {ok_msg}")
    else:
        print(f"  ❌ {err_msg}")
        errors.append(err_msg)


def _run_json_tool(tool: str) -> dict | None:
    p = subprocess.run(
        [sys.executable, str(BASE / "tools" / tool)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if p.returncode != 0:
        return None
    t = p.stdout.strip()
    if not t.startswith("{"):
        return None
    try:
        return json.loads(t)
    except Exception:
        return None


def _staged() -> list[str]:
    p = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(BASE),
    )
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]


def _mk_fixture(
    *,
    rf_grade: str,
    market_status: str,
    conf: int,
    no_market=False,
    line=1.0,
    over=1.9,
    h2h_status="H2H_NO_BONUS",
) -> dict:
    return {
        "fixture_id": 999000 + conf,
        "rf_shadow_grade": rf_grade,
        "market_adjusted_shadow_grade": rf_grade,
        "opening_market_support_status": market_status,
        "opening_market_available": not no_market,
        "opening_market_data_status": "NO_MARKET" if no_market else "HAS_DATA",
        "opening_ht_ou_line": line,
        "opening_ht_ou_over_odds": over,
        "rf_shadow_confidence": conf,
        "h2h_recent5_support_status": h2h_status,
    }


def main() -> int:
    errors: list[str] = []
    blocks: list[str] = []
    print("🔍 V4 RF Promotion Market Veto Policy Checker\n")

    # 1-4 conflict layers exist
    rf_source = (BASE / "engine" / "rf_shadow_fields.py").read_text(encoding="utf-8")
    _assert("MARKET_LIGHT_CONFLICT" in rf_source, "存在 MARKET_LIGHT_CONFLICT", "缺少 MARKET_LIGHT_CONFLICT", errors)
    _assert("MARKET_STRONG_CONFLICT" in rf_source, "存在 MARKET_STRONG_CONFLICT", "缺少 MARKET_STRONG_CONFLICT", errors)
    _assert("MARKET_EXTREME_VETO" in rf_source, "存在 MARKET_EXTREME_VETO", "缺少 MARKET_EXTREME_VETO", errors)

    # 5 RF A + LIGHT_CONFLICT not skip
    f1 = _mk_fixture(rf_grade="A", market_status="MARKET_WEAK_VETO", conf=82, line=0.9, over=2.0)
    g1, p1 = compute_dryrun_grade(f1, f1["fixture_id"])
    _assert(g1 in {"DRYRUN_B", "DRYRUN_C_OBSERVE"}, "RF A + 普通反向不直接SKIP", f"RF A + LIGHT_CONFLICT异常: {g1} {p1}", errors)

    # 6 RF A + STRONG_CONFLICT + high confidence => C observe
    f2 = _mk_fixture(rf_grade="A", market_status="MARKET_HARD_VETO", conf=88, line=0.5, over=2.21)
    g2, p2 = compute_dryrun_grade(f2, f2["fixture_id"])
    _assert(g2 == "DRYRUN_C_OBSERVE", "RF A + STRONG_CONFLICT(高信心) => C观察", f"STRONG_CONFLICT高信心异常: {g2} {p2}", errors)

    # 7 RF B + LIGHT_CONFLICT => C observe
    f3 = _mk_fixture(rf_grade="B", market_status="MARKET_WEAK_VETO", conf=78)
    g3, p3 = compute_dryrun_grade(f3, f3["fixture_id"])
    _assert(g3 == "DRYRUN_C_OBSERVE", "RF B + LIGHT_CONFLICT => C观察", f"RF B + LIGHT_CONFLICT异常: {g3} {p3}", errors)

    # 8/9 MARKET_NO_DATA cannot A; strong RF can B/C observe
    f4 = _mk_fixture(rf_grade="A", market_status="MARKET_NO_DATA", conf=80)
    g4, p4 = compute_dryrun_grade(f4, f4["fixture_id"])
    _assert(g4 in {"DRYRUN_B", "DRYRUN_C_OBSERVE"}, "MARKET_NO_DATA 强RF可B/C观察", f"NO_DATA强RF异常: {g4} {p4}", errors)
    _assert(g4 != "DRYRUN_A", "MARKET_NO_DATA 不升A", f"NO_DATA错误升A: {g4}", errors)

    # 10/11/12 H2H bonus-only non-demotion checks (function-level)
    base_record = {
        "recent10_sample_count_home": 10,
        "recent10_sample_count_away": 10,
        "home_recent10_fh_involved_rate": 0.8,
        "away_recent10_fh_involved_rate": 0.8,
        "home_recent5_fh_involved_rate": 1.0,
        "away_recent5_fh_involved_rate": 1.0,
        "combined_recent10_fh_involved_rate": 0.8,
        "combined_recent5_fh_involved_rate": 1.0,
        "prematch_ht_line": 1.0,
        "prematch_over_odds": 1.90,
        "prematch_under_odds": 1.90,
        "no_market_excluded": False,
    }
    low_sample = build_rf_shadow_grade_layer(base_record, factors={"h2h_official_sample_size": 2, "h2h_ht_goal_rate": 1.0})
    _assert(low_sample.get("h2h_recent5_support_status") == "H2H_LOW_SAMPLE", "H2H_LOW_SAMPLE 状态存在", "H2H_LOW_SAMPLE 状态缺失", errors)
    _assert(low_sample.get("market_adjusted_shadow_grade") != "SKIP", "H2H_LOW_SAMPLE 不直接降级为SKIP", "H2H_LOW_SAMPLE 触发降级异常", errors)

    no_bonus = build_rf_shadow_grade_layer(base_record, factors={"h2h_official_sample_size": 5, "h2h_ht_goal_rate": 0.2})
    _assert(no_bonus.get("h2h_recent5_support_status") == "H2H_NO_BONUS", "H2H_NO_BONUS 状态存在", "H2H_NO_BONUS 状态缺失", errors)
    _assert(no_bonus.get("market_adjusted_shadow_grade") in {"A", "B", "C"}, "H2H_NO_BONUS 不硬降级", "H2H_NO_BONUS 触发异常降级", errors)

    strong_bonus = build_rf_shadow_grade_layer(base_record, factors={"h2h_official_sample_size": 5, "h2h_ht_goal_rate": 1.0})
    _assert(strong_bonus.get("h2h_recent5_support_status") == "H2H_STRONG_BONUS", "H2H_STRONG_BONUS 状态存在", "H2H_STRONG_BONUS 状态缺失", errors)
    _assert(strong_bonus.get("market_adjusted_shadow_grade") in {"A", "B", "C"}, "H2H_STRONG_BONUS 不单独制造新级别", "H2H_STRONG_BONUS 异常", errors)

    # 13 full-time OU cannot pretend HT OU (delegated checker)
    p = subprocess.run([sys.executable, str(BASE / "tools" / "check_v4_market_bookmaker_fallback.py")], capture_output=True, text=True, timeout=120)
    _assert(p.returncode == 0, "full-time OU 冒充 HT OU 检查通过", "bookmaker fallback checker 未通过", errors)

    # 14-22 safety guards
    guard = _run_json_tool("check_v4_production_default_rules_guard.py")
    if not guard:
        blocks.append("DEFAULT_RULES guard 不可解析")
    else:
        _assert(guard.get("conclusion") == "PASS", "DEFAULT_RULES 未改", "DEFAULT_RULES guard 非PASS", errors)
        ff = guard.get("forbidden_flags", {})
        _assert(ff.get("cron_modified") is False, "cron 未改", "cron_modified=true", errors)
        _assert(ff.get("validation_recomputed") is False, "validation 未重算", "validation_recomputed=true", errors)
        _assert(ff.get("live_bet_raw_records_modified") is False, "live bet 未改", "live_bet_raw_records_modified=true", errors)
        _assert(ff.get("QQ_recommendation_pushed") is False, "QQ 未推", "QQ_recommendation_pushed=true", errors)

    staged = _staged()
    _assert(not any("data/runtime" in s for s in staged), "runtime artifact 未stage", "runtime artifact 被stage", errors)
    _assert(
        not any(any(k in s.lower() for k in [".env", "secret", "token", "apikey", "api_key"]) for s in staged),
        "no secrets staged",
        "发现 secrets staged",
        errors,
    )

    print(f"\nRESULT: errors={len(errors)}, blockers={len(blocks)}")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
    if blocks:
        for b in blocks:
            print(f"  🚫 {b}")
    if blocks:
        return 2
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

