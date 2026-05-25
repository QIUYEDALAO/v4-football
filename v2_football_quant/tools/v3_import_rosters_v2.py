#!/usr/bin/env python3
"""V3 World Cup Roster Import v2 — corrected team IDs and API format."""
import os, json, urllib.request, time, sys

API_KEY = os.environ.get('OPENCLAW_APIFOOTBALL_KEY')
CST = "+08:00"

# Corrected team IDs for World Cup 2026
WC_TEAMS = {
    "Algeria": 1532, "Argentina": 26, "Australia": 20, "Austria": 775, "Belgium": 1,
    "Brazil": 6, "Cameroon": 1530, "Canada": 1717, "Chile": 1977, "Colombia": 8,
    "Costa Rica": 29, "Croatia": 3, "Denmark": 21, "Ecuador": 2382, "Egypt": 32,
    "England": 10, "France": 2, "Germany": 25, "Ghana": 1504, "Iran": 22,
    "Iraq": 1567, "Italy": 768, "Ivory Coast": 1501, "Jamaica": 1785, "Japan": 12,
    "Mexico": 16, "Morocco": 31, "Netherlands": 1118, "New Zealand": 4673, "Nigeria": 19,
    "Panama": 11, "Poland": 24, "Portugal": 27, "Qatar": 1569, "Saudi Arabia": 23,
    "Senegal": 13, "Serbia": 14, "South Korea": 17, "Spain": 9, "Switzerland": 15,
    "Tunisia": 28, "Turkey": 777, "USA": 1718, "Ukraine": 772, "Uruguay": 7,
    "Uzbekistan": 1568,
}

OUTPUT = "data/v3_worldcup/rosters/worldcup_rosters_20260526.json"
STATUS = "data/runtime/status/v3_roster_import_20260526.json"

def api_get(endpoint, params={}):
    qs = '&'.join(f'{k}={urllib.request.quote(str(v))}' for k,v in params.items())
    url = f'https://v3.football.api-sports.io/{endpoint}?{qs}'
    req = urllib.request.Request(url, headers={
        'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'
    })
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())

def classify_pos(pos):
    p = pos.lower()
    if 'goalkeeper' in p: return 'goalkeepers'
    if 'defender' in p: return 'defenders'
    if 'midfielder' in p: return 'midfielders'
    if 'attacker' in p or 'forward' in p: return 'forwards'
    return 'midfielders'  # default

all_rosters = {}
teams_ok, teams_empty, teams_fail = 0, 0, 0
missing_list, empty_list = [], []
total_players = 0

for team_name, team_id in sorted(WC_TEAMS.items()):
    try:
        data = api_get('players/squads', {'team': team_id})
        
        squad = {"goalkeepers":[],"defenders":[],"midfielders":[],"forwards":[],
                 "staff_notes":None,"missing_key_players":[],"injury_watch":[]}
        
        if not data.get('response'):
            teams_empty += 1
            empty_list.append(team_name)
            squad['staff_notes'] = "API returned empty squad"
            all_rosters[team_name] = squad
            continue
            
        for item in data['response']:
            for raw_player in item.get('players', []):
                pos = raw_player.get('position', 'Midfielder')
                group = classify_pos(pos)
                
                player = {
                    "team": team_name, "player_name": raw_player.get('name','?'),
                    "position": pos, "age": raw_player.get('age'),
                    "club": "UNKNOWN", "league": "UNKNOWN",
                    "caps": 0, "goals": 0, "season_minutes": 0,
                    "injury_status": "UNKNOWN",
                    "shirt_number": raw_player.get('number'),
                    "role_tag": "SQUAD", "is_projected_starter": False,
                    "is_core_player": False, "is_newcomer": False,
                    "is_surprise_pick": False, "is_key_absence": False,
                    "source": "apifootball v3 players/squads",
                    "source_date": "2026-05-25",
                    "confidence": "MEDIUM",
                    "notes": "Basic roster; caps/goals/minutes/club need supplement"
                }
                squad[group].append(player)
                total_players += 1
        
        all_rosters[team_name] = squad
        teams_ok += 1
        print(f"  ✅ {team_name}: {sum(len(squad[k]) for k in ['goalkeepers','defenders','midfielders','forwards'])} players")
        
    except Exception as e:
        teams_fail += 1
        missing_list.append(team_name)
        all_rosters[team_name] = {"goalkeepers":[],"defenders":[],"midfielders":[],"forwards":[],
                                  "staff_notes":f"FETCH_FAILED: {str(e)[:100]}",
                                  "missing_key_players":[],"injury_watch":[]}
        print(f"  ❌ {team_name}: {e}")
    
    time.sleep(0.6)

# Save
output = {
    "meta": {"version":"3.0.0","generated":"2026-05-25","source":"apifootball v3",
             "total_teams":len(WC_TEAMS),"teams_with_squad":teams_ok,
             "teams_empty":teams_empty,"teams_failed":teams_fail,
             "empty_list":empty_list,"failed_list":missing_list,
             "total_players":total_players,
             "note":"caps/goals/minutes/club need supplement from /players endpoint"},
    "rosters": all_rosters
}

with open(OUTPUT, 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

status = {"step":3,"step_name":"Import team rosters",
    "status":"WARN_ONLY",
    "total_teams":len(WC_TEAMS),"teams_with_squad":teams_ok,
    "teams_empty":teams_empty,"teams_failed":teams_fail,
    "empty_list":empty_list,"failed_list":missing_list,
    "total_players":total_players,
    "output":OUTPUT}

with open(STATUS, 'w') as f:
    json.dump(status, f, ensure_ascii=False, indent=2)

print(f"\n{'='*50}")
print(f"OK:{teams_ok} Empty:{teams_empty} Failed:{teams_fail} Total:{len(WC_TEAMS)}")
print(f"Players:{total_players}")
print(f"Empty:{empty_list}")
print(f"Failed:{missing_list}")
print(f"Status: {status['status']}")
