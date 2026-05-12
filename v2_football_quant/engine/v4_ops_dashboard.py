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

ALERT_RULE_CN = {
    "budget_soft": "API用量接近软上限",
    "budget_hard": "API用量接近硬上限",
    "rpm_warn": "每分钟请求速率预警",
    "rpm_critical": "每分钟请求速率严重超限",
    "http_429": "出现429限流错误",
    "cron_duplicate_start": "Cron重复触发（已被锁拦截）",
    "a_strict_zero": "A严格样本为0",
    "b_shadow_low": "B影子样本不足",
    "c_slice_low": "C切片样本不足",
    "ht_ou_identified_low": "HT O/U识别率过低",
    "raw_snapshot_completion_low": "原始快照完整率过低",
    "asian_line_coverage_low": "0.75/1.0/1.25亚洲线覆盖率过低",
    "missing_reason_unknown_high": "缺失原因UNKNOWN占比过高",
    "normalized_zero_minutes": "标准化数据连续为空",
    "normalized_stale_minutes": "标准化数据更新滞后",
    "watchlist_empty": "今日watchlist为空",
}


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def render(date_str: str) -> Path:
    key = _date_key(date_str)
    status = build_status(key)
    resolved_key = str(status.get("resolved_date") or key)
    month = resolved_key[:6]
    progress = build_progress(month)
    alerts = run_alerts(resolved_key)
    alert_rows = []
    for a in alerts.get("alerts", []):
        rule = str(a.get("rule") or "")
        alert_rows.append(
            {
                "级别": a.get("level"),
                "规则": rule,
                "中文说明": ALERT_RULE_CN.get(rule, "未定义规则说明"),
                "消息": a.get("msg"),
            }
        )

    rows = []
    for j in status.get("jobs", []):
        rows.append(f"<tr><td>{j['job_name']}</td><td>{j['status']}</td><td>{j.get('last_heartbeat_sec_ago')}</td></tr>")
    progress_rows = []
    for p in status.get("task_progress", []):
        progress_rows.append(
            f"<tr><td>{p.get('tier')}</td><td>{p.get('planned_tasks')}</td><td>{p.get('actual_rows')} / {p.get('expected_rows')}</td><td>{p.get('progress_pct')}%</td><td>{p.get('failed_tasks')}</td></tr>"
        )

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>V4 运维监控塔 {key}</title>
<style>body{{font-family:Arial;padding:20px}} .kpi{{display:inline-block;margin-right:20px}} table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:6px}}</style>
</head><body>
<h1>V4 运维监控塔 - {resolved_key}</h1>
<div class='kpi'>请求日期: {status.get('requested_date')}</div>
<div class='kpi'>回退启用: {status.get('date_fallback_used')}</div>
<div class='kpi'>API用量: {status.get('api_used')}/{status.get('api_limit')}</div>
<div class='kpi'>429错误: {status.get('http_429')}</div>
<div class='kpi'>原始快照(Raw): {status.get('raw_rows')}</div>
<div class='kpi'>标准化快照(Normalized): {status.get('normalized_rows')}</div>
<div class='kpi'>OK快照命中率: {status.get('ok_snapshot_with_normalized_pct', 0)}%</div>
<div class='kpi'>每个OK快照标准化行数: {status.get('normalized_rows_per_ok_snapshot', 0)}</div>
<div class='kpi'>卡住任务(STALE): {status.get('stale_jobs')}</div>
<div class='kpi'>重复启动拦截: {status.get('duplicate_cron_starts', 0)}</div>
<h2>任务状态</h2>
<table><tr><th>任务名</th><th>状态</th><th>心跳间隔(秒)</th></tr>{''.join(rows)}</table>
<h2>分层进度</h2>
<table><tr><th>层级</th><th>计划场次</th><th>快照行数</th><th>完成率</th><th>失败场次</th></tr>{''.join(progress_rows)}</table>
<h2>A/B/C 分配</h2>
<pre>{json.dumps(status.get('tier_counts', {}), ensure_ascii=False, indent=2)}</pre>
<h2>Universe 过滤</h2>
<pre>{json.dumps({"universe_total": status.get("universe_total", 0), "eligible_live_total": status.get("eligible_live_total", 0), "universe_files_used": status.get("universe_files_used", []), "universe_files_expected": status.get("universe_files_expected", []), "universe_files_missing": status.get("universe_files_missing", []), "excluded_reason_counts": status.get("excluded_reason_counts", {})}, ensure_ascii=False, indent=2)}</pre>
<h2>告警</h2>
<pre>{json.dumps({"date": alerts.get("date"), "alert_count": alerts.get("alert_count"), "alerts": alert_rows, "alerts_path": alerts.get("alerts_path")}, ensure_ascii=False, indent=2)}</pre>
<h2>月底验证进度 ({month})</h2>
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
