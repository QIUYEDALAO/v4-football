#!/usr/bin/env python3
"""engine/qqbot_safe_send.py — Safe QQ Outbound 发送脚本
============================================================
职责：唯一允许向报告QQBOT发送固定模板文本的出口。
不调用 LLM / memory_search / agentTurn / announce / wake / main session。

用法：
  # Dry-run（不发送）
  python3 engine/qqbot_safe_send.py --module safe_test \
    --text-file data/dry_runs/templates/safe_qq_test.txt \
    --dry-run

  # 真实发送（需 BOSS 确认）
  python3 engine/qqbot_safe_send.py --module safe_test \
    --text-file data/dry_runs/templates/safe_qq_test.txt \
    --marker data/runtime/status/qq_safe_test_push.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_TZ = timezone(timedelta(hours=8))
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
TARGETS_PATH = STATUS_DIR / "qq_safe_send_targets.json"
DELIVERY_LOG_DIR = STATUS_DIR
GATEWAY_SAFE_SEND_URL = os.environ.get("OPENCLAW_SAFE_SEND_URL", "http://127.0.0.1:18789/api/safe-send")
SAFE_SEND_TOKEN = os.environ.get("OPENCLAW_SAFE_SEND_TOKEN", "")

FORBIDDEN_METHODS = ["announce", "agentTurn", "wake", "main_session", "stdout", "LLM", "memory_search"]
MAX_TEXT_LENGTH = 3000


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def validate_target(target_id: str, module: str) -> dict:
    """Validate target_id against allowlist"""
    targets = _load_json(TARGETS_PATH)
    for label, t in targets.get("targets", {}).items():
        if t.get("target_id") == target_id:
            if not t.get("enabled"):
                return {"ok": False, "reason": "target_disabled"}
            if t.get("activation_status") != "ACTIVE":
                return {"ok": False, "reason": "target_not_active"}
            if module not in t.get("allowed_modules", []):
                return {"ok": False, "reason": f"module_not_allowed: {module}"}
            if t.get("requires_active_thread") and not t.get("thread_id"):
                return {"ok": False, "reason": "no_active_thread"}
            return {"ok": True, "target": t}
    return {"ok": False, "reason": "target_not_in_allowlist"}


def validate_text(text: str, message_hash: str) -> dict:
    """Validate text"""
    if not text or not text.strip():
        return {"ok": False, "reason": "empty_text"}
    if len(text) > MAX_TEXT_LENGTH:
        return {"ok": False, "reason": f"text_too_long: {len(text)}>{MAX_TEXT_LENGTH}"}
    computed = _compute_hash(text)
    if computed != message_hash:
        return {"ok": False, "reason": f"hash_mismatch: expected={message_hash}, computed={computed}"}
    return {"ok": True}


def call_safe_send_endpoint(
    target_id: str, module: str, text: str, message_hash: str, dry_run: bool
) -> dict:
    """Call Gateway safe-send endpoint or file-based delivery"""
    result = {
        "timestamp": datetime.now(LOCAL_TZ).isoformat(),
        "module": module,
        "target_type": "qqbot",
        "target_id": target_id,
        "message_hash": message_hash,
        "text_length": len(text),
        "dry_run": dry_run,
        "used_announce": False,
        "used_agentTurn": False,
        "used_wake": False,
        "used_main_session": False,
        "used_stdout": False,
    }

    if dry_run:
        result["delivery_result"] = "dry_run_pass"
        result["delivery_id"] = f"dry_run_{_compute_hash(text + datetime.now(LOCAL_TZ).isoformat())[:8]}"
        result["sent"] = False
        return {"ok": True, **result}

    # Try Gateway endpoint
    try:
        import urllib.request

        payload = json.dumps({
            "target_type": "qqbot",
            "target_id": target_id,
            "module": module,
            "text": text,
            "message_hash": message_hash,
            "dry_run": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            GATEWAY_SAFE_SEND_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Safe-Send-Token": SAFE_SEND_TOKEN,
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            result["delivery_result"] = body.get("delivery_result", "unknown")
            result["delivery_id"] = body.get("delivery_id", "unknown")
            result["sent"] = body.get("ok", False)
            return result

    except Exception as e:
        # Gateway endpoint not available — write delivery file for pickup
        result["delivery_result"] = "endpoint_unavailable"
        result["error"] = str(e)[:200]
        result["sent"] = False
        result["note"] = "Gateway safe-send endpoint not available. Summary written to file."

        # Write summary file
        summary_path = DELIVERY_LOG_DIR / f"qq_safe_send_pending_{datetime.now(LOCAL_TZ).strftime('%Y%m%d_%H%M%S')}.json"
        summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["summary_file"] = str(summary_path)
        return result


def write_delivery_log(record: dict) -> None:
    """Append to delivery log"""
    date_str = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    log_path = DELIVERY_LOG_DIR / f"qq_delivery_{date_str}.jsonl"
    DELIVERY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_marker(marker_path: str, record: dict) -> None:
    """Write push marker"""
    Path(marker_path).parent.mkdir(parents=True, exist_ok=True)
    with open(marker_path, "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Safe QQ Outbound Sender")
    parser.add_argument("--module", required=True, help="Module name (safe_test, v2_pool, etc.)")
    parser.add_argument("--text-file", help="Path to text file")
    parser.add_argument("--text", help="Text content (alternative to --text-file)")
    parser.add_argument("--target-type", default="qqbot")
    parser.add_argument("--target-id", default="D1BC6F68CBBAC6A473947C53ECB861EC")
    parser.add_argument("--marker", help="Path to write push marker JSON")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, do not send")
    parser.add_argument("--message-hash", help="Pre-computed hash (optional)")
    args = parser.parse_args()

    # Load text
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        print("[SAFE_SEND] ERROR: --text-file or --text required", flush=True)
        sys.exit(1)

    message_hash = args.message_hash or _compute_hash(text)

    # Step 1: Validate target
    target_result = validate_target(args.target_id, args.module)
    if not target_result["ok"]:
        print(f"[SAFE_SEND] ❌ target validation failed: {target_result['reason']}", flush=True)
        # Write failed marker
        if args.marker:
            write_marker(args.marker, {
                "status": "FAILED",
                "reason": target_result["reason"],
                "qq_delivered": False,
                "target_type": args.target_type,
                "target_id": args.target_id,
                "source": "safe_qq_outbound",
                "message_hash": message_hash,
                "failure_stage": "target_validation",
            })
        sys.exit(1)

    # Step 2: Validate text
    text_result = validate_text(text, message_hash)
    if not text_result["ok"]:
        print(f"[SAFE_SEND] ❌ text validation failed: {text_result['reason']}", flush=True)
        sys.exit(1)

    # Step 3: Send
    result = call_safe_send_endpoint(args.target_id, args.module, text, message_hash, args.dry_run)

    # Step 4: Write delivery log
    write_delivery_log(result)

    # Step 5: Write marker
    if args.marker:
        marker_data = {
            "status": "DRY_RUN_PASS" if args.dry_run else ("SAFE_TEST_SENT" if result.get("sent") else "FAILED"),
            "qq_delivered": result.get("sent", False),
            "target_type": args.target_type,
            "target_id": args.target_id,
            "source": "safe_qq_outbound",
            "message_hash": message_hash,
            "delivery_result": result.get("delivery_result"),
            "delivery_id": result.get("delivery_id"),
            "timestamp": result.get("timestamp"),
        }
        write_marker(args.marker, marker_data)

    # Output
    status = "DRY_RUN_PASS" if args.dry_run else ("SUCCESS" if result.get("sent") else "FAILED")
    summary = result.get("summary_file", "")
    print(f"[SAFE_SEND] {status} | module={args.module} | hash={message_hash}", flush=True)
    if summary:
        print(f"[SAFE_SEND] summary file: {summary}", flush=True)
    if args.marker:
        print(f"[SAFE_SEND] marker: {args.marker}", flush=True)

    if not result.get("sent") and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
