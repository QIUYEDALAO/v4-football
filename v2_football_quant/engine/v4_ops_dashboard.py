from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from engine.v4_ops_alert import run_alerts
from engine.v4_ops_status import build_status
from engine.v4_validation_progress import build_progress

REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def render(date_str: str) -> Path:
    key = _date_key(date_str)
    status = build_status(key)
    month = key[:6]
    progress = build_progress(month)
    alerts = run_alerts(key)

    rows = []
    for j in status.get("jobs", []):
        rows.append(f"<tr><td>{j['job_name']}</td><td>{j['status']}</td><td>{j.get('last_heartbeat_sec_ago')}</td></tr>")

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>V4 Ops Dashboard {key}</title>
<style>body{{font-family:Arial;padding:20px}} .kpi{{display:inline-block;margin-right:20px}} table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:6px}}</style>
</head><body>
<h1>V4 Ops Control Tower - {key}</h1>
<div class='kpi'>API: {status.get('api_used')}/{status.get('api_limit')}</div>
<div class='kpi'>429: {status.get('http_429')}</div>
<div class='kpi'>Raw: {status.get('raw_rows')}</div>
<div class='kpi'>Normalized: {status.get('normalized_rows')}</div>
<div class='kpi'>Stale jobs: {status.get('stale_jobs')}</div>
<h2>Tasks</h2>
<table><tr><th>Job</th><th>Status</th><th>Heartbeat(s)</th></tr>{''.join(rows)}</table>
<h2>A/B/C</h2>
<pre>{json.dumps(status.get('tier_counts', {}), ensure_ascii=False, indent=2)}</pre>
<h2>Alerts</h2>
<pre>{json.dumps(alerts, ensure_ascii=False, indent=2)}</pre>
<h2>Validation Progress ({month})</h2>
<pre>{json.dumps(progress, ensure_ascii=False, indent=2)}</pre>
</body></html>"""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"v4_ops_dashboard_{key}.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()
    out = render(args.date)
    print(json.dumps({"dashboard_path": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
