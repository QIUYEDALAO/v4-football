#!/usr/bin/env python3
"""Phase V4-C checker: no-push enforcement and route/sent separation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
OUT_PATH = STATUS_DIR / "v4_no_push_enforcement_check.json"

SCAN_FILES = [
    "engine/v4_qq_formatter.py",
    "engine/v4_openclaw_brief.py",
    "engine/v4_scan_and_brief.py",
    "engine/v4_review_with_watchdog.py",
    "engine/v4_review_renderer.py",
    "templates/v4_daily_review_qq_template.md",
    "templates/v4_daily_review_qq_brief.md",
]

SEND_PATTERNS = [
    re.compile(r"openclaw\.message\.send", flags=re.IGNORECASE),
    re.compile(r"safe_outbound_sender", flags=re.IGNORECASE),
    re.compile(r"qqbot_safe_send", flags=re.IGNORECASE),
    re.compile(r"systemEvent", flags=re.IGNORECASE),
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def main() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    warnings: list[str] = []

    send_call_found = False
    unguarded_send_call_found = False
    formatter_only_safe = True

    file_texts: dict[str, str] = {}
    for rel in SCAN_FILES:
        text = _read(BASE_DIR / rel)
        file_texts[rel] = text
        if not text:
            warnings.append(f"file_missing_or_unreadable:{rel}")

    # send-call scanning
    for rel, text in file_texts.items():
        has_send = any(p.search(text) for p in SEND_PATTERNS)
        if has_send:
            send_call_found = True
            has_guard = ("OPENCLAW_NO_PUSH" in text) or ("no_push" in text)
            if not has_guard:
                unguarded_send_call_found = True
                blockers.append(f"unguarded_send_call:{rel}")
            if rel == "engine/v4_qq_formatter.py":
                formatter_only_safe = False
                blockers.append("formatter_calls_send")

    # route/sent separation checks from watchdog wrapper
    wd_text = file_texts.get("engine/v4_review_with_watchdog.py", "")
    route_sent_separated = (
        "v4_review_route_" in wd_text
        and "v4_review_push_" in wd_text
        and "route_allowed" in wd_text
        and "sent_marker_written" in wd_text
    )

    route_allowed_false = '"route_allowed": False' in wd_text
    sent_marker_written_false = '"sent_marker_written": False' in wd_text
    qq_sent_false = '"qq_sent": False' in wd_text

    openclaw_no_push_required = True
    openclaw_no_push_enforced = (
        "OPENCLAW_NO_PUSH" in "\n".join(file_texts.values())
        or '"no_push": _no_push' in wd_text
        or '"no_push": True' in wd_text
    ) and route_allowed_false and sent_marker_written_false and qq_sent_false

    if not route_sent_separated:
        blockers.append("route_sent_not_separated")
    if not formatter_only_safe:
        blockers.append("formatter_only_not_safe")
    if not openclaw_no_push_enforced:
        blockers.append("openclaw_no_push_not_enforced")
    if unguarded_send_call_found:
        blockers.append("unguarded_send_call_found")

    qq_sent = False
    sent_marker_written = False
    route_allowed = False
    production_verified = False
    phase_e_allowed = False

    if production_verified:
        blockers.append("production_verified_true")
    if phase_e_allowed:
        blockers.append("phase_e_allowed_true")

    if blockers:
        check_status = "BLOCKER"
    elif warnings:
        check_status = "WARN"
    else:
        check_status = "PASS"

    out: dict[str, Any] = {
        "schema_version": "v4_no_push_enforcement_check.v1",
        "generated_at": datetime.now(CN).isoformat(),
        "check_status": check_status,
        "send_call_found": send_call_found,
        "unguarded_send_call_found": unguarded_send_call_found,
        "openclaw_no_push_required": openclaw_no_push_required,
        "openclaw_no_push_enforced": openclaw_no_push_enforced,
        "formatter_only_safe": formatter_only_safe,
        "route_sent_separated": route_sent_separated,
        "qq_sent": qq_sent,
        "sent_marker_written": sent_marker_written,
        "route_allowed": route_allowed,
        "production_verified": production_verified,
        "phase_e_allowed": phase_e_allowed,
        "blockers": blockers,
        "warnings": warnings,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if check_status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
