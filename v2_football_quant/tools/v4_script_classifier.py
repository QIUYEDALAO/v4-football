#!/usr/bin/env python3
"""V4 Script Classifier — BOSS-directed formal taxonomy (9 script types).

Priority-ordered classification from goal-time distribution data.
Taxonomy source: data/runtime/status/v4_script_taxonomy_20260520.json

Hard rules:
  - FULLTIME_OVER / SH_OU / FT_OU / SECOND_HALF_OVER are direction labels, NOT script names.
  - All m0_15/m16_30/m31_45 values are fractions (0.0-1.0). Multiply by 100 for display.
  - Priority matching: first condition that matches wins.
"""
from typing import Dict, Optional, Tuple


def classify_script(
    ht_score: Optional[float] = None,
    m0_15: Optional[float] = None,
    m16_30: Optional[float] = None,
    m31_45: Optional[float] = None,
    expected_goals: Optional[float] = None,
) -> Tuple[str, str]:
    """Classify match script type using formal 9-type taxonomy.

    Priority order (BOSS-specified):
      1. 数据不足 — missing any of m0_15/m16_30/m31_45
      2. 低压观察型 — HT < 60 or expected_goals < 1.2 or max(segments) < 35
      3. 开局冲击型（高压） — 0-15m >= 0.55 AND 16-30m >= 0.45
      4. 慢热绝杀型 — 31-45m >= 0.60 AND 0-15m <= 0.25
      5. 开局冲击型 — 0-15m is max AND 0-15m >= 0.45
      6. 中段压迫型 — 16-30m is max AND 16-30m >= 0.45
      7. 中后段发力型 — 31-45m is max AND 31-45m >= 0.55
      8. 双峰拉扯型 — any 2 segments >= 0.40 AND top-two gap <= 0.15
      9. 均衡持续型 — all 3 segments >= 0.30 AND max-min <= 0.20

    Returns:
        (script_type, script_reason) — Chinese script name and reasoning.
    """

    # ── Priority 1: 数据不足 ──
    if m0_15 is None or m16_30 is None or m31_45 is None:
        missing = []
        if m0_15 is None: missing.append("0-15m")
        if m16_30 is None: missing.append("16-30m")
        if m31_45 is None: missing.append("31-45m")
        return (
            "数据不足",
            f"缺少时间段分布字段: {', '.join(missing)}" + (
                f"；HT={ht_score}" if ht_score is not None else ""
            ),
        )

    # All three segments are available
    segments = {"0-15m": m0_15, "16-30m": m16_30, "31-45m": m31_45}
    # Sort segments by value descending
    sorted_segs = sorted(segments.items(), key=lambda x: x[1], reverse=True)
    max_label, max_val = sorted_segs[0]
    second_label, second_val = sorted_segs[1]
    min_label, min_val = sorted_segs[2]

    # ── Priority 2: 低压观察型 ──
    if ht_score is not None and ht_score < 60:
        return (
            "低压观察型",
            f"HT压力={ht_score}<60，全场压力偏低；分布: 0-15m={m0_15:.0%} 16-30m={m16_30:.0%} 31-45m={m31_45:.0%}",
        )
    if expected_goals is not None and expected_goals < 1.2:
        return (
            "低压观察型",
            f"预计进球={expected_goals}<1.2，进攻预期不足",
        )
    if max_val < 0.35:
        return (
            "低压观察型",
            f"三段压力均不足35%（最高={max_label}={max_val:.0%}），缺乏明确信号",
        )

    # ── Priority 3: 开局冲击型（高压） ──
    if m0_15 >= 0.55 and m16_30 >= 0.45:
        return (
            "开局冲击型（高压）",
            f"0-15m={m0_15:.0%}≥55% 且 16-30m={m16_30:.0%}≥45%，开局高压持续至中段",
        )

    # ── Priority 4: 慢热绝杀型 ──
    if m31_45 >= 0.60 and m0_15 <= 0.25:
        return (
            "慢热绝杀型",
            f"31-45m={m31_45:.0%}≥60% 且 0-15m={m0_15:.0%}≤25%，开局慢热后程绝杀",
        )

    # ── Priority 5: 开局冲击型 ──
    if max_label == "0-15m" and m0_15 >= 0.45:
        return (
            "开局冲击型",
            f"0-15m={m0_15:.0%}为最高段且≥45%，开局压力主导",
        )

    # ── Priority 6: 中段压迫型 ──
    if max_label == "16-30m" and m16_30 >= 0.45:
        return (
            "中段压迫型",
            f"16-30m={m16_30:.0%}为最高段且≥45%，中场压迫主导",
        )

    # ── Priority 7: 中后段发力型 ──
    if max_label == "31-45m" and m31_45 >= 0.55:
        return (
            "中后段发力型",
            f"31-45m={m31_45:.0%}为最高段且≥55%，后段发力特征明显",
        )

    # ── Priority 8: 双峰拉扯型 ──
    high_count = sum(1 for v in [m0_15, m16_30, m31_45] if v >= 0.40)
    if high_count >= 2 and (max_val - second_val) <= 0.15:
        return (
            "双峰拉扯型",
            f"{high_count}个时段≥40%（{max_label}={max_val:.0%}, {second_label}={second_val:.0%}），差值={max_val-second_val:.0%}≤15%，多段博弈",
        )

    # ── Priority 9: 均衡持续型 ──
    if m0_15 >= 0.30 and m16_30 >= 0.30 and m31_45 >= 0.30 and (max_val - min_val) <= 0.20:
        return (
            "均衡持续型",
            f"三段均≥30%，压力差={max_val-min_val:.0%}≤20%，均衡分布",
        )

    # ── Fallback: data insufficient despite having numbers ──
    return (
        "数据不足",
        f"分布数据存在但不符合任何已知剧本模式（{max_label}={max_val:.0%}, {second_label}={second_val:.0%}, {min_label}={min_val:.0%}）",
    )


def get_display_script(entry: dict) -> dict:
    """Extract script classification from a candidate entry dict.

    Expects entry with keys: ht_score, goal_time_distribution (with m0_15/m16_30/m31_45/available),
    best_score, expected_goals.

    Returns dict with: script_type, script_reason, expected_goals_display,
    ht_pressure, strength_pct, best_score, distribution_text, distribution_available.
    """
    ht = entry.get("ht_score")
    best = entry.get("best_score")
    dist = entry.get("goal_time_distribution", {}) or {}
    exp_goals_raw = entry.get("expected_goals")
    # Parse expected_goals — may be string like "2.12球" or float
    exp_goals = None
    if isinstance(exp_goals_raw, (int, float)):
        exp_goals = float(exp_goals_raw)
    elif isinstance(exp_goals_raw, str):
        import re
        m = re.match(r'([\d.]+)', exp_goals_raw)
        if m:
            exp_goals = float(m.group(1))

    m0_15 = dist.get("m0_15")
    m16_30 = dist.get("m16_30")
    m31_45 = dist.get("m31_45")
    dist_available = dist.get("available", False) if isinstance(dist, dict) else False

    script_type, script_reason = classify_script(
        ht_score=ht,
        m0_15=m0_15,
        m16_30=m16_30,
        m31_45=m31_45,
        expected_goals=exp_goals,
    )

    # Build distribution display text (values are fractions, multiply by 100)
    if dist_available and all(v is not None for v in [m0_15, m16_30, m31_45]):
        p0 = int(round(float(m0_15) * 100))
        p16 = int(round(float(m16_30) * 100))
        p31 = int(round(float(m31_45) * 100))
        dist_text = f"0-15m {p0}% | 16-30m {p16}% | 31-45m {p31}%"
    else:
        dist_text = "暂无完整时间分布数据"

    # Expected goals display
    if exp_goals is not None:
        eg_display = f"{exp_goals}球"
    elif best is not None:
        eg_display = f"{round(best / 40, 2)}球"
    else:
        eg_display = "暂无数据"

    # Strength percentage
    if best is not None:
        strength = f"{min(round(best, 1), 100)}%"
    else:
        strength = "暂无数据"

    return {
        "script_type": script_type,
        "script_reason": script_reason,
        "expected_goals_display": eg_display,
        "ht_pressure": ht,
        "strength_pct": strength,
        "best_score": best,
        "distribution_text": dist_text,
        "distribution_available": dist_available,
    }


# Standalone smoke test
if __name__ == "__main__":
    test_cases = [
        # (ht, m0_15, m16_30, m31_45, expected_goals, description)
        (None, None, None, None, None, "数据不足 — all None"),
        (79, None, None, None, None, "数据不足 — no distribution, has HT"),
        (55, None, None, None, None, "数据不足 — no distribution, low HT"),
        # Taxonomy test cases
        (85, 0.40, 0.60, 0.30, 2.0, "Palmeiras 40/60/30 → 中段压迫型"),
        (61, 0.20, 0.30, 0.60, 1.5, "Hangzhou 20/30/60 → 慢热绝杀型"),
        (80, 0.60, 0.50, 0.40, 2.0, "Ilves 60/50/40 → 开局冲击型（高压）"),
        (70, 0.10, 0.50, 0.40, 1.8, "Start 10/50/40 → 中段压迫型"),
        (64, 0.10, 0.60, 0.40, 1.5, "Santos 10/60/40 → 中段压迫型"),
        (60, 0.30, 0.50, 0.40, 1.4, "Shanghai 30/50/40 → 中段压迫型"),
        (60, 0.40, 0.10, 0.40, 1.4, "KuPS 40/10/40 → 双峰拉扯型"),
        (60, 0.30, 0.30, 0.40, 1.3, "Pyramids 30/30/40 → 均衡持续型"),
        (55, 0.10, 0.30, 0.30, 1.2, "Zamalek 10/30/30 → 均衡持续型"),
        (60, 0.30, 0.80, 0.30, 1.5, "Al Khaleej 30/80/30 → 中段压迫型"),
        (60, 0.50, 0.40, 0.40, 1.4, "Aalesund 50/40/40 → 开局冲击型"),
        # Edge cases
        (50, 0.30, 0.30, 0.30, 1.0, "Low HT + low goals → 低压观察型"),
        (75, 0.55, 0.55, 0.20, 2.0, "Dual high → 开局冲击型（高压）"),
        (75, 0.50, 0.45, 0.55, 2.0, "late surge → 中后段发力型"),
    ]
    for ht, m0, m16, m31, eg, desc in test_cases:
        st, sr = classify_script(ht, m0, m16, m31, eg)
        dist = "Y" if all(v is not None for v in [m0, m16, m31]) else "N"
        print(f"[{st}] {desc}")
        print(f"  reason: {sr}")
