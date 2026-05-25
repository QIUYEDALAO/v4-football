#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STATUS = ROOT / 'data/runtime/status'
TZ = timezone(timedelta(hours=8))


def now() -> str:
    return datetime.now(TZ).isoformat()


def load(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def metric(hit: int, miss: int, unknown: int = 0) -> dict[str, Any]:
    settled = hit + miss
    rate = (hit / settled) if settled else None
    return {
        'count': settled,
        'hit': hit,
        'miss': miss,
        'unknown': unknown,
        'settled': settled,
        'hit_rate': rate,
        'display_rate': 'N/A' if rate is None else f'{rate*100:.1f}%',
        'display_compact': 'N/A' if rate is None else f'{hit}/{settled} · {rate*100:.1f}%',
    }


def is_settled_status(short: str, long_status: str) -> bool:
    s = (short or '').upper().strip()
    if s in {'FT', 'AET', 'PEN'}:
        return True
    txt = (long_status or '').lower()
    return 'match finished' in txt or 'after extra time' in txt or 'penalties' in txt


def choose_official_source(target_date: str) -> tuple[list[dict[str, Any]], str]:
    # Official source: candidate_view of target_date only (A/B from formal brief), no scout full pool.
    cv = STATUS / f'v3v4_dashboard_candidate_view_{target_date}.json'
    data = load(cv, {}) if cv.exists() else {}
    rows: list[dict[str, Any]] = []
    for k in ('A_candidates', 'B_candidates'):
        arr = data.get(k)
        if not isinstance(arr, list):
            continue
        for r in arr:
            if not isinstance(r, dict):
                continue
            fid = r.get('fixture_id')
            try:
                fid = int(fid)
            except Exception:
                continue
            grade = str(r.get('grade') or ('A' if k.startswith('A') else 'B')).upper()
            if grade not in {'A', 'B'}:
                continue
            home = r.get('home') or r.get('home_team_en') or r.get('home_team')
            away = r.get('away') or r.get('away_team_en') or r.get('away_team')
            if not home or not away:
                continue
            # block placeholders from official cards
            h = str(home).strip()
            a = str(away).strip()
            bad = {'', 'UNKNOWN', 'TBD', '：(无)', '(无)', '无'}
            if h in bad or a in bad or 'UNKNOWN' in h or 'UNKNOWN' in a:
                continue
            rows.append({
                'fixture_id': fid,
                'grade': grade,
                'home': str(home),
                'away': str(away),
                'league': r.get('league'),
                'script_type': r.get('script_type') or 'UNKNOWN_SCRIPT',
                'source': str(cv.relative_to(ROOT)),
            })
    dedup = {}
    for r in rows:
        dedup[(r['fixture_id'], r['grade'])] = r
    return list(dedup.values()), str(cv.relative_to(ROOT)) if cv.exists() else 'MISSING_CANDIDATE_VIEW'


def first_half_goal_minutes(events_payload: dict[str, Any]) -> tuple[list[int], str]:
    rows = events_payload.get('response') or []
    mins: list[int] = []
    for ev in rows:
        if not isinstance(ev, dict):
            continue
        if str(ev.get('type') or '').strip().lower() != 'goal':
            continue
        detail = str(ev.get('detail') or '').lower()
        if any(x in detail for x in ('missed', 'cancel', 'var', 'awarded', 'disallowed')):
            continue
        elapsed = (ev.get('time') or {}).get('elapsed')
        try:
            m = int(elapsed)
        except Exception:
            continue
        if 0 <= m <= 45:
            mins.append(m)
    mins = sorted(set(mins))
    return mins, ('EVENT_MINUTES_AVAILABLE' if mins or isinstance(rows, list) else 'NO_POSTMATCH_EVENT_DATA')


def run(args: argparse.Namespace) -> dict[str, Any]:
    dashboard_date = args.dashboard_date or (datetime.strptime(args.date, '%Y%m%d').date() + timedelta(days=1)).strftime('%Y%m%d')
    target_date = args.date
    rows, source_path = choose_official_source(target_date)

    api_enabled = not args.no_api
    fixtures_out: list[dict[str, Any]] = []
    script_fixtures_out: list[dict[str, Any]] = []

    a_hit = a_settled = b_hit = b_settled = 0
    script_a_hit = script_a_settled = script_b_hit = script_b_settled = 0
    excluded: list[dict[str, Any]] = []
    api_errors = 0
    events_unavailable = 0

    if api_enabled:
        from engine import net_utils  # local import to avoid side effects when dry/no-api
    else:
        net_utils = None

    # ── Retry policy ──
    SCORE_RETRY = {'max': 5, 'timeout': 12, 'backoff': [0, 10, 30, 60, 120]}
    EVENTS_RETRY = {'max': 4, 'timeout': 12, 'backoff': [0, 15, 45, 90]}
    RETRYABLE_STATUSES = {'timeout', 'connection_reset', 'temporary_5xx', 'empty_response', 'temporary_unavailable'}

    # Load existing retry state for this target_date
    retry_state_path = STATUS / f'v4_validation_retry_state_{target_date}.json'
    retry_state: dict[str, Any] = load(retry_state_path, {})
    state_fixtures: dict[int, dict[str, Any]] = retry_state.get('fixtures', {})
    if not isinstance(state_fixtures, dict):
        state_fixtures = {}

    def _with_retry(fn, max_attempts: int, backoff: list[int], label: str) -> tuple[dict | None, int]:
        for attempt in range(1, max_attempts + 1):
            try:
                if attempt > 1 and backoff and attempt - 1 < len(backoff):
                    import time
                    time.sleep(backoff[attempt - 1])
                result = fn()
                if result is not None and result.get('response') is not None:
                    return result, attempt
            except Exception:
                pass
            if attempt < max_attempts:
                import time
                delay = backoff[min(attempt, len(backoff) - 1)]
                time.sleep(delay)
        return None, max_attempts

    for r in rows:
        fid = int(r['fixture_id'])
        grade = r['grade']
        item = {
            'fixture_id': fid,
            'grade': grade,
            'home': r['home'],
            'away': r['away'],
            'status': 'NOT_QUERIED' if not api_enabled else None,
            'settled': False,
            'ht_hit': None,
        }
        script_item = {
            'fixture_id': fid,
            'grade': grade,
            'home': r['home'],
            'away': r['away'],
            'script_type': r.get('script_type') or 'UNKNOWN_SCRIPT',
            'script_result': 'SCRIPT_UNKNOWN',
            'event_minutes': [],
            'events_status': 'NOT_QUERIED' if not api_enabled else None,
            'count_in_denominator': False,
        }

        # Load existing retry state for this fixture
        sf_entry = state_fixtures.get(fid, {})
        score_attempts = sf_entry.get('score_attempts', 0) if isinstance(sf_entry, dict) else 0
        events_attempts = sf_entry.get('events_attempts', 0) if isinstance(sf_entry, dict) else 0
        if not api_enabled:
            fx_rows = []
            item['status'] = 'API_DISABLED'
            script_item['events_status'] = 'API_DISABLED'
        else:
            fx, score_attempts_made = _with_retry(lambda: net_utils.api_get(f'fixtures?id={fid}'), SCORE_RETRY['max'], SCORE_RETRY['backoff'], f'score-{fid}')
            score_attempts = max(score_attempts, score_attempts_made)
            fx_rows = (fx or {}).get('response') or []

        if not fx_rows:
            api_errors += 1
            if not api_enabled:
                excluded.append({'fixture_id': fid, 'grade': grade, 'reason': 'API_DISABLED'})
            elif score_attempts >= SCORE_RETRY['max']:
                excluded.append({'fixture_id': fid, 'grade': grade, 'reason': 'PENDING_RETRY', 'attempts': score_attempts})
            else:
                excluded.append({'fixture_id': fid, 'grade': grade, 'reason': 'API_ERROR_OR_TIMEOUT', 'attempts': score_attempts})
            item['status'] = 'API_ERROR' if api_enabled else 'API_DISABLED'
            item['error'] = 'fixtures_api_empty_or_error' if api_enabled else 'api_disabled'
            script_item['events_status'] = 'API_ERROR' if api_enabled else 'API_DISABLED'
            fixtures_out.append(item)
            script_fixtures_out.append(script_item)

            # Update retry state
            state_fixtures[fid] = {
                'fixture_id': fid, 'grade': grade, 'home': r['home'], 'away': r['away'],
                'score_attempts': score_attempts, 'events_attempts': events_attempts,
                'last_attempt_at': now(),
                'retry_status': 'PENDING_RETRY' if (api_enabled and score_attempts >= SCORE_RETRY['max']) else 'NOT_RETRYABLE' if not api_enabled else 'PENDING_RETRY',
                'final_status': 'PENDING_RETRY_EXCLUDED' if (api_enabled and score_attempts >= SCORE_RETRY['max']) else 'NOT_RETRYABLE_EXCLUDED',
                'included_in_result_denominator': False,
                'included_in_script_denominator': False,
            }
            continue

        row0 = fx_rows[0]
        st = (row0.get('fixture') or {}).get('status') or {}
        st_long = str(st.get('long') or '')
        st_short = str(st.get('short') or '')
        score = (row0.get('score') or {}).get('halftime') or {}
        h = score.get('home')
        a = score.get('away')
        ht_goals = None
        try:
            if h is not None and a is not None:
                ht_goals = int(h or 0) + int(a or 0)
        except Exception:
            ht_goals = None

        settled = is_settled_status(st_short, st_long) and ht_goals is not None
        item.update({'status': st_long or st_short or 'UNKNOWN', 'status_short': st_short or None, 'ht_goals': ht_goals, 'settled': bool(settled)})

        if settled:
            ht_hit = (ht_goals or 0) > 0
            item['ht_hit'] = bool(ht_hit)
            if grade == 'A':
                a_settled += 1
                a_hit += 1 if ht_hit else 0
            else:
                b_settled += 1
                b_hit += 1 if ht_hit else 0
        else:
            reason = f'NOT_SETTLED:{st_short or st_long or "UNKNOWN"}'
            excluded.append({'fixture_id': fid, 'grade': grade, 'reason': reason})

        # script validation via events endpoint
        ev_rows = None
        if api_enabled:
            ev, events_attempts_made = _with_retry(lambda: net_utils.api_get(f'fixtures/events?fixture={fid}'), EVENTS_RETRY['max'], EVENTS_RETRY['backoff'], f'events-{fid}')
            events_attempts = max(events_attempts, events_attempts_made)
            ev_rows = (ev or {}).get('response')
        if ev_rows is None:
            events_unavailable += 1
            script_item['events_status'] = 'API_ERROR' if api_enabled else 'API_DISABLED'
            script_item['script_result'] = 'SCRIPT_UNKNOWN'
            if api_enabled and events_attempts >= EVENTS_RETRY['max']:
                excluded.append({'fixture_id': fid, 'grade': grade, 'reason': 'EVENTS_PENDING_RETRY', 'attempts': events_attempts})
            elif not api_enabled:
                excluded.append({'fixture_id': fid, 'grade': grade, 'reason': 'API_DISABLED'})
            else:
                excluded.append({'fixture_id': fid, 'grade': grade, 'reason': 'EVENTS_API_ERROR', 'attempts': events_attempts})
        else:
            minutes, quality = first_half_goal_minutes(ev)
            script_item['event_minutes'] = minutes
            script_item['events_status'] = quality
            if settled:
                # settled+events available => denominator includes fixture; hit if any FH goal event.
                has_fh_event_goal = len(minutes) > 0
                script_item['count_in_denominator'] = True
                script_item['script_result'] = 'SCRIPT_HIT' if has_fh_event_goal else 'SCRIPT_MISS'
                if grade == 'A':
                    script_a_settled += 1
                    script_a_hit += 1 if has_fh_event_goal else 0
                else:
                    script_b_settled += 1
                    script_b_hit += 1 if has_fh_event_goal else 0
            else:
                script_item['script_result'] = 'SCRIPT_UNKNOWN'

        fixtures_out.append(item)
        script_fixtures_out.append(script_item)

    ab_settled = a_settled + b_settled
    ab_hit = a_hit + b_hit
    script_ab_settled = script_a_settled + script_b_settled
    script_ab_hit = script_a_hit + script_b_hit

    # Count pending retry fixtures
    pending_a = sum(1 for v in state_fixtures.values() if isinstance(v, dict) and v.get('grade') == 'A' and v.get('retry_status') == 'PENDING_RETRY')
    pending_b = sum(1 for v in state_fixtures.values() if isinstance(v, dict) and v.get('grade') == 'B' and v.get('retry_status') == 'PENDING_RETRY')

    # Save retry state
    retry_state['fixtures'] = state_fixtures
    retry_state['meta'] = {
        'target_date': target_date,
        'dashboard_date': dashboard_date,
        'updated_at': now(),
        'score_policy': SCORE_RETRY,
        'events_policy': EVENTS_RETRY,
    }
    if args.mode == 'apply':
        retry_state_path.parent.mkdir(parents=True, exist_ok=True)
        retry_state_path.write_text(json.dumps(retry_state, ensure_ascii=False, indent=2), encoding='utf-8')

    result_payload = {
        'target_date': target_date,
        'dashboard_date': dashboard_date,
        'source': 'API-SPORTS direct v3 fixtures?id=X',
        'official_source_path': source_path,
        'api_available': api_enabled,
        'total_official_ab': len(rows),
        'a_settled': a_settled,
        'a_hit': a_hit,
        'b_settled': b_settled,
        'b_hit': b_hit,
        'ab_settled': ab_settled,
        'ab_hit': ab_hit,
        'excluded_not_settled': len([x for x in excluded if x['reason'].startswith('NOT_SETTLED')]),
        'api_errors': api_errors,
        'excluded_fixtures': excluded,
        'fixtures': fixtures_out,
    }

    script_payload = {
        'target_date': target_date,
        'dashboard_date': dashboard_date,
        'source': 'API-SPORTS direct v3 fixtures/events?fixture=X',
        'official_source_path': source_path,
        'total_ab': len(rows),
        'a_with_events': script_a_settled,
        'a_first_half_goal_hit': script_a_hit,
        'b_with_events': script_b_settled,
        'b_first_half_goal_hit': script_b_hit,
        'events_unavailable': events_unavailable,
        'fixtures': script_fixtures_out,
    }

    # Build dashboard-compatible summary for dashboard_date
    cum_path = sorted(STATUS.glob('v4_true_cumulative_result_validation_*.json'))
    cum = load(cum_path[-1], {}) if cum_path else {}
    cumA = (cum.get('A') or {})
    cumB = (cum.get('B') or {})
    cumAB = (cum.get('AB') or {})

    summary = {
        'schema_version': 'v4_official_fixture_id_validation_pipeline.v1',
        'phase': 'V4-OFFICIAL-FIXTURE-ID-VALIDATION-PIPELINE-PERSISTENT-FIX-20260526',
        'generated_at': now(),
        'date': dashboard_date,
        'dashboard_date': dashboard_date,
        'yesterday_validation_target_date': target_date,
        'source': 'official_fixture_id_bounded_validation',
        'valid_for_dashboard': True,
        'validation_chain_success': ab_settled > 0,
        'safe_na_reason': None if ab_settled > 0 else ('API_DISABLED' if not api_enabled else 'OFFICIAL_SETTLED_SAMPLE_MISSING_OR_API_TIMEOUT'),
        'result_validation': {
            'yesterday': {
                'A': metric(a_hit, a_settled),
                'B': metric(b_hit, b_settled),
                'A_plus_B': metric(ab_hit, ab_settled),
            },
            'cumulative': {
                'A': {
                    'count': int(cumA.get('resolved', 0) or 0),
                    'hit': int(cumA.get('hit', 0) or 0),
                    'miss': int(cumA.get('miss', 0) or 0),
                    'unknown': int(cumA.get('unknown', 0) or 0),
                    'settled': int(cumA.get('resolved', 0) or 0),
                    'hit_rate': cumA.get('hit_rate'),
                    'display_rate': f"{float(cumA.get('hit_rate',0))*100:.1f}%" if cumA.get('hit_rate') is not None else 'N/A',
                    'display_compact': f"{int(cumA.get('hit',0) or 0)}/{int(cumA.get('resolved',0) or 0)} · {float(cumA.get('hit_rate',0))*100:.1f}%" if int(cumA.get('resolved',0) or 0)>0 else 'N/A',
                },
                'B': {
                    'count': int(cumB.get('resolved', 0) or 0),
                    'hit': int(cumB.get('hit', 0) or 0),
                    'miss': int(cumB.get('miss', 0) or 0),
                    'unknown': int(cumB.get('unknown', 0) or 0),
                    'settled': int(cumB.get('resolved', 0) or 0),
                    'hit_rate': cumB.get('hit_rate'),
                    'display_rate': f"{float(cumB.get('hit_rate',0))*100:.1f}%" if cumB.get('hit_rate') is not None else 'N/A',
                    'display_compact': f"{int(cumB.get('hit',0) or 0)}/{int(cumB.get('resolved',0) or 0)} · {float(cumB.get('hit_rate',0))*100:.1f}%" if int(cumB.get('resolved',0) or 0)>0 else 'N/A',
                },
                'A_plus_B': {
                    'count': int(cumAB.get('resolved', 0) or 0),
                    'hit': int(cumAB.get('hit', 0) or 0),
                    'miss': int(cumAB.get('miss', 0) or 0),
                    'unknown': int(cumAB.get('unknown', 0) or 0),
                    'settled': int(cumAB.get('resolved', 0) or 0),
                    'hit_rate': cumAB.get('hit_rate'),
                    'display_rate': f"{float(cumAB.get('hit_rate',0))*100:.1f}%" if cumAB.get('hit_rate') is not None else 'N/A',
                    'display_compact': f"{int(cumAB.get('hit',0) or 0)}/{int(cumAB.get('resolved',0) or 0)} · {float(cumAB.get('hit_rate',0))*100:.1f}%" if int(cumAB.get('resolved',0) or 0)>0 else 'N/A',
                },
                'label': 'A/B-only · 不含C',
            },
            'excluded_fixtures': excluded,
            'excluded_bodo': any((x.get('fixture_id') == 1494668) for x in excluded),
        },
        'script_validation': {
            'yesterday': {
                'A': metric(script_a_hit, script_a_settled),
                'B': metric(script_b_hit, script_b_settled),
                'AB': metric(script_ab_hit, script_ab_settled),
            },
            'cumulative': load(STATUS / f'v4_script_validation_summary_{dashboard_date}.json', {}).get('cumulative', {}),
            'events_unavailable': events_unavailable,
            'unknown_excluded_from_denominator': True,
            'brief_used_for_script_validation': False,
            'scan_date_used': False,
            'c_included': False,
            'skip_included': False,
        },
        'dashboard_active': {
            'yesterday': {
                'A': metric(a_hit, a_settled),
                'B': metric(b_hit, b_settled),
                'A_plus_B': metric(ab_hit, ab_settled),
            },
            'cumulative': {
                'A': {
                    'hit': int(cumA.get('hit', 0) or 0), 'settled': int(cumA.get('resolved', 0) or 0),
                    'display_rate': f"{int(cumA.get('hit',0) or 0)}/{int(cumA.get('resolved',0) or 0)} · {float(cumA.get('hit_rate',0))*100:.1f}%" if int(cumA.get('resolved',0) or 0)>0 else 'N/A'
                },
                'B': {
                    'hit': int(cumB.get('hit', 0) or 0), 'settled': int(cumB.get('resolved', 0) or 0),
                    'display_rate': f"{int(cumB.get('hit',0) or 0)}/{int(cumB.get('resolved',0) or 0)} · {float(cumB.get('hit_rate',0))*100:.1f}%" if int(cumB.get('resolved',0) or 0)>0 else 'N/A'
                },
                'A_plus_B': {
                    'hit': int(cumAB.get('hit', 0) or 0), 'settled': int(cumAB.get('resolved', 0) or 0),
                    'display_rate': f"{int(cumAB.get('hit',0) or 0)}/{int(cumAB.get('resolved',0) or 0)} · {float(cumAB.get('hit_rate',0))*100:.1f}%" if int(cumAB.get('resolved',0) or 0)>0 else 'N/A'
                },
            }
        },
        'date_filter_field': 'match_date',
        'match_date_used': True,
        'scan_date_used_for_validation': False,
        'brief_used_for_hit_rate': False,
        'scout_full_pool_used': False,
        'outside_57_mixed_into_official': False,
        'c_excluded_from_ab': True,
        'capture_ran': False,
        'QQ_push': False,
        'cloud_publish': False,
    }
    summary['source_hash'] = hashlib.sha256(json.dumps({'result': result_payload, 'script': script_payload}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    outputs = {
        'result': STATUS / f'v4_official_fixture_id_validation_{target_date}.json',
        'script': STATUS / f'v4_official_fixture_id_script_validation_{target_date}.json',
        'summary': STATUS / f'v3v4_validation_summary_{dashboard_date}.json',
    }
    if args.mode == 'apply':
        outputs['result'].write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        outputs['script'].write_text(json.dumps(script_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        outputs['summary'].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'phase': 'V4-OFFICIAL-FIXTURE-ID-VALIDATION-PIPELINE-PERSISTENT-FIX-20260526',
        'generated_at': now(),
        'mode': args.mode,
        'date': target_date,
        'dashboard_date': dashboard_date,
        'official_source': source_path,
        'api_enabled': api_enabled,
        'total_official_ab': len(rows),
        'a': {'settled': a_settled, 'hit': a_hit, 'display': metric(a_hit, a_settled)['display_compact'], 'recommended': len([r for r in rows if r['grade']=='A']), 'pending': pending_a},
        'b': {'settled': b_settled, 'hit': b_hit, 'display': metric(b_hit, b_settled)['display_compact'], 'recommended': len([r for r in rows if r['grade']=='B']), 'pending': pending_b},
        'ab': {'settled': ab_settled, 'hit': ab_hit, 'display': metric(ab_hit, ab_settled)['display_compact'], 'recommended': len(rows), 'pending': pending_a + pending_b},
        'recommended_a': len([r for r in rows if r['grade']=='A']),
        'recommended_b': len([r for r in rows if r['grade']=='B']),
        'pending_a': pending_a,
        'pending_b': pending_b,
        'excluded_count': len(excluded),
        'excluded_bodo': any(x.get('fixture_id') == 1494668 for x in excluded),
        'safe_na_reason': summary.get('safe_na_reason'),
        'summary_path': str(outputs['summary'].relative_to(ROOT)),
        'result_path': str(outputs['result'].relative_to(ROOT)),
        'script_path': str(outputs['script'].relative_to(ROOT)),
        'forbidden_flags': {
            'full_scan_ran': False,
            'capture_ran': False,
            'strategy_changed': False,
            'candidate_changed': False,
            'candidate_rating_changed': False,
            'result_validation_history_changed': False,
            'script_validation_history_changed': False,
            'brief_used_for_hit_rate': False,
            'scan_date_used_for_validation': False,
            'scout_full_pool_used': False,
            'outside_57_mixed_into_official': False,
            'v2_restored': False,
            'v33_active': False,
            'QQ_push': False,
            'cloud_publish': False,
            'cron_schedule_modified': False,
            'secrets_printed': False,
            'secrets_committed': False,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--date', required=True, help='target_date YYYYMMDD (yesterday official recommendations date)')
    p.add_argument('--dashboard-date', default=None, help='dashboard date YYYYMMDD; defaults to target+1')
    p.add_argument('--mode', choices=['dry-run', 'apply'], default='dry-run')
    p.add_argument('--no-api', action='store_true')
    p.add_argument('--apply', action='store_true', help='alias of --mode apply')
    p.add_argument('--strict', action='store_true')
    args = p.parse_args()
    if args.apply:
        args.mode = 'apply'
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.strict and result['total_official_ab'] == 0:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
