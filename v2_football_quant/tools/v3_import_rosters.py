#!/usr/bin/env python3
"""
V3 World Cup Roster Import
Fetches World Cup 2026 team rosters from Apifootball API.
"""
import os, json, urllib.request, urllib.parse, time, sys

API_KEY = os.environ.get('OPENCLAW_APIFOOTBALL_KEY')
if not API_KEY:
    print(json.dumps({"error": "NO_API_KEY"}))
    sys.exit(1)

# World Cup 2026 teams (48 teams) by Apifootball team IDs
# These need to be discovered via API; listed here are known IDs from responses
WC_TEAMS = {
    # Host nations
    "USA": 1540,
    "Canada": 5529,
    "Mexico": 16,
    # AFC
    "Japan": 12,
    "South Korea": 17,
    "Iran": 22,
    "Saudi Arabia": 23,
    "Australia": 20,
    "Qatar": 1848,
    "Uzbekistan": 12086,
    "Iraq": 1850,
    # CAF
    "Morocco": 31,
    "Senegal": 30,
    "Egypt": 32,
    "Nigeria": 19,
    "Algeria": 33,
    "Ivory Coast": 34,
    "Cameroon": 37,
    "Ghana": 35,
    "Tunisia": 36,
    # UEFA
    "France": 2,
    "Spain": 9,
    "Germany": 25,
    "England": 10,
    "Portugal": 27,
    "Netherlands": 7,
    "Italy": 13,
    "Belgium": 1,
    "Croatia": 3,
    "Denmark": 21,
    "Switzerland": 14,
    "Serbia": 24,
    "Austria": 775,
    "Poland": 28,
    "Ukraine": 26,
    "Turkey": 776,
    # CONMEBOL
    "Argentina": 11,
    "Brazil": 6,
    "Uruguay": 15,
    "Colombia": 8,
    "Chile": 29,
    "Ecuador": 1140,
    # CONCACAF
    "Costa Rica": 774,
    "Jamaica": 1775,
    "Panama": 1779,
    # OFC
    "New Zealand": 1851,
}

ROSTER_CACHE_DIR = "data/v3_worldcup/rosters"
OUTPUT_FILE = f"{ROSTER_CACHE_DIR}/worldcup_rosters_20260526.json"
STATUS_FILE = "data/runtime/status/v3_roster_import_20260526.json"

os.makedirs(ROSTER_CACHE_DIR, exist_ok=True)

def api_get(endpoint, params={}):
    """Call apifootball API."""
    qs = '&'.join(f'{k}={urllib.parse.quote(str(v))}' for k,v in params.items())
    url = f'https://v3.football.api-sports.io/{endpoint}?{qs}'
    req = urllib.request.Request(url, headers={
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    })
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())

def parse_player(raw):
    """Convert API player data to schema format."""
    player = raw['player']
    stats = raw.get('statistics', [{}])[0]
    
    return {
        "team": "",
        "player_name": player.get('name', '?'),
        "position": player.get('position', '?'),
        "age": player.get('age'),
        "club": stats.get('team', {}).get('name', '?'),
        "league": stats.get('league', {}).get('name', '?'),
        "caps": player.get('national', {}).get('caps', 0) or 0,
        "goals": player.get('national', {}).get('goals', 0) or 0,
        "season_minutes": stats.get('games', {}).get('minutes', 0) or 0,
        "injury_status": "UNKNOWN",
        "role_tag": "SQUAD",
        "is_projected_starter": False,
        "is_core_player": False,
        "is_newcomer": False,
        "is_surprise_pick": False,
        "is_key_absence": False,
        "source": "apifootball v3",
        "source_date": "2026-05-25",
        "confidence": "MEDIUM"
    }

all_rosters = {}
errors = []
total_players = 0
teams_collected = 0
teams_missing = []

for team_name, team_id in sorted(WC_TEAMS.items()):
    try:
        # Get squad
        data = api_get('players/squads', {'team': team_id})
        
        squad = {
            "goalkeepers": [],
            "defenders": [],
            "midfielders": [],
            "forwards": [],
            "staff_notes": None,
            "missing_key_players": [],
            "injury_watch": []
        }
        
        position_groups = {
            "Goalkeeper": "goalkeepers",
            "Defender": "defenders",
            "Midfielder": "midfielders",
            "Attacker": "forwards"
        }
        
        for raw in data.get('response', []):
            player = parse_player(raw)
            player['team'] = team_name
            
            pos = raw['player'].get('position', '?')
            group = position_groups.get(pos, 
                      "goalkeepers" if pos == "GK" else
                      "defenders" if pos in ("DEF","CB","LB","RB") else
                      "midfielders" if pos in ("MID","CDM","CM","CAM") else
                      "forwards")
            
            squad[group].append(player)
            total_players += 1
        
        all_rosters[team_name] = squad
        teams_collected += 1
        print(f"  ✅ {team_name}: {len(data.get('response',[]))} players")
        
        time.sleep(0.8)  # rate limit
        
    except Exception as e:
        print(f"  ❌ {team_name}: {e}")
        teams_missing.append(team_name)
        all_rosters[team_name] = {
            "goalkeepers": [], "defenders": [], "midfielders": [], "forwards": [],
            "staff_notes": f"FETCH_FAILED: {str(e)[:100]}",
            "missing_key_players": [],
            "injury_watch": []
        }

# Save
output = {
    "meta": {
        "version": "3.0.0",
        "generated": "2026-05-25",
        "source": "apifootball v3",
        "total_teams": len(WC_TEAMS),
        "teams_collected": teams_collected,
        "teams_missing": teams_missing,
        "total_players": total_players
    },
    "rosters": all_rosters
}

with open(OUTPUT_FILE, 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# Status
status = {
    "step": 3,
    "step_name": "Import team rosters",
    "status": "PASS" if teams_missing == [] else "WARN_ONLY",
    "total_teams": len(WC_TEAMS),
    "teams_collected": teams_collected,
    "teams_missing": teams_missing,
    "total_players": total_players,
    "output": OUTPUT_FILE
}
with open(STATUS_FILE, 'w') as f:
    json.dump(status, f, ensure_ascii=False, indent=2)

print(f"\n{'='*50}")
print(f"Total: {teams_collected}/{len(WC_TEAMS)} teams")
print(f"Players: {total_players}")
print(f"Missing: {teams_missing if teams_missing else 'NONE'}")
print(f"Output: {OUTPUT_FILE}")
print(f"Status: {status['status']}")
