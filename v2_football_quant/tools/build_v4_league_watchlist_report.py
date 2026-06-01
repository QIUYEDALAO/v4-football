#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "data/runtime/validation"
WEEKLY_DIR = ROOT / "data/weekly_reports"
MONTHLY_DIR = ROOT / "data/monthly_reports"
LEDGER = VALIDATION / "v4_league_performance_ledger_latest.json"
LEDGER_BUILDER = ROOT / "tools/build_v4_league_performance_ledger.py"

ALLOWED_ACTION_HINTS = {
    "KEEP_OBSERVE",
    "WATCH_ONLY",
    "LOW_TRUST_OBSERVE_ONLY",
    "LOW_SAMPLE_DO_NOT_CONCLUDE",
    "PENDING_ONLY_NO_DENOMINATOR",
    "DATA_GAP_REVIEW",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def ensure_ledger() -> tuple[dict[str, Any], str]:
    if LEDGER.exists():
        return load_json(LEDGER), "EXISTING"
    run = subprocess.run(
        ["python3", str(LEDGER_BUILDER)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        return {}, f"BUILD_FAILED:{run.stderr[-500:] or run.stdout[-500:]}"
    return load_json(LEDGER), "BUILT_RUNTIME"


def explanation_and_hint(row: dict[str, Any]) -> tuple[str, str]:
    tag = str(row.get("trust_tag") or "")
    sample = str(row.get("sample_tag") or "")
    if tag == "KEEP":
        return "长期样本与命中表现稳定，继续观察。", "KEEP_OBSERVE"
    if tag == "WATCH":
        return "长期表现接近观察阈值，保持跟踪。", "WATCH_ONLY"
    if tag == "LOW_TRUST_ALERT":
        return "长期低命中预警，仅观察，不自动排除。", "LOW_TRUST_OBSERVE_ONLY"
    if tag == "PENDING_ONLY" or sample == "PENDING_ONLY":
        return "延期/未完赛，仅记录，不进入命中率分母。", "PENDING_ONLY_NO_DENOMINATOR"
    if tag in {"LOW_SAMPLE_ONLY", "DO_NOT_CONCLUDE"}:
        return "样本不足，不下结论，仅观察。", "LOW_SAMPLE_DO_NOT_CONCLUDE"
    return "数据质量需复核，仅观察，不自动影响评级。", "DATA_GAP_REVIEW"


def league_item(row: dict[str, Any]) -> dict[str, Any]:
    explanation, hint = explanation_and_hint(row)
    item = {
        "league": row.get("league"),
        "validated_count": int(row.get("validated_count") or 0),
        "pending_count": int(row.get("pending_count") or 0),
        "hit_count": int(row.get("hit_count") or 0),
        "miss_count": int(row.get("miss_count") or 0),
        "hit_rate": float(row.get("hit_rate") or 0.0),
        "A_count": int(row.get("A_count") or 0),
        "A_hit_rate": float(row.get("A_hit_rate") or 0.0),
        "B_count": int(row.get("B_count") or 0),
        "B_hit_rate": float(row.get("B_hit_rate") or 0.0),
        "rescue_hit_rate": float(row.get("rescue_hit_rate") or 0.0),
        "non_rescue_hit_rate": float(row.get("non_rescue_hit_rate") or 0.0),
        "sample_tag": row.get("sample_tag"),
        "trust_tag": row.get("trust_tag"),
        "confidence_level": row.get("confidence_level"),
        "warning_flags": list(row.get("warning_flags") or []),
        "last_seen_date": row.get("last_seen_date") or "",
        "explanation": explanation,
        "action_hint": hint,
    }
    if item["action_hint"] not in ALLOWED_ACTION_HINTS:
        item["action_hint"] = "DATA_GAP_REVIEW"
    return item


def top_bottom(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid = [row for row in rows if int(row.get("validated_count") or 0) > 0]
    ranked = sorted(
        valid,
        key=lambda x: (float(x.get("hit_rate") or 0.0), int(x.get("validated_count") or 0)),
        reverse=True,
    )
    top = [league_item(row) for row in ranked[:8]]
    bottom = [league_item(row) for row in sorted(ranked, key=lambda x: (float(x.get("hit_rate") or 0.0), -int(x.get("validated_count") or 0)))[:8]]
    return top, bottom


def build_payload(report_type: str) -> dict[str, Any]:
    ledger, ledger_status = ensure_ledger()
    rows = list(ledger.get("leagues") or [])
    grouped = {
        "KEEP": [],
        "WATCH": [],
        "LOW_TRUST_ALERT": [],
        "LOW_SAMPLE_ONLY": [],
        "DO_NOT_CONCLUDE": [],
        "PENDING_ONLY": [],
        "DATA_GAP": [],
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        tag = str(row.get("trust_tag") or "DATA_GAP")
        if tag not in grouped:
            tag = "DATA_GAP"
        grouped[tag].append(league_item(row))
    for key in grouped:
        grouped[key].sort(key=lambda x: (-x["validated_count"], x["league"] or ""))

    top, bottom = top_bottom(rows)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "report_type": report_type,
        "source_ledger_path": str(LEDGER),
        "source_ledger_resolved": ledger.get("source_ledger_resolved") or "NOT_FOUND",
        "trend_anchor_date": ledger.get("trend_anchor_date") or "DATA_MISSING",
        "total_leagues": int(ledger.get("league_count") or 0),
        "total_validated": int(ledger.get("total_validated") or 0),
        "total_pending": int(ledger.get("total_pending") or 0),
        "keep_leagues": grouped["KEEP"],
        "watch_leagues": grouped["WATCH"],
        "low_trust_alert_leagues": grouped["LOW_TRUST_ALERT"],
        "low_sample_leagues": grouped["LOW_SAMPLE_ONLY"],
        "do_not_conclude_leagues": grouped["DO_NOT_CONCLUDE"],
        "pending_only_leagues": grouped["PENDING_ONLY"],
        "data_gap_leagues": grouped["DATA_GAP"],
        "top_hit_rate_leagues": top,
        "bottom_hit_rate_leagues": bottom,
        "sample_insufficient_count": len(grouped["LOW_SAMPLE_ONLY"]) + len(grouped["DO_NOT_CONCLUDE"]),
        "policy_note": "League tags are observation-only and never auto-change official grade/rules.",
        "safety_guard": {
            "official_grade_unchanged": True,
            "no_auto_exclude": True,
            "no_auto_downgrade": True,
            "pending_excluded_from_denominator": bool(ledger.get("pending_excluded_from_denominator")),
            "ledger_status": ledger_status,
        },
        "baseline_20260531": ledger.get("baseline_20260531") or {},
    }
    return payload


def render_text(payload: dict[str, Any]) -> str:
    def one_line(title: str, rows: list[dict[str, Any]], limit: int = 8) -> list[str]:
        if not rows:
            return [f"- {title}：无"]
        picks = rows[:limit]
        body = "；".join(
            f"{x['league']}({x['hit_count']}/{x['validated_count']}, pending:{x['pending_count']}, {x['action_hint']})"
            for x in picks
        )
        return [f"- {title}：{body}"]

    lines = [
        "V4 联赛长期表现观察层（周报/月报）",
        f"生成时间：{payload.get('generated_at')}",
        f"来源：{payload.get('source_ledger_resolved')}",
        f"趋势锚点：{payload.get('trend_anchor_date')}",
        "",
        "总览",
        f"- 联赛总数：{payload.get('total_leagues')}，已验证：{payload.get('total_validated')}，待赛：{payload.get('total_pending')}",
        "",
        "联赛观察名单",
        *one_line("KEEP", payload.get("keep_leagues") or []),
        *one_line("WATCH", payload.get("watch_leagues") or []),
        *one_line("LOW_TRUST_ALERT", payload.get("low_trust_alert_leagues") or []),
        "",
        "低样本名单",
        *one_line("LOW_SAMPLE_ONLY", payload.get("low_sample_leagues") or []),
        *one_line("DO_NOT_CONCLUDE", payload.get("do_not_conclude_leagues") or []),
        "",
        "Pending-only 名单",
        *one_line("PENDING_ONLY", payload.get("pending_only_leagues") or []),
        "",
        "风险提示",
        "- LOW_TRUST_ALERT 仅观察，不自动排除。",
        "- DO_NOT_CONCLUDE 仅表示样本不足，不是负面判级。",
        "- PENDING_ONLY 不进入命中率分母。",
        "",
        "结论",
        "- 联赛标签只读观察，不自动改规则、不自动改阈值、不自动改 official grade。",
    ]
    return "\n".join(lines)


def resolve_out_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.json_out and args.txt_out:
        return Path(args.json_out), Path(args.txt_out)
    if args.report_type == "monthly":
        key = args.month_key or datetime.now().strftime("%Y%m")
        return (
            MONTHLY_DIR / f"v4_league_watchlist_report_{key}.json",
            MONTHLY_DIR / f"v4_league_watchlist_report_{key}.txt",
        )
    key = args.week_key or "dryrun"
    return (
        WEEKLY_DIR / f"v4_league_watchlist_report_{key}.json",
        WEEKLY_DIR / f"v4_league_watchlist_report_{key}.txt",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-type", choices=["weekly", "monthly", "dryrun"], default="dryrun")
    parser.add_argument("--week-key", default="")
    parser.add_argument("--month-key", default="")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--txt-out", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args.report_type)
    txt = render_text(payload)
    json_out, txt_out = resolve_out_paths(args)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    txt_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_out.write_text(txt, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "report_type": args.report_type,
                "json_out": str(json_out),
                "txt_out": str(txt_out),
                "dry_run": bool(args.dry_run),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
