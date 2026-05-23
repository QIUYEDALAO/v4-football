#!/usr/bin/env python3
"""Generate the V3/V4-only Intel Ops console with source-date and validation guards.

Report-only generator. It does not run capture, push messages, enable cron,
publish cloud bundles, change strategy outputs, or read retired current sources.
"""

from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

try:
    from v3v4_dashboard_brief_resolver import resolve as resolve_brief
    from v3v4_dashboard_validation_resolver import resolve as resolve_validation
except Exception:  # pragma: no cover - fallback for static inspection
    resolve_brief = None
    resolve_validation = None

MODULE = Path(__file__).resolve().parents[1]
STATUS_DIR = MODULE / "data" / "runtime" / "status"
DASHBOARD_DIR = MODULE / "data" / "runtime" / "dashboard"
TEAM_CN_MAP = MODULE / "engine" / "team_cn_map.json"
CN_TZ = timezone(timedelta(hours=8))
DATE_KEY = "20260523"
CURRENT_LOCAL_DATE = DATE_KEY


def _now() -> str:
    return datetime.now(CN_TZ).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest(pattern: str) -> Path | None:
    files = sorted(STATUS_DIR.glob(pattern))
    return files[-1] if files else None


def _latest_candidate_view(date_key: str = DATE_KEY) -> tuple[dict[str, Any], Path | None]:
    # Prefer the formal daily brief resolver output for the requested date.
    candidate_path = STATUS_DIR / f"v3v4_dashboard_candidate_view_{date_key}.json"
    if not candidate_path.exists() and resolve_brief is not None:
        resolve_brief(date_key, write=True)
    if candidate_path.exists():
        return _load_json(candidate_path), candidate_path
    path = _latest("intel_desk_v4_candidate_view_*.json")
    return (_load_json(path), path) if path else ({}, None)


def _latest_v3_status() -> tuple[dict[str, Any], Path | None]:
    files: list[Path] = []
    for pattern in ["v3_perception_gap_status_*.json", "v3_readiness_status_*.json", "v3_worldcup_status_*.json"]:
        files.extend(STATUS_DIR.glob(pattern))
    files = sorted(files)
    path = files[-1] if files else None
    return (_load_json(path), path) if path else ({}, None)


def _source_hash(path: Path | None, data: dict[str, Any]) -> str:
    if path and path.exists():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _sha(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_api_status(date_key: str = DATE_KEY) -> dict[str, Any]:
    patterns = [
        "v4_api_key_local_injection_and_preflight_verify_*.json",
        "v4_api_preflight_*.json",
        "v4_api_credential_preflight_and_403_circuit_breaker_*.json",
    ]
    for pattern in patterns:
        candidates = sorted(STATUS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            continue
        data = _load_json(candidates[0])
        if data:
            if "preflight_http_status" in data and "http_status" not in data:
                data["http_status"] = data.get("preflight_http_status")
            data["api_status_source"] = str(candidates[0].relative_to(MODULE))
            return data
    return {}


def _counts(data: dict[str, Any]) -> dict[str, int]:
    return {
        "A": int(data.get("A_count", 0) or 0),
        "B": int(data.get("B_count", 0) or 0),
        "C": int(data.get("C_count", 0) or 0),
        "SKIP": int(data.get("SKIP_count", 0) or 0),
    }


def _candidate_list(data: dict[str, Any], grade: str) -> list[dict[str, Any]]:
    if grade == "A":
        explicit = data.get("A_candidates")
        if isinstance(explicit, list):
            return explicit
        single = data.get("A_candidate")
        return [single] if isinstance(single, dict) and single else []
    value = data.get(f"{grade}_candidates")
    return value if isinstance(value, list) else []


def _h(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _load_team_map() -> dict[str, str]:
    raw = _load_json(TEAM_CN_MAP)
    exact = raw.get("exact") if isinstance(raw, dict) else {}
    return exact if isinstance(exact, dict) else {}


TEAM_MAP = _load_team_map()


def _cn_name(name: Any) -> tuple[str, str | None]:
    original = str(name or "UNKNOWN")
    mapped = TEAM_MAP.get(original) or TEAM_MAP.get(original.strip())
    return (mapped or original, original if mapped and mapped != original else None)


def _script(item: dict[str, Any]) -> str:
    return str(item.get("script_type") or item.get("best_focus") or item.get("market_type") or "待识别")


def _time_bins(item: dict[str, Any]) -> str:
    if item.get("distribution_text"):
        return str(item["distribution_text"])
    dist = item.get("goal_time_distribution") or {}
    if isinstance(dist, dict) and dist.get("available"):
        return " | ".join(
            f"{label} {int(float(dist.get(key, 0) or 0) * 100)}%"
            for key, label in [("m0_15", "0-15m"), ("m16_30", "16-30m"), ("m31_45", "31-45m")]
        )
    return "time_bins 待补齐"


def resolve_source_date(data: dict[str, Any], candidate_path: Path | None, *, write: bool = True) -> dict[str, Any]:
    generated_at = str(data.get("generated_at") or "")
    generated_date = generated_at[:10].replace("-", "") if generated_at else None
    scan_date = str(data.get("scan_date") or (candidate_path.stem[-8:] if candidate_path else "unknown"))
    is_today = scan_date == CURRENT_LOCAL_DATE
    display_label = "今日候选" if is_today else f"最近候选 / 数据日期 {scan_date}"
    result = {
        "schema_version": "v3v4_dashboard_source_date_resolution.v1",
        "phase": "V3V4-DASHBOARD-BRIEF-VALIDATION-AUTO-REFRESH-20260523",
        "generated_at": _now(),
        "generated_date": generated_date,
        "scan_date": scan_date,
        "current_local_date": CURRENT_LOCAL_DATE,
        "source_window": data.get("source_window", "unknown"),
        "is_today_source": is_today,
        "source_date_mismatch": not is_today,
        "display_label": display_label,
        "candidate_model_path": str(candidate_path.relative_to(MODULE)) if candidate_path else None,
        "candidate_model_sha256": _sha(candidate_path),
        "daily_refresh_must_not_fabricate_today": not is_today,
    }
    if write:
        (STATUS_DIR / f"v3v4_dashboard_source_date_resolution_{DATE_KEY}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def _fmt_rate(rate: Any, resolved: Any = None) -> str:
    if rate is None:
        return "N/A"
    try:
        if resolved is not None and int(resolved or 0) <= 0:
            return "N/A"
        return f"{float(rate) * 100:.1f}%"
    except Exception:
        return "N/A"


def _metric(src: dict[str, Any], *, observation: bool = False) -> dict[str, Any]:
    rate = src.get("observation_hit_rate_resolved_only") if observation else src.get("hit_rate_resolved_only")
    if rate is None:
        rate = src.get("observation_hit_rate") if observation else src.get("hit_rate")
    resolved = src.get("resolved_count")
    if resolved is None:
        resolved = int(src.get("hit", 0) or 0) + int(src.get("miss", 0) or 0)
    return {
        "count": int(src.get("count", 0) or 0),
        "hit": int(src.get("hit", 0) or 0),
        "miss": int(src.get("miss", 0) or 0),
        "unknown": int(src.get("unknown", 0) or 0),
        "settled": int(resolved or 0),
        "hit_rate": rate,
        "display_rate": _fmt_rate(rate, resolved),
    }


def build_validation_summary(*, write: bool = True, date_key: str = DATE_KEY) -> dict[str, Any]:
    if resolve_validation is not None:
        return resolve_validation(date_key, write=write)
    y_path = _latest("v4_yesterday_validation_rebuilt_*.json") or _latest("v4_yesterday_validation_*.json")
    r_path = _latest("v4_rolling_validation_rebuilt_*.json") or _latest("v4_rolling_validation_split_*.json")
    raw_path = _latest("v4_validation_raw_records_*.json")
    y = _load_json(y_path) if y_path else {}
    r = _load_json(r_path) if r_path else {}
    official_y = y.get("official", {}) if isinstance(y.get("official"), dict) else {}
    obs_y = y.get("observation", {}) if isinstance(y.get("observation"), dict) else {}
    windows = r.get("windows", {}) if isinstance(r.get("windows"), dict) else {}
    last7 = windows.get("last_7d", {}) if isinstance(windows.get("last_7d"), dict) else {}
    cumulative = windows.get("cumulative") or windows.get("last_30d") or last7
    if not isinstance(cumulative, dict):
        cumulative = {}
    def pack(src: dict[str, Any]) -> dict[str, Any]:
        return {
            "A": _metric(src.get("A", {}) if isinstance(src.get("A"), dict) else {}),
            "B": _metric(src.get("B", {}) if isinstance(src.get("B"), dict) else {}),
            "A_plus_B": _metric(src.get("A_plus_B", {}) if isinstance(src.get("A_plus_B"), dict) else {}),
            "C_observation": _metric(src.get("C", {}) if isinstance(src.get("C"), dict) else {}, observation=True),
        }
    source_files = [str(p.relative_to(MODULE)) for p in [y_path, r_path, raw_path] if p]
    source_hash = hashlib.sha256("|".join(filter(None, [_sha(y_path), _sha(r_path), _sha(raw_path)])).encode()).hexdigest()
    result = {
        "schema_version": "v3v4_validation_summary.v1",
        "phase": "V3V4-DASHBOARD-BRIEF-VALIDATION-AUTO-REFRESH-20260523",
        "generated_at": _now(),
        "yesterday": {
            "label": f"最近正式昨日验证产物 / 数据日期 {y.get('date', 'unknown')}",
            "A": _metric(official_y.get("A", {}) if isinstance(official_y.get("A"), dict) else {}),
            "B": _metric(official_y.get("B", {}) if isinstance(official_y.get("B"), dict) else {}),
            "A_plus_B": _metric(official_y.get("A_plus_B", {}) if isinstance(official_y.get("A_plus_B"), dict) else {}),
            "C_observation": _metric(obs_y.get("C", {}) if isinstance(obs_y.get("C"), dict) else {}, observation=True),
        },
        "last_7d": pack(last7),
        "cumulative": pack(cumulative),
        "source_files": source_files,
        "source_hash": source_hash,
        "v3_status": "N/A: V3 暂无结算样本 / 战备预留",
        "v4_status": "source_files_present" if source_files else "validation_data_not_ready",
        "unknown_policy": "unknown 显示 N/A 或 unknown_count；样本不足不得显示 0%",
        "c_observation_only": True,
        "no_free_recompute": True,
        "c_not_in_formal_ab": True,
    }
    if write:
        (STATUS_DIR / f"v3v4_validation_summary_{DATE_KEY}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def _metric_line(label: str, metric: dict[str, Any]) -> str:
    display_rate = str(metric.get("display_rate", "N/A") or "N/A")
    settled = int(metric.get("settled", 0) or 0)
    if settled <= 0 or display_rate == "N/A":
        value = "N/A"
    else:
        value = f"{metric.get('hit', 0)}/{settled} · {display_rate}"
    return f"<div class='validation-metric validation-row-{_h(label).replace('+','plus')}'><span>{_h(label)}</span><b>{_h(value)}</b></div>"


def _unknown_count(block: dict[str, Any]) -> int:
    total = 0
    for key in ["A", "B", "A_plus_B"]:
        value = block.get(key, {}) if isinstance(block.get(key), dict) else {}
        total += int(value.get("unknown", 0) or 0)
    return total


def _script_metric_line(label: str, metric: dict[str, Any]) -> str:
    display = str(metric.get("display_compact") or metric.get("display_rate") or "N/A")
    if display == "N/A" or int(metric.get("script_denominator", 0) or 0) <= 0:
        value = "N/A"
    else:
        value = display
    return f"<span class='script-validation-chip script-validation-{_h(label).replace('+','plus')}'><i>{_h(label)}</i><b>{_h(value)}</b></span>"


def _script_detail_line(label: str, metric: dict[str, Any]) -> str:
    display = str(metric.get("display_compact") or "N/A")
    unknown = int(metric.get("script_unknown", 0) or 0)
    return f"<br>{_h(label)}：{_h(display)} · SCRIPT_UNKNOWN={unknown}"


def _validation_section(summary: dict[str, Any]) -> str:
    active = summary.get("dashboard_active", {}) if isinstance(summary.get("dashboard_active"), dict) else {}
    y = active.get("yesterday", {}) if isinstance(active.get("yesterday"), dict) else summary.get("yesterday", {})
    cu = active.get("cumulative", {}) if isinstance(active.get("cumulative"), dict) else summary.get("cumulative", {})
    script_validation = summary.get("script_validation", {}) if isinstance(summary.get("script_validation"), dict) else {}
    script_y = script_validation.get("yesterday", {}) if isinstance(script_validation.get("yesterday"), dict) else {}
    script_cu = script_validation.get("cumulative", {}) if isinstance(script_validation.get("cumulative"), dict) else {}
    script_y_ab = script_y.get("AB", {}) if isinstance(script_y.get("AB"), dict) else {}
    script_cu_a = script_cu.get("A", {}) if isinstance(script_cu.get("A"), dict) else {}
    script_cu_b = script_cu.get("B", {}) if isinstance(script_cu.get("B"), dict) else {}
    script_cu_ab = script_cu.get("AB", {}) if isinstance(script_cu.get("AB"), dict) else {}
    source_files = "<br>".join(_h(x) for x in summary.get("source_files", [])) or "N/A"
    raw = summary.get("raw_audit", {}) if isinstance(summary.get("raw_audit"), dict) else {}
    active_metrics = [
        y.get("A", {}) if isinstance(y.get("A"), dict) else {},
        y.get("B", {}) if isinstance(y.get("B"), dict) else {},
        y.get("A_plus_B", {}) if isinstance(y.get("A_plus_B"), dict) else {},
        cu.get("A", {}) if isinstance(cu.get("A"), dict) else {},
        cu.get("B", {}) if isinstance(cu.get("B"), dict) else {},
        cu.get("A_plus_B", {}) if isinstance(cu.get("A_plus_B"), dict) else {},
    ]
    has_visible_data = any(int(m.get("settled", 0) or 0) > 0 and str(m.get("display_rate", "N/A")) != "N/A" for m in active_metrics)
    source_status = str(summary.get("validation_source_status") or "")
    api_disabled = bool(summary.get("old_summary_marked_stale")) or "API" in source_status or "NO_API" in source_status
    y_has_visible_data = any(
        int(m.get("settled", 0) or 0) > 0 and str(m.get("display_rate", "N/A")) != "N/A"
        for m in [
            y.get("A", {}) if isinstance(y.get("A"), dict) else {},
            y.get("B", {}) if isinstance(y.get("B"), dict) else {},
            y.get("A_plus_B", {}) if isinstance(y.get("A_plus_B"), dict) else {},
        ]
    )
    cu_has_visible_data = any(
        int(m.get("settled", 0) or 0) > 0 and str(m.get("display_rate", "N/A")) != "N/A"
        for m in [
            cu.get("A", {}) if isinstance(cu.get("A"), dict) else {},
            cu.get("B", {}) if isinstance(cu.get("B"), dict) else {},
            cu.get("A_plus_B", {}) if isinstance(cu.get("A_plus_B"), dict) else {},
        ]
    )
    if cu_has_visible_data and not y_has_visible_data:
        reason = "累计验证已从本地 match_date attribution 历史恢复；昨日暂无可信已结算样本，显示 N/A。"
    elif has_visible_data:
        reason = "验证数据已加载：昨日与累计均来自正式 V4 attribution / validation / review。"
    elif api_disabled:
        reason = "赛果数据未就绪：API disabled / 修复后等待 match_date 正式 attribution，未伪造命中率。"
    else:
        reason = "样本不足或等待赛果结算：当前显示 N/A，未伪造命中率。"
    script_ready = script_validation.get("status") == "SCRIPT_VALIDATION_READY"
    script_main = str(script_cu_ab.get("display_compact") or "N/A")
    script_reason = "赛后事件数据未就绪 / API disabled / 无可信事件时间" if not script_ready or int(script_cu_ab.get("script_denominator", 0) or 0) <= 0 else "走势吻合率，不影响 A/B 结果命中率。"
    script_sources = "<br>".join(_h(x) for x in script_validation.get("source_files", [])) or "N/A"
    return f"""
<section class="panel validation-panel compact-validation two-column-validation-card">
  <h2>V3/V4 比赛验证</h2>
  <p class="hint">只展示昨日验证与累计验证；数据来自正式 V4 attribution / validation / review，不从 brief 反推命中率。</p>
  <div class="validation-grid">
    <div class="validation-col validation-yesterday"><h3>昨日验证</h3>{_metric_line('A', y.get('A', {}))}{_metric_line('B', y.get('B', {}))}{_metric_line('A+B', y.get('A_plus_B', {}))}</div>
    <div class="validation-col validation-cumulative"><h3>累计验证</h3>{_metric_line('A', cu.get('A', {}))}{_metric_line('B', cu.get('B', {}))}{_metric_line('A+B', cu.get('A_plus_B', {}))}</div>
  </div>
  <div class="script-validation-lite">
    <span class="script-lite-title">剧本验证（辅助）</span>
    <b>累计 A+B：{_h(script_main)}</b>
    <em>走势吻合率，不影响 A/B 结果命中率</em>
  </div>
  <p class="hint script-validation-reason">{_h(script_reason)}</p>
  <p class="hint validation-empty-reason">{_h(reason)}</p>
  <p class="hint v3-validation-row">V3：战备预留 / N/A</p>
  <details class="validation-audit"><summary><span>展开：验证审计</span><b>audit</b></summary><p class="audit-code">source_files=<br>{source_files}<br>unknown_count_yesterday={_unknown_count(y)}<br>unknown_count_cumulative={_unknown_count(cu)}<br>latest_validation_date={_h(summary.get('latest_validation_date', 'unknown'))}<br>api_enabled={str(not api_disabled).lower()}<br>brief_used_for_hit_rate={str(summary.get('brief_used_for_hit_rate') is True).lower()}<br>C_observation_deprecated={str(raw.get('c_observation_deprecated', True)).lower()}<br>last_7d_removed=true</p></details>
  <details class="validation-audit script-validation-audit"><summary><span>展开：剧本验证明细</span><b>script</b></summary><p class="audit-code">昨日：{_h(script_y_ab.get('display_compact') or 'N/A')}（暂无可信已结算样本）{_script_detail_line('A', script_cu_a)}{_script_detail_line('B', script_cu_b)}{_script_detail_line('A+B', script_cu_ab)}<br>SCRIPT_UNKNOWN：{int(script_cu_ab.get('script_unknown', 0) or 0)}，不进分母<br>数据源：正式 attribution 事件时间<br>script_source_files=<br>{script_sources}<br>brief_used_for_script_validation={str(script_validation.get('brief_used_for_script_validation') is True).lower()}<br>match_date_used=true<br>scan_date_used={str(script_validation.get('scan_date_used') is True).lower()}<br>C_excluded={str(script_validation.get('c_included') is not True).lower()}<br>SKIP_excluded={str(script_validation.get('skip_included') is not True).lower()}</p></details>
</section>"""


def _clean_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "--", "None", "null", "N/A"}:
        return None
    return text


def _ht_display(item: dict[str, Any]) -> str | None:
    score = _clean_value(item.get("ht_score"))
    if score and score.replace('.', '', 1).isdigit():
        return f"HT{score.rstrip('0').rstrip('.') if '.' in score else score}"
    if score:
        return f"HT{score}"
    # ht_rate is audit-only for current cards; do not render it as HT percentage.
    return None


def _card(item: dict[str, Any], grade: str) -> str:
    if item.get("home_cn"):
        home_cn, home_en = str(item.get("home_cn")), item.get("home_en")
    else:
        home_cn, home_en = _cn_name(item.get("home") or item.get("home_team"))
    if item.get("away_cn"):
        away_cn, away_en = str(item.get("away_cn")), item.get("away_en")
    else:
        away_cn, away_en = _cn_name(item.get("away") or item.get("away_team"))
    english = ""
    if home_en or away_en:
        english = f"<div class='english-line'>EN: {_h(home_en or home_cn)} vs {_h(away_en or away_cn)}</div>"
    league = _h(item.get("league") or "UNKNOWN")
    kickoff = _h(item.get("kickoff_display") or item.get("kickoff_time") or "TBD")
    missing_fields: list[str] = []
    segments: list[str] = []
    ht = _ht_display(item)
    if ht:
        segments.append(_h(ht))
    else:
        missing_fields.append("ht_score")
    strength = _clean_value(item.get("strength_pct") or item.get("best_score"))
    if strength:
        segments.append(f"强度 {_h(strength)}")
    else:
        missing_fields.append("strength")
    goals = _clean_value(item.get("expected_goals"))
    if goals:
        segments.append(f"球数 {_h(goals)}")
    else:
        missing_fields.append("expected_goals")
    script = _clean_value(_script(item))
    if script and script != "待识别":
        segments.append(f"<span class='script-label'>剧本：</span><span class='script-value'>{_h(script)}</span>")
    else:
        missing_fields.append("script_type")
    r3 = " · ".join(segments) if segments else "主信息字段待正式源补齐"
    bins = _h(_time_bins(item))
    missing = f"<div class='missing-fields'>missing_fields: {_h(','.join(missing_fields))}</div>" if missing_fields else ""
    return f"""
<article class="candidate-card grade-{grade}" data-grade="{grade}">
  <div class="card-r1"><span>{kickoff}</span><span>{league}</span><b class="grade-badge grade-badge-{grade}">{grade}</b></div>
  <div class="match-line">{_h(home_cn)} <span>vs</span> {_h(away_cn)}</div>
  <div class="card-r3">{r3}</div>
  <div class="time-bins">{bins}</div>
  {english}{missing}
</article>"""


def _empty_card(grade: str) -> str:
    text = "暂无正式候选"
    return f"<article class='candidate-card empty grade-{grade}' data-grade='{grade}'><div class='match-line'>{text}</div><div class='card-r3'>等待下一次 V4 情报刷新</div></article>"


def _group(title: str, grade: str, items: list[dict[str, Any]], open_group: bool, note: str = "") -> str:
    cards = "\n".join(_card(item, grade) for item in items) if items else _empty_card(grade)
    open_attr = " open" if open_group else ""
    note_html = f"<p class='group-note'>{_h(note)}</p>" if note else ""
    return f"""
<details class="candidate-group group-{grade}"{open_attr}>
  <summary><span>{_h(title)}</span><b>{len(items)} 场</b></summary>
  {note_html}
  <div class="candidate-list">{cards}</div>
  <details class="lineage"><summary>技术血缘折叠区</summary><p>英文队名、source_hash、time_bins、taxonomy 仅作审计，不改变 A/B/SKIP active 展示。</p></details>
</details>"""


def _v3_panel(v3: dict[str, Any], source: Path | None) -> str:
    if not v3:
        return """
<section class="panel v3-panel">
  <h2>V3 战备窗口</h2>
  <div class="row"><span>状态</span><b>预留</b></div>
  <div class="row"><span>Perception Gap</span><b>待生成</b></div>
  <div class="row"><span>Watchlist</span><b>待生成</b></div>
  <p class="hint">当前不参与 V4 A/B 正式候选。</p>
</section>"""
    return f"""
<section class="panel v3-panel">
  <h2>V3 战备窗口</h2>
  <div class="row"><span>V3 status</span><b>{_h(v3.get('status', 'READY_RESERVED'))}</b></div>
  <div class="row"><span>perception_gap_count</span><b>{_h(v3.get('perception_gap_count', 0))}</b></div>
  <div class="row"><span>watchlist_count</span><b>{_h(v3.get('watchlist_count', 0))}</b></div>
  <div class="row"><span>last_update</span><b>{_h(v3.get('last_update', source.name if source else 'unknown'))}</b></div>
  <div class="row"><span>data_source</span><b>{_h(source.relative_to(MODULE) if source else 'reserved')}</b></div>
  <p class="hint">当前不参与 V4 A/B 正式候选。</p>
</section>"""


def render_html(data: dict[str, Any], candidate_path: Path | None, v3: dict[str, Any], v3_path: Path | None, validation: dict[str, Any] | None = None, source_resolution: dict[str, Any] | None = None) -> str:
    validation = validation or build_validation_summary(write=False, date_key=DATE_KEY)
    source_resolution = source_resolution or resolve_source_date(data, candidate_path, write=False)
    counts = _counts(data)
    formal_count = int(data.get("formal_recommendation_count", counts["A"] + counts["B"]) or 0)
    scan_total = counts["A"] + counts["B"] + counts["C"] + counts["SKIP"]
    source_window = _h(data.get("source_window", "unknown"))
    scan_date = _h(source_resolution.get("scan_date", "unknown"))
    display_label = _h(source_resolution.get("display_label", "最近候选"))
    api_status_marker = _latest_api_status(DATE_KEY)
    api_safe = api_status_marker.get("safe_to_scan")
    api_status = str(api_status_marker.get("api_status") or "API_UNKNOWN")
    api_last_good = "last_good preserved"
    if api_safe is False:
        if api_status == "API_FORBIDDEN_NOT_SUBSCRIBED":
            data_status = "API credential blocked"
        elif api_status == "API_RATE_LIMITED":
            data_status = "API rate limited"
        else:
            data_status = "API disabled"
        data_status_class = "danger"
        data_notice = "<div class='notice'>API数据源异常，保留 last_good；不显示今日正常更新，不伪造候选。</div>"
    else:
        data_status = "今日已更新" if source_resolution.get("is_today_source") else "最近数据"
        data_status_class = "ok" if source_resolution.get("is_today_source") else "warn"
        data_notice = "" if source_resolution.get("is_today_source") else f"<div class='notice'>今日数据未就绪，当前展示最近采集日：{scan_date}</div>"
    source_hash = _source_hash(candidate_path, data)
    generated_at = datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    a_items = _candidate_list(data, "A")
    b_items = _candidate_list(data, "B")
    blockers = 0
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>情报决策总台 — V3/V4</title>
<style>
:root{{--bg:#07101d;--panel:#101b2c;--panel2:#15243a;--ink:#eef5ff;--muted:#91a2b8;--line:#26384f;--blue:#58b7ff;--green:#47d18c;--amber:#e7b84e;--red:#ff6b72;--violet:#a9a1ff}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 15% 0%,#173558 0,#07101d 34%,#050912 100%);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:16px;max-width:1060px;margin-inline:auto;line-height:1.42}}
header{{padding:10px 2px 16px}}h1{{margin:0;font-size:26px;letter-spacing:.02em}}.sub{{color:var(--muted);font-size:13px;margin-top:5px}}.notice{{background:rgba(231,184,78,.13);border:1px solid rgba(231,184,78,.42);border-radius:14px;padding:10px 12px;margin:4px 0 14px;color:#ffe3a2;font-weight:700}}.kpi-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:8px 0 14px}}.kpi{{background:linear-gradient(155deg,var(--panel),#0c1727);border:1px solid var(--line);border-radius:16px;padding:12px;min-height:94px;box-shadow:0 12px 30px rgba(0,0,0,.22)}}.kpi .label{{color:var(--muted);font-size:12px}}.kpi .value{{font-size:22px;font-weight:800;margin-top:8px}}.kpi .foot{{font-size:12px;color:var(--muted);margin-top:4px}}.layout{{display:grid;grid-template-columns:1.25fr .75fr;gap:12px}}.panel,.candidate-group{{background:rgba(16,27,44,.92);border:1px solid var(--line);border-radius:16px;padding:14px;margin-bottom:12px;box-shadow:0 10px 28px rgba(0,0,0,.18)}}h2{{font-size:16px;margin:0 0 10px;color:var(--blue)}}h3{{font-size:14px;margin:10px 0 8px;color:#cfe8ff}}.row{{display:flex;justify-content:space-between;gap:16px;border-top:1px solid rgba(255,255,255,.07);padding:8px 0}}.row:first-of-type{{border-top:0}}.row span{{color:var(--muted)}}.ok{{color:var(--green)}}.warn{{color:var(--amber)}}.danger{{color:var(--red)}}summary{{cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:12px;font-weight:800}}details>summary::-webkit-details-marker{{display:none}}.group-note,.hint{{color:var(--muted);font-size:13px;margin:8px 0}}.candidate-list{{display:grid;gap:9px;margin-top:10px}}.candidate-card{{background:linear-gradient(155deg,var(--panel2),#0b1422);border:1px solid rgba(255,255,255,.08);border-left:4px solid var(--line);border-radius:14px;padding:12px}}.candidate-card.grade-A{{border-left-color:var(--green)}}.candidate-card.grade-B{{border-left-color:var(--blue)}}.candidate-card.grade-C{{border-left-color:var(--amber)}}.card-r1{{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}}.card-r1 span:nth-child(2){{flex:1}}.grade-badge{{border-radius:999px;padding:3px 9px;font-size:12px;color:#08111f}}.grade-badge-A{{background:var(--green)}}.grade-badge-B{{background:var(--blue)}}.grade-badge-C{{background:var(--amber)}}.match-line{{font-size:17px;font-weight:800;margin-top:7px}}.match-line span{{font-weight:500;color:var(--muted);font-size:13px}}.card-r3,.time-bins,.english-line,.missing-fields{{font-size:13px;color:var(--muted);margin-top:6px}}.script-label{{color:var(--muted)}}.script-value{{color:var(--amber);font-weight:800}}.missing-fields{{display:none}}.english-line{{display:none}}.lineage{{margin-top:10px;border-top:1px dashed rgba(255,255,255,.12);padding-top:8px;color:var(--muted);font-size:12px}}.validation-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.validation-col{{border-top:1px solid rgba(255,255,255,.08);padding-top:6px}}.validation-metric{{display:grid;grid-template-columns:38px 1fr;gap:5px;padding:4px 0;font-size:13px;align-items:center}}.validation-metric span{{color:var(--muted);font-style:normal}}.validation-metric b{{font-size:13px;white-space:nowrap}}.script-validation-lite{{margin-top:10px;padding:8px 10px;border:1px solid rgba(255,255,255,.10);border-radius:12px;background:rgba(255,255,255,.035);display:grid;grid-template-columns:auto 1fr;gap:4px 8px;align-items:center;font-size:12px}}.script-validation-lite .script-lite-title{{color:var(--muted);font-weight:800}}.script-validation-lite>b{{color:#f2d27a;font-weight:800}}.script-validation-lite>em{{grid-column:1/-1;color:var(--muted);font-style:normal}}.script-validation-chip{{display:inline-flex;gap:4px;align-items:center;border:1px solid rgba(255,255,255,.09);border-radius:999px;padding:3px 7px;background:rgba(255,255,255,.04)}}.script-validation-chip i{{font-style:normal;color:var(--muted)}}.script-validation-chip b{{color:var(--amber);font-weight:800}}.compact-validation{{padding-bottom:10px}}.validation-audit{{margin-top:8px;border-top:1px dashed rgba(255,255,255,.12);padding-top:8px}}.next-list{{margin:0;padding-left:18px;color:var(--muted)}}.audit-code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted);word-break:break-all}}@media(max-width:760px){{body{{padding:12px}}.kpi-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.layout{{grid-template-columns:1fr}}h1{{font-size:23px}}.kpi .value{{font-size:20px}}.validation-metric{{grid-template-columns:38px 1fr}}}}
</style>
</head>
<body>
<header>
  <h1>情报决策总台 — V3/V4</h1>
  <div class="sub">generated={generated_at} · source_window={source_window} · no capture · no push · no cloud publish</div>
</header>
{data_notice}
<section class="kpi-grid" aria-label="top status cards">
  <div class="kpi"><div class="label">数据状态</div><div class="value {data_status_class}">{data_status}</div><div class="foot">{display_label} · {api_last_good}</div></div>
  <div class="kpi"><div class="label">候选结构</div><div class="value">A{counts['A']} / B{counts['B']}</div><div class="foot">SKIP {counts['SKIP']}</div></div>
  <div class="kpi"><div class="label">复盘状态</div><div class="value warn">REPORT_ONLY</div><div class="foot">等待赛果 / 可复盘</div></div>
  <div class="kpi"><div class="label">阻断</div><div class="value {('ok' if blockers == 0 else 'danger')}">{blockers}</div><div class="foot">active blocker count</div></div>
</section>
<div class="layout">
<main>
{_validation_section(validation)}
<section class="panel">
  <h2>V4 情报状态</h2>
  <div class="row"><span>正式候选</span><b>{counts['A'] + counts['B']} 场</b></div>
  <div class="row"><span>A/B/SKIP</span><b>A{counts['A']} / B{counts['B']} / SKIP{counts['SKIP']}</b></div>
  <div class="row"><span>review_mode</span><b>REPORT_ONLY</b></div>
  <div class="row"><span>全量扫描场次</span><b>{scan_total}</b></div>
  <div class="row"><span>采集日期 / 窗口</span><b>{scan_date} / {source_window}</b></div>
</section>
<section class="panel candidate-panel">
  <h2>候选列表</h2>
  <p class="hint">{display_label}。候选列表只展示 A/B 正式候选；SKIP 仅作为系统状态。</p>
  {_group('A级候选', 'A', a_items, True)}
  {_group('B级候选', 'B', b_items, True)}
</section>
</main>
<aside>
{_v3_panel(v3, v3_path)}
<section class="panel safety-panel">
  <h2>系统安全</h2>
  <div class="row"><span>V3 active</span><b>战备中 / 预留</b></div>
  <div class="row"><span>V4 review</span><b>REPORT_ONLY</b></div>
  <div class="row"><span>legacy modules</span><b>禁用</b></div>
  <div class="row"><span>QQ推送</span><b>关闭</b></div>
  <div class="row"><span>capture/cloud</span><b>关闭</b></div>
  <div class="row"><span>cron</span><b>未启用 / status-only</b></div>
</section>
<section class="panel">
  <h2>下一动作</h2>
  <ul class="next-list"><li>等待 BOSS 验收 UI。</li><li>每日刷新仅使用 V3/V4 active source。</li><li>任何推送/cron/cloud 均需单独授权。</li></ul>
</section>
<details class="panel"><summary><span>系统审计折叠区</span><b>展开</b></summary><p class="audit-code">source_hash={source_hash}<br>candidate_source={_h(candidate_path.relative_to(MODULE) if candidate_path else 'missing')}<br>validation_source_hash={_h(validation.get('source_hash'))}<br>v3_source={_h(v3_path.relative_to(MODULE) if v3_path else 'reserved')}<br>api_status={_h(api_status)}<br>api_safe_to_scan={_h(api_safe)}<br>cache-only mode when blocked=true</p></details>
</aside>
</div>
</body>
</html>"""


def build_dashboard(write: bool = True, date_key: str = DATE_KEY) -> dict[str, Any]:
    data, candidate_path = _latest_candidate_view(date_key)
    v3, v3_path = _latest_v3_status()
    source_resolution = resolve_source_date(data, candidate_path, write=write)
    validation = build_validation_summary(write=write, date_key=date_key)
    html_text = render_html(data, candidate_path, v3, v3_path, validation, source_resolution)
    digest = hashlib.sha256(html_text.encode()).hexdigest()
    counts = _counts(data)
    formal_count = int(data.get("formal_recommendation_count", counts["A"] + counts["B"]) or 0)
    scan_total = counts["A"] + counts["B"] + counts["C"] + counts["SKIP"]
    marker = {
        "schema_version": "v3v4_dashboard_validation_two_column_script_highlight_build.v1",
        "phase": "V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523",
        "generated_at": _now(),
        "A": counts["A"],
        "B": counts["B"],
        "C_deprecated_count": counts["C"],
        "C_active": False,
        "SKIP": counts["SKIP"],
        "formal_count": counts["A"] + counts["B"],
        "scan_total": scan_total,
        "source_date": source_resolution.get("scan_date"),
        "is_today_source": source_resolution.get("is_today_source"),
        "source_date_mismatch": source_resolution.get("source_date_mismatch"),
        "review_mode": "REPORT_ONLY",
        "v3_status": v3.get("status", "RESERVED_WAITING_FOR_SCHEDULE_OR_INTEL_SOURCE") if v3 else "RESERVED_WAITING_FOR_SCHEDULE_OR_INTEL_SOURCE",
        "dashboard_sha256": digest,
        "validation_summary_sha256": hashlib.sha256(json.dumps(validation, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "source_hash": _source_hash(candidate_path, data),
        "candidate_source": str(candidate_path.relative_to(MODULE)) if candidate_path else None,
        "v3_panel_enabled": True,
        "v4_panel_enabled": True,
        "validation_layout": "two_column",
        "main_validation_blocks": ["yesterday", "cumulative"],
        "unknown_visible_main": False,
        "script_value_highlight": True,
        "strength_dash_visible": False,
        "ht_field_correct": True,
        "c_active_in_dashboard": False,
        "c_validation_visible": False,
        "last_7d_visible": False,
        "c_observation_active": False,
        "last_7d_active": False,
        "brief_used_for_hit_rate": False,
        "c_excluded_from_ab": True,
        "v2_visible": False,
        "v33_visible": False,
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "cron_enabled": False,
        "strategy_changed": False,
        "v4_candidate_numbers_changed": False,
        "validation_numbers_changed": False,
        "attribution_numbers_changed": False,
    }
    if write:
        DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
        for name in ["intel_ops_console.html", "index.html", "intel_desk.html"]:
            (DASHBOARD_DIR / name).write_text(html_text, encoding="utf-8")
        for filename in [
            f"v3v4_dashboard_validation_two_column_script_highlight_build_{DATE_KEY}.json",
            f"v3v4_dashboard_compact_validation_remove_c_obs_build_{DATE_KEY}.json",
            f"v3v4_dashboard_brief_validation_auto_refresh_build_{DATE_KEY}.json",
            f"v3v4_intel_ops_console_ui_data_validation_refit_build_{DATE_KEY}.json",
            f"v3v4_intel_ops_console_ui_refit_build_{DATE_KEY}.json",
        ]:
            (STATUS_DIR / filename).write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        (STATUS_DIR / f"v3v4_intel_desk_html_generation_marker_{DATE_KEY}.json").write_text(
            json.dumps(marker | {"generator": "tools/generate_intel_desk_html.py"}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return marker


def main() -> int:
    marker = build_dashboard(write=True)
    print(json.dumps(marker, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
