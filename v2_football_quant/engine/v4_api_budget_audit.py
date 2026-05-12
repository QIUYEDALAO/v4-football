from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EXEC_DIR = BASE_DIR / "data" / "execution"
AUDIT_DIR = BASE_DIR / "data" / "capture_audit"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def build_audit(date_str: str, hard_limit: int = 75000) -> dict:
    key = _date_key(date_str)
    log_path = EXEC_DIR / f"api_call_log_{key}.jsonl"
    rows = _load_jsonl(log_path)
    task_meta = _load_json(MONITOR_DIR / f"v4_capture_tasks_{key}.json", {})

    by_tier = Counter()
    by_ep = Counter()
    by_minute = defaultdict(int)
    fail = 0
    e429 = 0

    for r in rows:
        by_tier[str(r.get("capture_tier") or "UNKNOWN")] += 1
        by_ep[str(r.get("endpoint_type") or "unknown")] += 1
        ts = str(r.get("ts") or "")
        mm = ts[:16]
        by_minute[mm] += 1
        if not r.get("ok", True):
            fail += 1
        if int(r.get("http_status") or 0) == 429:
            e429 += 1

    used = len(rows)
    remaining = max(0, hard_limit - used)
    peak_per_min = max(by_minute.values()) if by_minute else 0

    out = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "daily_calls_used": used,
        "daily_calls_remaining": remaining,
        "hard_limit": hard_limit,
        "peak_requests_per_minute": peak_per_min,
        "calls_by_tier": dict(by_tier),
        "calls_by_endpoint": dict(by_ep),
        "failed_requests": fail,
        "http_429_count": e429,
        "scheduler_tier_counts": (task_meta.get("tier_counts") or {}),
        "task_file": str(MONITOR_DIR / f"v4_capture_tasks_{key}.json"),
        "api_call_log": str(log_path),
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / f"v4_api_budget_audit_{key}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["audit_path"] = str(out_path)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--hard-limit", type=int, default=75000)
    args = parser.parse_args()

    result = build_audit(args.date, hard_limit=args.hard_limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
