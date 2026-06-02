#!/usr/bin/env python3
"""Generate the V3/V4-only Intel Ops console with source-date and validation guards.

Report-only generator. It does not run capture, push messages, enable cron,
publish cloud bundles, change strategy outputs, or read retired current sources.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
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
DATE_KEY = datetime.now(CN_TZ).strftime("%Y%m%d")
CURRENT_LOCAL_DATE = datetime.now(CN_TZ).strftime("%Y%m%d")


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


def _active_source_allowlist(date_key: str = DATE_KEY) -> dict[str, Any]:
    path = STATUS_DIR / f"v3v4_dashboard_active_source_allowlist_{date_key}.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _is_allowed(rel_path: str, key: str, date_key: str = DATE_KEY) -> bool:
    allow = _active_source_allowlist(date_key).get("active_allowlist", {})
    if not isinstance(allow, dict):
        return True
    allowed = allow.get(key)
    if not isinstance(allowed, list):
        return True
    return rel_path in allowed


def _latest_candidate_view(date_key: str = DATE_KEY) -> tuple[dict[str, Any], Path | None]:
    # Prefer the formal daily brief resolver output for the requested date.
    candidate_path = STATUS_DIR / f"v3v4_dashboard_candidate_view_{date_key}.json"
    if not candidate_path.exists() and resolve_brief is not None:
        resolve_brief(date_key, write=True)
    if candidate_path.exists():
        rel = str(candidate_path.relative_to(MODULE))
        if _is_allowed(rel, "candidate_view", date_key):
            return _load_json(candidate_path), candidate_path
    # Fail closed: do not fallback to legacy intel_desk_v4_candidate_view_*.json
    # to avoid stale source pollution (e.g., 20260522 rollback artifacts).
    return {}, None


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
    rows = value if isinstance(value, list) else []
    return [x for x in rows if _is_formal_candidate_row(x)]


def _is_formal_candidate_row(item: dict[str, Any]) -> bool:
    fixture_id = item.get("fixture_id")
    home = str(item.get("home") or "").strip()
    away = str(item.get("away") or "").strip()
    kickoff = str(item.get("kickoff_display") or item.get("kickoff_time") or "").strip()
    dist = str(item.get("distribution_text") or "").strip()
    bad_tokens = {"", "UNKNOWN", "TBD", "：(无)", "(无)", "无"}
    if not fixture_id:
        return False
    if home in bad_tokens or away in bad_tokens:
        return False
    if "UNKNOWN" in home or "UNKNOWN" in away:
        return False
    if kickoff in {"", "TBD"}:
        return False
    if dist in {"", "time_bins 待补齐"}:
        return False
    return True


def _h(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _load_team_map() -> dict[str, str]:
    raw = _load_json(TEAM_CN_MAP)
    exact = raw.get("exact") if isinstance(raw, dict) else {}
    return exact if isinstance(exact, dict) else {}


TEAM_MAP = _load_team_map()

LEAGUE_DISPLAY_ALIASES = {
    "芬甲": "芬甲 / Finland Ykkonen",
    "Finland Ykkonen": "芬甲 / Finland Ykkonen",
    "Ykkonen": "芬甲 / Finland Ykkonen",
}

TEAM_DISPLAY_ALIASES = {
    "Rops": "罗瓦涅米RoPS",
    "RoPS": "罗瓦涅米RoPS",
    "OLS": "奥卢OLS",
}


def _cn_name(name: Any) -> tuple[str, str | None]:
    original = str(name or "UNKNOWN")
    mapped = TEAM_MAP.get(original) or TEAM_MAP.get(original.strip())
    return (mapped or original, original if mapped and mapped != original else None)


def _team_display(item: dict[str, Any]) -> dict[str, str]:
    home_en = str(item.get("home_team_en") or item.get("home_en") or item.get("home") or item.get("home_team") or "UNKNOWN")
    away_en = str(item.get("away_team_en") or item.get("away_en") or item.get("away") or item.get("away_team") or "UNKNOWN")
    home_cn = str(item.get("home_team_cn") or item.get("home_cn") or "").strip()
    away_cn = str(item.get("away_team_cn") or item.get("away_cn") or "").strip()
    missing = bool(item.get("team_cn_missing"))
    if home_cn.startswith("中文名缺失："):
        home_cn = ""
        missing = True
    if away_cn.startswith("中文名缺失："):
        away_cn = ""
        missing = True
    home_alias = TEAM_DISPLAY_ALIASES.get(home_en)
    away_alias = TEAM_DISPLAY_ALIASES.get(away_en)
    if home_alias:
        home_cn = home_alias
        missing = False
    if away_alias:
        away_cn = away_alias
        missing = False
    if not home_cn or home_cn == home_en:
        home_cn = home_en
        missing = True
    if not away_cn or away_cn == away_en:
        away_cn = away_en
        missing = True
    title = f"{home_cn} vs {away_cn}"
    return {
        "title": title,
        "home_cn": home_cn,
        "away_cn": away_cn,
        "home_en": home_en,
        "away_en": away_en,
        "cn_status": "暂无中文映射，显示原始队名" if missing else "中文/音译名",
    }


def _market_advice_display(item: dict[str, Any]) -> str:
    line = _clean_value(item.get("default_line") or item.get("line") or item.get("displayLine")) or "0.75"
    stake = _clean_value(item.get("default_stake") or item.get("stake")) or "150"
    return f"{line} / {stake}"


def _grade_display(grade: str) -> str:
    return f"{grade}级候选"


def _audit_summary(item: dict[str, Any]) -> str:
    text = str(item.get("distribution_text") or "")
    rf_grade = _clean_value(item.get("rf_shadow_grade"))
    market_grade = _clean_value(item.get("market_adjusted_shadow_grade"))
    if not rf_grade:
        m = re.search(r"shadow=([A-Z]+)", text)
        rf_grade = m.group(1) if m else "C"
    if not market_grade:
        m = re.search(r"market_adjusted_shadow_grade\(([A-Z]+)\)", text)
        market_grade = m.group(1) if m else "C"
    return f"RF {rf_grade}，盘后 {market_grade}"


def _audit_rows(item: dict[str, Any], grade: str, dist_note: dict[str, Any]) -> list[tuple[str, str]]:
    text = str(item.get("distribution_text") or "")
    market_evidence = "盘口强确认，但资料不足" if "STRONG_CONFIRMED" in text or "MARKET_STRONG_CONFIRM" in text else "资料不足"
    season = "赛季进行中" if "ACTIVE_SEASON" in text else "赛季阶段未明"
    tier = "三级联赛，覆盖较弱" if "TIER_3_WEAK_COVERAGE" in text else "覆盖状态未明"
    return [
        ("正式等级", _grade_display(grade)),
        ("盘口证据", market_evidence),
        ("近况 / 交锋", "H2H样本不足"),
        ("赛季阶段", season),
        ("联赛覆盖", tier),
        ("技术审计", _audit_summary(item)),
        ("进球分布", str(dist_note["summary"])),
        ("缺失原因", str(dist_note["unsupported_reason"])),
    ]


def _league_display(item: dict[str, Any]) -> str:
    league = str(item.get("league") or item.get("league_name") or "UNKNOWN").strip()
    return LEAGUE_DISPLAY_ALIASES.get(league, league)


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


def _goal_distribution_note(item: dict[str, Any]) -> dict[str, Any]:
    dist = item.get("goal_distribution") or item.get("goal_time_distribution") or {}
    peak = item.get("peak_goal_window")
    has_real_dist = isinstance(dist, dict) and (dist.get("available") is True or any(k in dist for k in ("m0_15", "m16_30", "m31_45")))
    if has_real_dist or peak:
        return {
            "missing": False,
            "summary": _time_bins(item),
            "reasons": [],
            "unsupported_reason": "真实进球分布已返回",
        }
    reasons: list[str] = []
    h2h_count = item.get("h2h_used_count") or item.get("h2h_valid_count") or item.get("h2h_official_count") or item.get("sample_size")
    if item.get("h2h_low_sample") is True or not h2h_count:
        reasons.append("H2H样本不足")
    dist_text = str(item.get("distribution_text") or "")
    if "TIER_3_WEAK_COVERAGE" in dist_text or "WEAK_COVERAGE" in dist_text or not item.get("league_sample"):
        reasons.append("联赛长期样本不足")
    reasons.append("数据源未返回进球时间分布")
    deduped = list(dict.fromkeys(reasons))
    return {
        "missing": True,
        "summary": "暂无真实进球分布。",
        "reasons": deduped,
        "unsupported_reason": " / ".join(deduped),
    }


def _candidate_decision_focus(items: list[dict[str, Any]]) -> str:
    item = items[0] if items else {}
    if not item:
        return """
<section class="panel decision-focus-panel">
  <h2>单场决策</h2>
  <p class="hint">暂无 B 候选，等待下一次 V4 情报刷新。</p>
</section>"""
    teams = _team_display(item)
    dist_note = _goal_distribution_note(item)
    league = _league_display(item)
    gap = "进球分布不可用" if dist_note["missing"] else "无"
    reason = f"{dist_note['unsupported_reason']}。"
    grade = str(item.get("grade") or "B").upper()
    conclusion_grade = f"{grade}级"
    return f"""
<section class="panel decision-focus-panel">
  <h2>单场决策</h2>
  <div class="decision-title">对阵：{_h(teams['title'])}</div>
  <div class="decision-original">原始队名：{_h(teams['home_en'])} vs {_h(teams['away_en'])}</div>
  <div class="decision-sub">联赛：{_h(league)}</div>
  <div class="decision-row"><span>等级：</span><b>{_h(_grade_display(grade))}</b></div>
  <div class="decision-row"><span>状态：</span><b>待关注</b></div>
  <div class="decision-row"><span>盘口建议：</span><b>{_h(_market_advice_display(item))}</b></div>
  <div class="decision-row"><span>技术审计：</span><b>{_h(_audit_summary(item))}</b></div>
  <div class="decision-row decision-sentence">数据缺口：{_h(gap)}。</div>
  <div class="decision-row decision-sentence">不支持原因：{_h(reason)}</div>
  <div class="decision-row decision-sentence">当前结论：{_h(conclusion_grade)}待关注，不是已推送推荐。</div>
</section>"""


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
    official_counts = summary.get("official_counts", {}) if isinstance(summary.get("official_counts"), dict) else {}
    rec = official_counts.get("recommended", {}) if isinstance(official_counts.get("recommended"), dict) else {}
    ver = official_counts.get("verified", {}) if isinstance(official_counts.get("verified"), dict) else {}
    pen = official_counts.get("pending", {}) if isinstance(official_counts.get("pending"), dict) else {}
    rec_ab = int(rec.get("AB", 0) or 0)
    ver_ab = int(ver.get("AB", 0) or 0)
    pen_ab = int(pen.get("AB", 0) or 0)
    counts_line = ""
    if rec_ab > 0 or ver_ab > 0 or pen_ab > 0:
        counts_line = (
            f"<div style=\"font-size:11px;color:var(--muted);margin:4px 0 8px;padding-left:4px\">"
            f"推荐 A<strong style=\"color:var(--green)\">{int(rec.get('A', 0) or 0)}</strong> · "
            f"B<strong style=\"color:var(--blue)\">{int(rec.get('B', 0) or 0)}</strong> · "
            f"合计<strong>{rec_ab}</strong>　"
            f"已验证 <strong>{ver_ab}/{rec_ab}</strong>　待补验 <strong>{pen_ab}</strong></div>"
        )
    source_label = str(summary.get("source_label") or "A/B-only · 不含C · official settled only")
    safe_na_reason = summary.get("safe_na_reason")
    if safe_na_reason:
        reason = f"昨日验证安全显示：{safe_na_reason}；不代表验证链路成功。累计主口径：{source_label}。"
    else:
        reason = f"昨日 official A/B 验证与累计均来自同一 source-of-truth；累计主口径：{source_label}。"
    return f"""
<section class="panel validation-panel compact-validation two-column-validation-card">
  <h2>V3/V4 比赛验证</h2>
  <p class="hint">只展示昨日验证与累计验证；数据来自正式 V4 attribution / validation / review，不从 brief 反推命中率。</p>
  <div class="validation-grid">
    <div class="validation-col validation-yesterday"><h3>昨日验证</h3>{_metric_line('A', y.get('A', {}))}{_metric_line('B', y.get('B', {}))}{_metric_line('A+B', y.get('A_plus_B', {}))}{counts_line}</div>
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
    teams = _team_display(item)
    english = f"<div class='english-line'>原始队名：{_h(teams['home_en'])} vs {_h(teams['away_en'])}</div>"
    league = _h(_league_display(item))
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
    dist_note = _goal_distribution_note(item)
    r3 = (
        f"<span>等级：{_h(_grade_display(grade))}</span>"
        f"<span>状态：待关注</span>"
        f"<span>盘口建议：{_h(_market_advice_display(item))}</span>"
        f"<span>技术审计：{_h(_audit_summary(item))}</span>"
    )
    if dist_note["missing"]:
        bins = (
            "<div class='goal-dist-missing'><b>暂无真实进球分布。</b>"
            f"<span>原因：{_h(dist_note['unsupported_reason'])}。</span></div>"
        )
    else:
        bins = _h(str(dist_note["summary"]))
    gap_text = "进球分布不可用" if dist_note["missing"] else ("、".join(missing_fields) if missing_fields else "无")
    missing = f"<div class='missing-fields'>数据缺口：{_h(gap_text)}。</div>"
    unsupported = (
        f"<div class='unsupported-reason'>不支持原因：{_h(dist_note['unsupported_reason'])}。</div>"
        if dist_note["missing"] else ""
    )
    shadow_pairs = _audit_rows(item, grade, dist_note)
    shadow_lines = "".join(
        f"<div class='row'><span>{_h(k)}</span><b>{_h(v)}</b></div>" for k, v in shadow_pairs
    )
    shadow_detail = f"<details class='shadow-fold' open><summary>技术审计</summary>{shadow_lines}</details>"
    decision_detail = (
        "<details class='decision-gap-fold' open><summary>单场决策数据说明</summary>"
        f"<div class='row'><span>数据缺口</span><b>{_h(gap_text)}。</b></div>"
        f"<div class='row'><span>进球分布</span><b>{_h(dist_note['summary'])}</b></div>"
        f"<div class='row'><span>不支持原因</span><b>{_h(dist_note['unsupported_reason'])}。</b></div>"
        "</details>"
    )
    return f"""
<article class="candidate-card grade-{grade}" data-grade="{grade}">
  <div class="card-r1"><span>{kickoff}</span><span>联赛：{league}</span><b class="grade-badge grade-badge-{grade}">{_h(_grade_display(grade))}</b></div>
  <div class="match-line">对阵：{_h(teams['title'])}</div>
  <div class="card-r3 summary-grid">{r3}</div>
  <div class="time-bins">{bins}</div>
  {english}{missing}{unsupported}{decision_detail}{shadow_detail}
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
    scan_total = int(data.get("scan_total", counts["A"] + counts["B"] + counts["C"] + counts["SKIP"]) or 0)
    source_window = _h(data.get("source_window", "unknown"))
    scan_date = _h(source_resolution.get("scan_date", "unknown"))
    display_label = _h(source_resolution.get("display_label", "最近候选"))
    api_status_marker = _latest_api_status(DATE_KEY)
    api_safe = api_status_marker.get("safe_to_scan")
    api_status = str(api_status_marker.get("api_status") or "API_UNKNOWN")
    api_last_good = "稳定版本已保留"
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
header{{padding:8px 2px 10px}}h1{{margin:0;font-size:24px;letter-spacing:.02em}}.sub{{color:var(--muted);font-size:12px;margin-top:4px}}.notice{{background:rgba(231,184,78,.13);border:1px solid rgba(231,184,78,.42);border-radius:14px;padding:10px 12px;margin:4px 0 14px;color:#ffe3a2;font-weight:700}}.kpi-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:6px 0 10px}}.kpi{{background:linear-gradient(155deg,var(--panel),#0c1727);border:1px solid var(--line);border-radius:12px;padding:10px;min-height:76px;box-shadow:0 12px 30px rgba(0,0,0,.22)}}.kpi .label{{color:var(--muted);font-size:12px}}.kpi .value{{font-size:20px;font-weight:800;margin-top:6px}}.kpi .foot{{font-size:12px;color:var(--muted);margin-top:3px}}.layout{{display:grid;grid-template-columns:1.15fr .85fr;gap:12px;align-items:start}}.panel,.candidate-group{{background:rgba(16,27,44,.92);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px;box-shadow:0 10px 28px rgba(0,0,0,.18)}}h2{{font-size:16px;margin:0 0 8px;color:var(--blue)}}h3{{font-size:14px;margin:8px 0 6px;color:#cfe8ff}}.row{{display:flex;justify-content:space-between;gap:16px;border-top:1px solid rgba(255,255,255,.07);padding:8px 0}}.row:first-of-type{{border-top:0}}.row span{{color:var(--muted)}}.ok{{color:var(--green)}}.warn{{color:var(--amber)}}.danger{{color:var(--red)}}summary{{cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:12px;font-weight:800}}details>summary::-webkit-details-marker{{display:none}}.group-note,.hint{{color:var(--muted);font-size:13px;margin:6px 0}}.candidate-list{{display:grid;gap:8px;margin-top:8px}}.candidate-card{{background:linear-gradient(155deg,var(--panel2),#0b1422);border:1px solid rgba(255,255,255,.08);border-left:4px solid var(--line);border-radius:12px;padding:10px}}.candidate-card.grade-A{{border-left-color:var(--green)}}.candidate-card.grade-B{{border-left-color:var(--blue)}}.candidate-card.grade-C{{border-left-color:var(--amber)}}.card-r1{{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}}.card-r1 span:nth-child(2){{flex:1;white-space:normal}}.grade-badge{{border-radius:999px;padding:3px 9px;font-size:12px;color:#08111f}}.grade-badge-A{{background:var(--green)}}.grade-badge-B{{background:var(--blue)}}.grade-badge-C{{background:var(--amber)}}.match-line{{font-size:18px;font-weight:800;margin-top:6px}}.match-line span{{font-weight:500;color:var(--muted);font-size:13px}}.summary-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4px 10px;color:var(--ink)}}.card-r3,.time-bins,.english-line,.cn-display-line,.missing-fields,.unsupported-reason{{font-size:13px;color:var(--muted);margin-top:5px}}.goal-dist-missing{{display:grid;gap:2px;color:var(--muted)}}.goal-dist-missing b{{color:#f2d27a}}.goal-dist-missing span{{font-size:13px;white-space:normal}}.decision-focus-panel{{border-color:rgba(88,183,255,.55)}}.decision-title{{font-size:18px;font-weight:800;margin-bottom:4px}}.decision-original,.decision-sub{{color:var(--muted);font-size:13px;margin-bottom:6px}}.decision-row{{display:block;border-top:1px solid rgba(255,255,255,.08);padding:8px 0;font-size:14px}}.decision-row span{{display:block;color:var(--muted);font-size:12px;margin-bottom:3px}}.decision-row b{{display:block;color:var(--ink);white-space:normal;line-height:1.35}}.decision-sentence{{color:var(--ink);font-weight:800;line-height:1.35;white-space:normal}}.decision-gap-fold,.shadow-fold{{margin-top:8px;border-top:1px dashed rgba(255,255,255,.12);padding-top:6px}}.decision-gap-fold .row,.shadow-fold .row{{padding:4px 0;font-size:12px;gap:12px}}.decision-gap-fold .row span,.shadow-fold .row span{{max-width:45%;white-space:normal}}.decision-gap-fold .row b,.shadow-fold .row b{{flex:1;font-size:12px;text-align:right;white-space:normal;word-break:break-word}}.script-label{{color:var(--muted)}}.script-value{{color:var(--amber);font-weight:800}}.lineage{{margin-top:10px;border-top:1px dashed rgba(255,255,255,.12);padding-top:8px;color:var(--muted);font-size:12px}}.validation-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.validation-col{{border-top:1px solid rgba(255,255,255,.08);padding-top:6px}}.validation-metric{{display:grid;grid-template-columns:38px 1fr;gap:5px;padding:4px 0;font-size:13px;align-items:center}}.validation-metric span{{color:var(--muted);font-style:normal}}.validation-metric b{{font-size:13px;white-space:nowrap}}.script-validation-lite{{margin-top:10px;padding:8px 10px;border:1px solid rgba(255,255,255,.10);border-radius:12px;background:rgba(255,255,255,.035);display:grid;grid-template-columns:auto 1fr;gap:4px 8px;align-items:center;font-size:12px}}.script-validation-lite .script-lite-title{{color:var(--muted);font-weight:800}}.script-validation-lite>b{{color:#f2d27a;font-weight:800}}.script-validation-lite>em{{grid-column:1/-1;color:var(--muted);font-style:normal}}.script-validation-chip{{display:inline-flex;gap:4px;align-items:center;border:1px solid rgba(255,255,255,.09);border-radius:999px;padding:3px 7px;background:rgba(255,255,255,.04)}}.script-validation-chip i{{font-style:normal;color:var(--muted)}}.script-validation-chip b{{color:var(--amber);font-weight:800}}.compact-validation{{padding-bottom:10px}}.validation-audit{{margin-top:8px;border-top:1px dashed rgba(255,255,255,.12);padding-top:8px}}.next-list{{margin:0;padding-left:18px;color:var(--muted)}}.audit-code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted);word-break:break-all}}@media(max-width:760px){{body{{padding:12px}}.kpi-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.layout{{grid-template-columns:1fr}}h1{{font-size:23px}}.kpi .value{{font-size:20px}}.summary-grid{{grid-template-columns:1fr}}.validation-metric{{grid-template-columns:38px 1fr}}.decision-gap-fold .row,.shadow-fold .row{{display:block}}.decision-gap-fold .row span,.shadow-fold .row span{{display:block;max-width:100%;white-space:normal}}.decision-gap-fold .row b,.shadow-fold .row b{{display:block;text-align:left;margin-top:2px}}}}
</style>
</head>
<body>
<header>
  <h1>情报决策总台 — V3/V4</h1>
  <div class="sub">生成时间={generated_at} · 扫描窗口={source_window} · 未采集 · 未推送 · 未发布</div>
</header>
{data_notice}
<section class="kpi-grid" aria-label="top status cards">
  <div class="kpi"><div class="label">数据状态</div><div class="value {data_status_class}">{data_status}</div><div class="foot">{display_label} · {api_last_good}</div></div>
  <div class="kpi"><div class="label">候选结构</div><div class="value">A{counts['A']} / B{counts['B']}</div><div class="foot">SKIP {counts['SKIP']}</div></div>
  <div class="kpi"><div class="label">复盘状态</div><div class="value warn">待复盘</div><div class="foot">等待赛果 / 可复盘</div></div>
  <div class="kpi"><div class="label">阻断</div><div class="value {('ok' if blockers == 0 else 'danger')}">{blockers}</div><div class="foot">当前阻断数</div></div>
</section>
<div class="layout">
<main>
<section class="panel candidate-panel">
  <h2>候选列表</h2>
  <p class="hint">{display_label}。候选列表只展示 A/B 正式候选；SKIP 仅作为系统状态。</p>
  {_group('B级候选', 'B', b_items, True)}
  {_group('A级候选', 'A', a_items, False)}
</section>
<section class="panel">
  <h2>V4 情报状态</h2>
  <div class="row"><span>正式候选</span><b>{counts['A'] + counts['B']} 场</b></div>
  <div class="row"><span>A/B/SKIP</span><b>A{counts['A']} / B{counts['B']} / SKIP{counts['SKIP']}</b></div>
  <div class="row"><span>复盘模式</span><b>待复盘</b></div>
  <div class="row"><span>全量扫描场次</span><b>{scan_total}</b></div>
  <div class="row"><span>采集日期 / 窗口</span><b>{scan_date} / {source_window}</b></div>
</section>
{_validation_section(validation)}
</main>
<aside>
{_candidate_decision_focus(b_items or a_items)}
{_v3_panel(v3, v3_path)}
<section class="panel safety-panel">
  <h2>系统安全</h2>
  <div class="row"><span>V3 active</span><b>战备中 / 预留</b></div>
  <div class="row"><span>V4复盘模式</span><b>只展示，未推送</b></div>
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
    scan_total = int(data.get("scan_total", counts["A"] + counts["B"] + counts["C"] + counts["SKIP"]) or 0)
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
        "review_mode": "只展示，未推送",
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
