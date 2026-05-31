#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from engine.market_bookmaker_fallback import BOOKMAKER_PRIORITY, capture_ht_ou_snapshot  # noqa: E402
from engine.rf_shadow_fields import build_rf_shadow_grade_layer  # noqa: E402


def _run_guard() -> dict | None:
    cmd = [sys.executable, str(BASE / "tools" / "check_v4_production_default_rules_guard.py")]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        return None
    out = p.stdout.strip()
    if not out.startswith("{"):
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


def _staged_files() -> list[str]:
    p = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(BASE),
    )
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]


def _assert(cond: bool, ok_msg: str, err_msg: str, errors: list[str]) -> None:
    if cond:
        print(f"  ✅ {ok_msg}")
    else:
        print(f"  ❌ {err_msg}")
        errors.append(err_msg)


def main() -> int:
    errors: list[str] = []
    blocks: list[str] = []

    print("🔍 V4 Market Bookmaker Fallback Checker\n")

    # 1) _capture_ht_ou_lines no longer pinnacle-only
    runner = (BASE / "engine" / "v4_runner.py").read_text(encoding="utf-8")
    _assert(
        'if "Pinnacle" not in bo.get("name", "")' not in runner,
        "_capture_ht_ou_lines 不再 Pinnacle-only",
        "_capture_ht_ou_lines 仍包含 Pinnacle-only 过滤",
        errors,
    )
    _assert(
        "capture_ht_ou_snapshot" in runner,
        "runner 已接入 capture_ht_ou_snapshot",
        "runner 未接入 capture_ht_ou_snapshot",
        errors,
    )

    # 2) priority list
    _assert(
        BOOKMAKER_PRIORITY and BOOKMAKER_PRIORITY[0] == "Pinnacle",
        "Pinnacle 仍为最高优先级",
        "Pinnacle 非最高优先级",
        errors,
    )
    _assert(
        len(BOOKMAKER_PRIORITY) >= 7 and "Bet365" in BOOKMAKER_PRIORITY,
        "fallback bookmaker 列表存在",
        "fallback bookmaker 列表缺失",
        errors,
    )

    # Synthetic case: Pinnacle missing HT OU, Bet365 has HT OU
    odds_fallback = {
        "response": [
            {
                "bookmakers": [
                    {
                        "name": "Pinnacle",
                        "bets": [{"name": "Match Winner", "values": [{"value": "Home", "odd": "2.1"}]}],
                    },
                    {
                        "name": "Bet365",
                        "bets": [
                            {
                                "name": "First Half Over/Under",
                                "values": [
                                    {"value": "Over 1.0", "odd": "1.90"},
                                    {"value": "Under 1.0", "odd": "1.92"},
                                ],
                            }
                        ],
                    },
                ]
            }
        ]
    }
    s1 = capture_ht_ou_snapshot(odds_fallback)
    _assert(
        s1.get("ht_ou_detected") is True and s1.get("bookmaker_used") == "Bet365",
        "合成样本(Pinnacle无, Bet365有) 可识别 HT OU",
        f"fallback样本识别失败: {s1}",
        errors,
    )
    _assert(
        s1.get("market_source") == "BOOKMAKER_FALLBACK",
        "fallback 来源标记正确",
        f"fallback 来源错误: {s1.get('market_source')}",
        errors,
    )

    # Synthetic case: Pinnacle has HT OU
    odds_pin = {
        "response": [
            {
                "bookmakers": [
                    {
                        "name": "Pinnacle",
                        "bets": [
                            {
                                "name": "1st Half Over/Under",
                                "values": [
                                    {"value": "Over 0.5", "odd": "1.66"},
                                    {"value": "Under 0.5", "odd": "2.12"},
                                ],
                            }
                        ],
                    },
                    {
                        "name": "Bet365",
                        "bets": [
                            {
                                "name": "First Half Over/Under",
                                "values": [
                                    {"value": "Over 0.5", "odd": "1.71"},
                                    {"value": "Under 0.5", "odd": "2.05"},
                                ],
                            }
                        ],
                    },
                ]
            }
        ]
    }
    s2 = capture_ht_ou_snapshot(odds_pin)
    _assert(
        s2.get("bookmaker_used") == "Pinnacle" and s2.get("market_source") == "PINNACLE_PRIMARY",
        "Pinnacle 有 HT OU 时仍优先 Pinnacle",
        f"Pinnacle 主源逻辑失败: {s2}",
        errors,
    )

    # Synthetic case: only full-time OU should not pass
    odds_ft_only = {
        "response": [
            {
                "bookmakers": [
                    {
                        "name": "Bet365",
                        "bets": [
                            {
                                "name": "Goals Over/Under",
                                "values": [
                                    {"value": "Over 2.5", "odd": "1.95"},
                                    {"value": "Under 2.5", "odd": "1.90"},
                                ],
                            }
                        ],
                    }
                ]
            }
        ]
    }
    s3 = capture_ht_ou_snapshot(odds_ft_only)
    _assert(
        s3.get("ht_ou_detected") is False and s3.get("market_source") == "NO_HT_OU",
        "仅全场OU不会被识别为HT OU",
        f"全场OU被误识别: {s3}",
        errors,
    )

    # Synthetic case: no odds -> MARKET_NO_DATA via grade layer
    s4 = capture_ht_ou_snapshot({"response": []})
    market = build_rf_shadow_grade_layer(
        {
            "prematch_ht_line": None,
            "prematch_over_odds": None,
            "prematch_under_odds": None,
            "no_market_excluded": False,
            "recent10_sample_count_home": 0,
            "recent10_sample_count_away": 0,
        }
    )
    _assert(
        s4.get("market_source") == "NO_ODDS" and market.get("opening_market_support_status") == "MARKET_NO_DATA",
        "无odds时保持 MARKET_NO_DATA",
        f"无odds状态异常: snapshot={s4}, market={market.get('opening_market_support_status')}",
        errors,
    )

    # Required output fields
    _assert(
        all(k in s2 for k in ["bookmaker_used", "bookmaker_priority", "market_source", "market_name", "bet_name"]),
        "输出字段包含 bookmaker_used / market_source",
        "输出字段缺失 bookmaker/source",
        errors,
    )

    # Guard: DEFAULT_RULES / cron / validation / live bet / QQ
    guard = _run_guard()
    if not guard:
        blocks.append("无法读取 DEFAULT_RULES guard")
        print("  🚫 无法读取 DEFAULT_RULES guard")
    else:
        _assert(guard.get("conclusion") == "PASS", "DEFAULT_RULES guard PASS", "DEFAULT_RULES guard 非PASS", errors)
        forbidden = guard.get("forbidden_flags", {})
        for key in [
            "cron_modified",
            "validation_recomputed",
            "live_bet_raw_records_modified",
            "QQ_recommendation_pushed",
        ]:
            if forbidden.get(key) is True:
                blocks.append(f"forbidden flag true: {key}")
                print(f"  🚫 {key}=true")
            else:
                print(f"  ✅ {key}=false")

    staged = _staged_files()
    if any("data/runtime" in s for s in staged):
        errors.append("runtime artifact staged")
        print("  ❌ runtime artifact staged")
    else:
        print("  ✅ runtime artifact not staged")
    secret_hits = [s for s in staged if any(k in s.lower() for k in [".env", "secret", "token", "apikey", "api_key"])]
    if secret_hits:
        blocks.append(f"secrets staged: {secret_hits}")
        print(f"  🚫 secrets staged: {secret_hits}")
    else:
        print("  ✅ no secrets staged")

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

