#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "daily_reports"
STATUS_DIR = ROOT / "data" / "runtime" / "status"
LOCAL_TZ = timezone(timedelta(hours=8))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.v4_openclaw_brief import build_brief


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _date_key(v: str) -> str:
    return str(v).replace("-", "")


def _content_guard(text: str) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    required = [
        "V4上半场情报",
        "A级强推荐",
        "B级达标推荐",
        "V4最终结论",
        "production_grade_mode=season_aware_rf",
        "official_grade_source=market_adjusted_shadow_grade",
    ]
    for k in required:
        if k not in text:
            blockers.append(f"missing_required:{k}")
    forbidden = [
        "C级上半场主推荐",
        "shadow-only 主推荐",
        "dryrun-only 主推荐",
    ]
    for k in forbidden:
        if k in text:
            blockers.append(f"forbidden_content:{k}")
    return (len(blockers) == 0), blockers


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYYMMDD")
    p.add_argument("--window", default="midday")
    p.add_argument("--production-grade-mode", default="season_aware_rf", choices=["official_legacy", "season_aware_rf"])
    p.add_argument("--real-send", action="store_true", help="must remain false in Codex stage")
    args = p.parse_args()

    key = _date_key(args.date)
    cv_path = STATUS_DIR / f"v4_official_candidate_view_{key}.json"
    cv = _load_json(cv_path, {})

    brief_text = build_brief(
        key,
        production_grade_mode=args.production_grade_mode,
        candidate_view_path=cv_path,
    )
    brief_path = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
    brief_sha256 = hashlib.sha256(brief_text.encode("utf-8")).hexdigest()

    a_count = int(cv.get("A_count", 0) or 0) if isinstance(cv, dict) else 0
    b_count = int(cv.get("B_count", 0) or 0) if isinstance(cv, dict) else 0
    ab_count = a_count + b_count
    mode = str((cv or {}).get("production_grade_mode") or args.production_grade_mode)
    src = str((cv or {}).get("official_grade_source") or "market_adjusted_shadow_grade")

    sent_marker = STATUS_DIR / f"v4_scan_{args.window}_sent_{key}.json"
    dryrun_marker = STATUS_DIR / f"v4_scan_{args.window}_dryrun_{key}.json"
    push_marker = STATUS_DIR / f"v4_scan_{args.window}_push_{key}.json"
    duplicate_sent = sent_marker.exists()

    content_ok, content_blockers = _content_guard(brief_text)

    v4_qq_enabled = False
    no_push = True
    requested_real_send = bool(args.real_send)
    real_send = bool(requested_real_send and v4_qq_enabled and (not no_push) and (not duplicate_sent) and ab_count > 0)

    route = {
        "schema_version": "v4_season_aware_qq_recommendation_dryrun.v1",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "date": key,
        "window": args.window,
        "production_grade_mode": mode,
        "official_grade_source": src,
        "candidate_view_path": str(cv_path),
        "candidate_view_exists": cv_path.exists(),
        "brief_path": str(brief_path),
        "brief_exists": brief_path.exists(),
        "brief_sha256": brief_sha256,
        "A_count": a_count,
        "B_count": b_count,
        "pending_candidates_count": ab_count,
        "main_recommendation_count": ab_count,
        "content_guard_ok": content_ok,
        "content_guard_blockers": content_blockers,
        "route_guard": {
            "official_only": True,
            "allow_grades": ["A", "B"],
            "block_C_main_recommendation": True,
            "block_shadow_only": True,
            "block_dryrun_only": True,
            "brief_path": str(brief_path),
            "brief_sha256": brief_sha256,
            "candidate_count": ab_count,
            "sent_marker_path": str(sent_marker),
            "duplicate_sent_exists": duplicate_sent,
            "allowed_to_send": bool(ab_count > 0 and (not no_push) and v4_qq_enabled and (not duplicate_sent) and content_ok),
        },
        "push_mode": {
            "requested_real_send": requested_real_send,
            "real_send": real_send,
            "dryrun": True,
            "V4_QQ_ENABLED": v4_qq_enabled,
            "no_push": no_push,
            "blocked_reason": (
                "duplicate_sent_marker_exists" if duplicate_sent else
                "V4_QQ_ENABLED_false" if not v4_qq_enabled else
                "no_push_true" if no_push else
                "no_ab_candidates" if ab_count <= 0 else
                "content_guard_failed" if not content_ok else
                "eligible"
            ),
        },
        "markers": {
            "sent_marker_path": str(sent_marker),
            "sent_marker_written": False,
            "dryrun_marker_path": str(dryrun_marker),
            "push_marker_path": str(push_marker),
        },
    }

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    dryrun_marker.write_text(json.dumps(route, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(route, ensure_ascii=False, indent=2))
    blockers = []
    if not cv_path.exists():
        blockers.append("candidate_view_missing")
    if not content_ok:
        blockers.append("content_guard_failed")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
