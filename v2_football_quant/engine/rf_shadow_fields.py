from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _safe_rate(hit: int, sample: int) -> float | None:
    if sample <= 0:
        return None
    return round(hit / sample, 3)


def _parse_fixture_dt(match: dict) -> Optional[datetime]:
    fixture = match.get("fixture") or {}
    ts = fixture.get("timestamp")
    if isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    raw = fixture.get("date")
    if not raw or not isinstance(raw, str):
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def build_team_fh_samples(recent_resp: dict | None, team_id: int, max_n: int = 10) -> list[dict]:
    matches = []
    if isinstance(recent_resp, dict):
        rows = recent_resp.get("response")
        if isinstance(rows, list):
            matches = rows

    samples: list[dict] = []
    for m in matches:
        score = m.get("score") or {}
        ht = score.get("halftime") or {}
        ht_home = ht.get("home")
        ht_away = ht.get("away")
        # RF strict rule: halftime score must exist
        if ht_home is None or ht_away is None:
            continue

        teams = m.get("teams") or {}
        home_id = (teams.get("home") or {}).get("id")
        away_id = (teams.get("away") or {}).get("id")
        if str(home_id) == str(team_id):
            ht_for = int(ht_home)
            ht_against = int(ht_away)
        elif str(away_id) == str(team_id):
            ht_for = int(ht_away)
            ht_against = int(ht_home)
        else:
            continue

        samples.append(
            {
                "involved": (int(ht_home) + int(ht_away)) > 0,
                "scored": ht_for > 0,
                "conceded": ht_against > 0,
                "dt": _parse_fixture_dt(m),
            }
        )
        if len(samples) >= max_n:
            break
    return samples


def summarize_recent(samples: list[dict]) -> dict:
    n = len(samples)
    involved = sum(1 for x in samples if x.get("involved"))
    scored = sum(1 for x in samples if x.get("scored"))
    conceded = sum(1 for x in samples if x.get("conceded"))
    dts = [x.get("dt") for x in samples if isinstance(x.get("dt"), datetime)]
    if len(dts) >= 2:
        window_days = int((max(dts) - min(dts)).days)
    elif len(dts) == 1:
        window_days = 0
    else:
        window_days = None
    return {
        "sample_count": n,
        "involved_rate": _safe_rate(involved, n),
        "score_rate": _safe_rate(scored, n),
        "concede_rate": _safe_rate(conceded, n),
        "window_days": window_days,
    }


def freshness_status(home_days: Optional[int], away_days: Optional[int], home_n: int, away_n: int) -> str:
    if home_n <= 0 or away_n <= 0:
        return "UNKNOWN"
    if home_days is None or away_days is None:
        return "UNKNOWN"
    span = max(home_days, away_days)
    if span <= 90:
        return "FRESH"
    if span <= 120:
        return "NORMAL"
    if span <= 180:
        return "STALE"
    return "EXPIRED"


def _pct_text(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{round(v * 100)}%"


def build_recent_form_shadow_from_recent(
    home_recent_resp: dict | None,
    home_id: int,
    away_recent_resp: dict | None,
    away_id: int,
) -> dict[str, Any]:
    home10_samples = build_team_fh_samples(home_recent_resp, home_id, max_n=10)
    away10_samples = build_team_fh_samples(away_recent_resp, away_id, max_n=10)
    home5_samples = home10_samples[:5]
    away5_samples = away10_samples[:5]

    home10 = summarize_recent(home10_samples)
    away10 = summarize_recent(away10_samples)
    home5 = summarize_recent(home5_samples)
    away5 = summarize_recent(away5_samples)

    h10_inv = home10["involved_rate"]
    a10_inv = away10["involved_rate"]
    h5_inv = home5["involved_rate"]
    a5_inv = away5["involved_rate"]

    combined10 = round((h10_inv + a10_inv) / 2, 3) if h10_inv is not None and a10_inv is not None else None
    combined5 = round((h5_inv + a5_inv) / 2, 3) if h5_inv is not None and a5_inv is not None else None

    freshness = freshness_status(
        home10["window_days"],
        away10["window_days"],
        home10["sample_count"],
        away10["sample_count"],
    )

    if home5["sample_count"] < 5 or away5["sample_count"] < 5:
        momentum = "LOW_SAMPLE"
    elif combined10 is None or combined5 is None:
        momentum = "DATA_MISSING"
    else:
        delta = combined5 - combined10
        if delta > 0.10:
            momentum = "HEATING_UP"
        elif delta < -0.10:
            momentum = "COOLING_DOWN"
        else:
            momentum = "STABLE"

    primary_score: float | None = None
    primary_level = "DATA_MISSING"
    primary_reason = "近10样本缺失，RF 不参与"

    if combined10 is not None:
        if home10["sample_count"] < 3 or away10["sample_count"] < 3:
            primary_level = "LOW_SAMPLE"
            primary_reason = (
                f"近10样本不足（home={home10['sample_count']}, away={away10['sample_count']}），RF 不参与"
            )
        elif combined5 is None or home5["sample_count"] < 5 or away5["sample_count"] < 5:
            primary_level = "LOW_SAMPLE"
            primary_reason = (
                f"近10 FH参与率 {_pct_text(combined10)}，近5样本不足（home={home5['sample_count']}, away={away5['sample_count']}）"
            )
        else:
            primary_score = round((combined10 * 0.70 + combined5 * 0.30) * 100, 1)
            if primary_score >= 70:
                primary_level = "STRONG"
            elif primary_score >= 55:
                primary_level = "MEDIUM"
            else:
                primary_level = "WEAK"
            if freshness == "STALE":
                primary_level = "STALE_SAMPLE"
            elif freshness == "EXPIRED":
                primary_level = "EXPIRED_SAMPLE"
            momentum_text = {
                "HEATING_UP": "升温",
                "STABLE": "稳定",
                "COOLING_DOWN": "降温",
                "LOW_SAMPLE": "样本不足",
                "DATA_MISSING": "数据缺失",
            }.get(momentum, momentum)
            primary_reason = f"近10 FH参与率 {_pct_text(combined10)}，近5 {momentum_text}，样本 {freshness}"
            if freshness in ("STALE", "EXPIRED"):
                primary_reason = (
                    f"近10跨度 {max(home10['window_days'] or 0, away10['window_days'] or 0)} 天，样本 {freshness}，仅参考"
                )

    return {
        "home_recent10_fh_involved_rate": h10_inv,
        "away_recent10_fh_involved_rate": a10_inv,
        "combined_recent10_fh_involved_rate": combined10,
        "home_recent10_fh_score_rate": home10["score_rate"],
        "away_recent10_fh_score_rate": away10["score_rate"],
        "home_recent10_fh_concede_rate": home10["concede_rate"],
        "away_recent10_fh_concede_rate": away10["concede_rate"],
        "recent10_sample_count_home": home10["sample_count"],
        "recent10_sample_count_away": away10["sample_count"],
        "recent10_window_days_home": home10["window_days"],
        "recent10_window_days_away": away10["window_days"],
        "recent_freshness_status": freshness,
        "home_recent5_fh_involved_rate": h5_inv,
        "away_recent5_fh_involved_rate": a5_inv,
        "combined_recent5_fh_involved_rate": combined5,
        "home_recent5_fh_score_rate": home5["score_rate"],
        "away_recent5_fh_score_rate": away5["score_rate"],
        "home_recent5_fh_concede_rate": home5["concede_rate"],
        "away_recent5_fh_concede_rate": away5["concede_rate"],
        "recent5_momentum_status": momentum,
        "recent_form_primary_score": primary_score,
        "recent_form_primary_level": primary_level,
        "recent_form_primary_reason": primary_reason,
    }
