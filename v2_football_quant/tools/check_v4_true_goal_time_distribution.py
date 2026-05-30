#!/usr/bin/env python3
"""check_v4_true_goal_time_distribution.py — 验证 V4 时间分布来自真实进球计数，而非 hit rate 归一化。"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))

VALID_SOURCES = frozenset({"events_goal_counts", "events_missing", "data_unavailable"})
VALID_SCRIPTS = frozenset({
    "开局冲击", "中段发力", "尾段压迫", "双段压迫", "均衡压迫", "弱剧本", "数据暂缺"
})


def main() -> int:
    ts = datetime.now(TZ).isoformat()
    violations = []
    checks = {}

    model_files = sorted(STATUS.glob("v4_control_center_model_*.json"))
    if not model_files:
        print("BLOCKER: no model")
        return 2
    with open(model_files[-1]) as f:
        model = json.load(f)

    items = model.get("candidates", {}).get("items", [])
    if not items:
        violations.append("no_candidates")
        checks["candidate_count"] = 0
        return _output(checks, violations, ts, warn_only=True)

    for i, item in enumerate(items):
        label = f"candidate_{i}"
        src = item.get("fh_goal_dist_source", "")

        # 1. Source must NOT be normalized_from_per_bin_hit_rates
        checks[f"{label}_not_normalized_hit_rate"] = src != "normalized_from_per_bin_hit_rates"
        if src == "normalized_from_per_bin_hit_rates":
            violations.append(f"{label}_still_using_hit_rate_normalization")

        # 2. Source must be valid
        checks[f"{label}_valid_source"] = src in VALID_SOURCES
        if src not in VALID_SOURCES and src:
            violations.append(f"{label}_invalid_source:{src}")

        # 3. If available, verify real goal counts
        available = item.get("fh_goal_dist_available", False)
        if available:
            total = item.get("fh_goal_dist_total_goals", 0)
            pct_015 = item.get("fh_goal_dist_0_15_pct")
            pct_1630 = item.get("fh_goal_dist_16_30_pct")
            pct_3145 = item.get("fh_goal_dist_31_45_pct")
            
            checks[f"{label}_has_real_goals"] = total > 0
            if total <= 0:
                violations.append(f"{label}_total_goals_zero_but_available")
            
            if pct_015 is not None and pct_1630 is not None and pct_3145 is not None:
                s = pct_015 + pct_1630 + pct_3145
                checks[f"{label}_dist_sum_99_101"] = 99.0 <= s <= 101.0
                if not (99.0 <= s <= 101.0):
                    violations.append(f"{label}_dist_sum_out_of_range:{s}")
        else:
            # Events unavailable — distribution should be null, not fake
            checks[f"{label}_dist_null_when_unavailable"] = (
                item.get("fh_goal_dist_0_15_pct") is None
                and item.get("fh_goal_dist_16_30_pct") is None
                and item.get("fh_goal_dist_31_45_pct") is None
            )
            if not checks[f"{label}_dist_null_when_unavailable"]:
                violations.append(f"{label}_fake_dist_when_events_missing")

        # 4. Playbook must be based on real distribution or "数据暂缺"
        ps = item.get("playbook_script", "")
        checks[f"{label}_playbook_valid"] = ps in VALID_SCRIPTS
        if ps not in VALID_SCRIPTS:
            violations.append(f"{label}_playbook_invalid:{ps}")
        
        if not available and ps != "数据暂缺":
            violations.append(f"{label}_playbook_should_be_missing_not:{ps}")

        # 5. hit_rate debug fields exist but not on main display
        hr_015 = item.get("fh_bin_hit_rate_0_15_pct")
        checks[f"{label}_hit_rate_debug_exists"] = hr_015 is not None

    # 6. H2H last10
    for item in items:
        used = item.get("h2h_used_count")
        limit = item.get("h2h_used_limit")
        if used is not None and limit is not None and used > limit:
            violations.append(f"h2h_used_exceeds_limit:{used}>{limit}")
    checks["h2h_last10_ok"] = all(
        (item.get("h2h_used_count") or 0) <= (item.get("h2h_used_limit") or 10)
        for item in items
    )

    # 7. source_group preserved
    checks["source_group_preserved"] = all(item.get("source_group") for item in items)

    # 8. Forbidden labels in candidate display fields
    for item in items:
        for field in ['script', 'script_type']:
            val = str(item.get(field, ''))
            for forbidden in ['57白名单', '全量合规', '正式候选', '候选剧本', 'HT进球剧本']:
                if forbidden in val:
                    violations.append(f"forbidden_label:{forbidden}")

    # 9. No N/A, undefined, null in display
    items_str = json.dumps(items)
    if "N/A" in items_str:
        violations.append("NA_found")
    if "undefined" in items_str:
        violations.append("undefined_found")

    # 10. Safety gates
    checks["unbet_amount_null"] = all(item.get("default_stake") is None for item in items)
    checks["unbet_entry_null"] = all(item.get("default_entry_minute") is None for item in items)
    checks["SKIP_not_in_cards"] = all(item.get("grade") != "SKIP" for item in items)

    # 11. h2h_engine has fh_goals support
    h2h_path = ROOT / "engine/data_sources/h2h_engine.py"
    if h2h_path.exists():
        h2h_src = h2h_path.read_text()
        checks["h2h_has_goal_counts"] = "fh_goals_0_15" in h2h_src and "fh_goals_total" in h2h_src
        checks["h2h_has_events_goal_counts"] = "events_goal_counts" in h2h_src
        if not checks["h2h_has_goal_counts"]:
            violations.append("h2h_engine_missing_fh_goals")

    return _output(checks, violations, ts)


def _output(checks, violations, ts, exit_code=None, warn_only=False):
    if warn_only:
        conclusion = "WARN_ONLY"
    else:
        conclusion = "PASS" if not violations else "BLOCKER"
    result = {
        "schema_version": "v4_true_goal_time_distribution.v1",
        "generated_at": ts,
        "checks": checks,
        "violations": violations,
        "conclusion": conclusion,
    }
    out = STATUS / "check_v4_true_goal_time_distribution_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Conclusion: {conclusion}")
    if violations:
        print("Violations:")
        for v in violations:
            print(f"  - {v}")
    return 0 if conclusion in {"PASS", "WARN_ONLY"} else (exit_code or 1)


if __name__ == "__main__":
    sys.exit(main())
