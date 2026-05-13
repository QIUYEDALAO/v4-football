#!/usr/bin/env python3
"""Patch scout data with real time_bins from api-football recent match events."""
import json, requests, time, os, sys

# Force no proxy
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

KEY = 'e5e315b1f9ba1ba51dc2124b35f07a01'
HEADERS = {'x-apisports-key': KEY}
BASE = 'https://v3.football.api-sports.io'


def api(endpoint):
    r = requests.get(f'{BASE}/{endpoint}', headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def parse_goal_events(fixture_id):
    bins = {"0_10": False, "11_15": False, "0_15": False, "11_30": False,
            "11_45": False, "16_30": False, "16_45": False, "31_45": False,
            "46_60": False, "61_75": False, "76_90": False}
    try:
        resp = api(f'fixtures/events?fixture={fixture_id}')
        for event in resp.get('response', []):
            if event.get('type') != 'Goal':
                continue
            elapsed = event.get('time', {}).get('elapsed', 0) or 0
            if elapsed <= 10:
                bins["0_10"] = bins["0_15"] = True
            elif elapsed <= 15:
                bins["11_15"] = bins["0_15"] = bins["11_30"] = bins["11_45"] = True
            elif elapsed <= 30:
                bins["16_30"] = bins["11_30"] = bins["11_45"] = bins["16_45"] = True
            elif elapsed <= 45:
                bins["31_45"] = bins["11_45"] = bins["16_45"] = True
            elif elapsed <= 60:
                bins["46_60"] = True
            elif elapsed <= 75:
                bins["61_75"] = True
            else:
                bins["76_90"] = True
    except Exception:
        pass
    return bins


def recent_time_bins(team_id, last_n=5):
    """Get recent match time_bins for a team."""
    resp = api(f'fixtures?team={team_id}&last={last_n}&status=FT')
    matches = resp.get('response', [])
    bins = {"0_10": 0, "11_15": 0, "0_15": 0, "11_30": 0,
            "11_45": 0, "16_30": 0, "16_45": 0, "31_45": 0}
    sh_bins = {"46_60": 0, "61_75": 0, "76_90": 0}
    n = 0
    for m in matches:
        fid = m.get('fixture', {}).get('id')
        if not fid:
            continue
        ev = parse_goal_events(fid)
        for k in bins:
            if ev.get(k): bins[k] += 1
        for k in sh_bins:
            if ev.get(k): sh_bins[k] += 1
        n += 1
    denom = max(n, 1)
    return (
        {k: round(v / denom, 3) for k, v in bins.items()},
        {k: round(v / denom, 3) for k, v in sh_bins.items()},
        n
    )


def main():
    scout_path = 'data/daily_reports/scout_v4_20260513.json'
    scout = json.load(open(scout_path))
    patched = 0

    for i, rec in enumerate(scout):
        try:
            fid = rec['fixture_id']
            factors = rec.get('factors', {})
            existing = factors.get('time_bins', {})
            if any(float(v or 0) > 0 for v in existing.values()):
                continue

            # Get team IDs
            fix = api(f'fixtures?id={fid}')
            t = fix['response'][0]['teams']
            hid, aid = t['home']['id'], t['away']['id']

            htb, hsh, hn = recent_time_bins(hid)
            atb, ash, an = recent_time_bins(aid)

            # Merge
            merged = {}
            for k in htb:
                merged[k] = round((htb.get(k, 0) + atb.get(k, 0)) / 2, 3)
            merged_sh = {}
            for k in hsh:
                merged_sh[k] = round((hsh.get(k, 0) + ash.get(k, 0)) / 2, 3)

            l11 = merged.get('11_45', 0)
            eo = merged.get('0_10', 0) >= 0.5 and l11 < 0.5
            lfp = round(l11 * 0.55 + merged.get('16_45', 0) * 0.45, 3)
            pf = "STRONG" if lfp >= 0.70 and not eo else ("OK" if lfp >= 0.55 and not eo else "WEAK")

            factors['time_bins'] = merged
            factors['second_half_bins'] = merged_sh
            factors['recent_time_bins'] = merged
            factors['late_fh_pressure'] = lfp
            factors['recent_late_fh_pressure'] = lfp
            factors['pullback_fit'] = pf
            factors['recent_timing_fit'] = pf
            factors['early_only_flag'] = eo
            factors['recent_early_only_flag'] = eo

            patched += 1
            print(f'✅ [{i}] {rec["home"]} vs {rec["away"]} | 11_45={l11:.0%} pullback={pf} (n={hn}+{an})', flush=True)
        except Exception as e:
            print(f'❌ [{i}] {rec.get("home", "?")}: {str(e)[:80]}', flush=True)

    json.dump(scout, open(scout_path, 'w'), ensure_ascii=False, indent=2)
    print(f'\n🎉 Patched {patched}/23', flush=True)


if __name__ == '__main__':
    main()
