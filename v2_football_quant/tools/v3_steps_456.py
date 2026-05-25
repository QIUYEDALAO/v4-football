#!/usr/bin/env python3
"""V3 World Cup — Steps 4-6: Roster Delta + Team Profiles + Perception Gap Watchlist"""
import json, os, random, sys
from datetime import datetime

CST = "+08:00"
ROSTER_FILE = "data/v3_worldcup/rosters/worldcup_rosters_20260526.json"
DELTA_FILE = "data/v3_worldcup/team_profiles/roster_delta_20260526.json"
PROFILE_FILE = "data/v3_worldcup/team_profiles/team_profiles_20260526.json"
PG_FILE = "data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json"

# ── Load roster data ──
with open(ROSTER_FILE) as f:
    rosters = json.load(f)['rosters']

# ── Step 4: Roster Delta Analysis ──
deltas = {}
for team_name, squad in rosters.items():
    # Count players by position
    gk = len(squad.get('goalkeepers', []))
    df = len(squad.get('defenders', []))
    mf = len(squad.get('midfielders', []))
    fw = len(squad.get('forwards', []))
    total = gk + df + mf + fw
    
    # Age analysis
    ages = []
    for pos_group in ['goalkeepers', 'defenders', 'midfielders', 'forwards']:
        for p in squad.get(pos_group, []):
            if p.get('age') is not None:
                ages.append(p['age'])
    
    avg_age = sum(ages) / len(ages) if ages else 0
    old_count = sum(1 for a in ages if a > 32)
    young_count = sum(1 for a in ages if a < 23)
    
    # Core stability: larger squads with balanced age = more stable
    core_stability = min(100, max(20, 70 - (old_count * 3) + (young_count * 1)))
    
    # Spine change: based on whether GK/DEF/MID/FW are all represented
    spine_change = 30 if gk >= 2 and df >= 6 and mf >= 5 and fw >= 3 else 60
    
    # Age risk: older players = higher risk
    age_risk = min(100, int(old_count / max(total, 1) * 100))
    
    # Injury risk estimate: placeholder until injury data available
    injury_risk = 25 if total >= 24 else 45
    
    # Depth score: more players = better depth
    depth_score = min(100, total * 3)
    
    # Key absence: placeholder until we identify key players
    key_absence_score = 30
    
    # Newcomer impact: placeholder until we identify newcomers
    newcomer_impact = 20
    
    deltas[team_name] = {
        "team": team_name,
        "core_stability_score": core_stability,
        "spine_change_score": spine_change,
        "age_risk_score": age_risk,
        "injury_risk_score": injury_risk,
        "depth_score": depth_score,
        "key_absence_score": key_absence_score,
        "newcomer_impact_score": newcomer_impact,
        "meta": {
            "total_players": total,
            "average_age": round(avg_age, 1),
            "gk_count": gk, "df_count": df, "mf_count": mf, "fw_count": fw,
            "players_over_32": old_count,
            "players_under_23": young_count
        }
    }

with open(DELTA_FILE, 'w') as f:
    json.dump({"meta":{"version":"3.0.0","generated":"2026-05-25","total_teams":len(deltas)},
               "deltas":deltas}, f, ensure_ascii=False, indent=2)
print(f"[Step 4] Roster delta: {len(deltas)} teams ✅")

# ── Step 5: Team Profiles ──
def estimate_attack(team, squad):
    fw = squad.get('forwards', [])
    ages = [(p.get('age') or 25) for p in fw]
    count = len(fw)
    avg = sum(ages)/len(ages) if ages else 25
    if count >= 5 and avg < 29: return "STRONG — deep young forward line"
    if count >= 4: return "ADEQUATE — sufficient attacking options"
    return "THIN — limited forward depth"

def estimate_defense(team, squad):
    df = squad.get('defenders', [])
    count = len(df)
    if count >= 8: return "SOLID — deep defensive unit"
    if count >= 6: return "ADEQUATE — standard defensive depth"
    return "THIN — vulnerable to injuries"

def estimate_midfield(team, squad):
    mf = squad.get('midfielders', [])
    count = len(mf)
    if count >= 8: return "DOMINANT — midfield control depth"
    if count >= 6: return "BALANCED — adequate midfield options"
    return "LIGHT — limited midfield rotation"

def estimate_gk(team, squad):
    gk = squad.get('goalkeepers', [])
    count = len(gk)
    if count >= 3: return "DEEP — three goalkeepers"
    if count == 2: return "STANDARD — starter + backup"
    return "RISKY — single goalkeeper listed"

def estimate_bench(team, squad):
    total = sum(len(squad.get(k,[])) for k in ['goalkeepers','defenders','midfielders','forwards'])
    if total >= 28: return "EXCELLENT — full competitive squad"
    if total >= 24: return "ADEQUATE — standard tournament squad"
    if total >= 20: return "MODERATE — manageable depth"
    return "SHALLOW — injury-prone roster"

# Public narratives (based on commonly known team reputations)
PUBLIC_NARRATIVES = {
    "Argentina": "Defending champions, Messi's final dance — heavy public expectation",
    "Brazil": "Always favorites, Neymar era closing — public expects finals",
    "France": "Mbappé's team, deepest talent pool — expected semifinals minimum",
    "England": "Golden generation pressure — public expects breakthrough",
    "Germany": "Rebuilding after disappointments — narrative of redemption",
    "Spain": "Young core, beautiful football — public optimism",
    "Portugal": "Ronaldo farewell tour? — high expectations",
    "Netherlands": "Always talented, never champions — cautious optimism",
    "Italy": "Euro champions collapse — redemption narrative",
    "Belgium": "Golden generation fading — last chance narrative",
    "Argentina": "Messi's leadership — defending champions swagger",
    "Croatia": "Modric's last World Cup — overachiever narrative",
    "Morocco": "2022 semifinal heroes — expectations inflated",
    "USA": "Home advantage — public expects quarterfinal breakthrough",
    "Mexico": "Fifth game curse — desperation narrative",
    "Canada": "Davies leads — first World Cup as host, no pressure",
    "Japan": "Asian power rising — quarterfinal ambition",
    "South Korea": "Son's team — knockout round ambitions",
    "Saudi Arabia": "2022 Argentina upset — belief in miracles",
    "Senegal": "Mane's legacy — African champion ambitions",
    "Uruguay": "Bielsa's project — counter-attacking threat",
}

# Hidden strengths/weaknesses (to be refined with data)
HIDDEN_STRENGTHS = {
    "Argentina": "Tournament experience — know how to win ugly",
    "Brazil": "Incredible attacking depth beyond starting XI",
    "France": "Physical dominance + pace in every position",
    "England": "Set piece threat + young fearless attackers",
    "Germany": "Tournament pedigree + never write them off",
    "Spain": "Possession control — can strangle any opponent",
    "Portugal": "Tactical flexibility + elite bench",
    "Netherlands": "System cohesion — everyone knows their role",
    "Italy": "Defensive organization + counter-attack threat",
    "Belgium": "Individual brilliance can overcome tactical flaws",
    "Croatia": "Midfield control + extra-time specialists",
    "Morocco": "Home crowd advantage (regional proximity)",
    "Japan": "Pressing intensity + tactical discipline",
    "South Korea": "Counter-attack speed + Son individual threat",
    "Uruguay": "New generation + Bielsa intensity",
    "USA": "Home advantage + physically dominant",
    "Ecuador": "Altitude conditioning + youthful energy",
    "Senegal": "Physical profile + European experience",
    "Serbia": "Set piece dominance + aerial threat",
}

HIDDEN_WEAKNESSES = {
    "Argentina": "Aging core — if Messi/Di Maria slow down",
    "Brazil": "Defensive organization under sustained pressure",
    "France": "Midfield chemistry after Pogba-era transition",
    "England": "Tactical inflexibility under Southgate",
    "Germany": "Striker position still not settled",
    "Spain": "Lack of clinical finisher — possession without penetration",
    "Portugal": "Ronaldo conundrum — build around him or past him",
    "Netherlands": "Lack of world-class striker",
    "Italy": "Missing 2022 momentum — tournament gap",
    "Belgium": "Aging defense — pace vulnerability",
    "Croatia": "Aging core — Modric/Brozovic succession gap",
    "Morocco": "Offensive creativity without home crowd boost",
    "Japan": "Physical disadvantage against elite teams",
    "South Korea": "Defensive organization beyond Kim Min-jae",
    "Uruguay": "Transition period — Bielsa system still settling",
    "USA": "Lack of tournament experience at elite level",
    "Ecuador": "Inconsistent away from altitude",
    "Senegal": "Mane dependency — creativity beyond him",
    "Serbia": "Defensive vulnerability against pace",
}

profiles = {}
for team_name, squad in rosters.items():
    nar = PUBLIC_NARRATIVES.get(team_name, f"{team_name}: data pending")
    hs = HIDDEN_STRENGTHS.get(team_name, "Analysis pending — need detailed scouting")
    hw = HIDDEN_WEAKNESSES.get(team_name, "Analysis pending — need detailed scouting")
    
    profiles[team_name] = {
        "team": team_name,
        "attack_profile": estimate_attack(team_name, squad),
        "defense_profile": estimate_defense(team_name, squad),
        "transition_profile": "ANALYSIS_PENDING",
        "set_piece_profile": "ANALYSIS_PENDING",
        "midfield_control": estimate_midfield(team_name, squad),
        "goalkeeper_reliability": estimate_gk(team_name, squad),
        "bench_depth": estimate_bench(team_name, squad),
        "tactical_risk": "LOW" if deltas[team_name]['core_stability_score'] > 60 else "MEDIUM",
        "public_narrative": nar,
        "hidden_strength": hs,
        "hidden_weakness": hw
    }

with open(PROFILE_FILE, 'w') as f:
    json.dump({"meta":{"version":"3.0.0","generated":"2026-05-25","total_teams":len(profiles)},
               "profiles":profiles}, f, ensure_ascii=False, indent=2)
print(f"[Step 5] Team profiles: {len(profiles)} teams ✅")

# ── Step 6: Perception Gap Watchlist ──
# Identify teams where public expectation might diverge from roster reality
watchlist = []

for team_name, delta in deltas.items():
    stab = delta['core_stability_score']
    age_risk = delta['age_risk_score']
    depth = delta['depth_score']
    
    # PG rules
    if stab < 50 and age_risk > 40:
        gap = "WATCHLIST"
        reason = "Low stability + high age risk — public may overrate"
    elif stab > 75 and depth > 70:
        gap = "WATCHLIST"
        reason = "High stability + depth — public may underrate squad readiness"
    elif age_risk > 50:
        gap = "PG_HIGH"
        reason = "Very high age risk — aging squad may underperform expectations"
    elif stab < 40:
        gap = "PG_HIGH"
        reason = "Very low squad stability — major turnover risk"
    elif stab > 70:
        gap = "PG_MEDIUM"
        reason = "Stable squad — consistent performance likely"
    else:
        gap = "PG_LOW"
        reason = "Moderate stability — no obvious perception gap"
    
    direction = "OVERRATED" if age_risk > 35 or stab < 45 else ("UNDERRATED" if stab > 70 and depth > 60 else "ALIGNED")
    
    watchlist.append({
        "team": team_name,
        "public_expectation": PUBLIC_NARRATIVES.get(team_name, "DATA_PENDING"),
        "roster_reality": f"Stability:{stab} AgeRisk:{age_risk} Depth:{depth} AvgAge:{delta['meta']['average_age']}",
        "gap_direction": direction,
        "gap_level": gap,
        "reason": reason,
        "confidence": "LOW" if delta['meta']['total_players'] < 23 else "MEDIUM",
        "next_required_data": "caps/goals/club data, injury status, pre-tournament friendlies"
    })

with open(PG_FILE, 'w') as f:
    json.dump({"meta":{"version":"3.0.0","generated":"2026-05-25","total_teams":len(watchlist),
                       "note":"WATCHLIST ONLY — NO BETTING RECOMMENDATIONS"},
               "watchlist":watchlist}, f, ensure_ascii=False, indent=2)
print(f"[Step 6] Perception Gap watchlist: {len(watchlist)} teams ✅")

# Summary
pg_counts = {}
for w in watchlist:
    lvl = w['gap_level']
    pg_counts[lvl] = pg_counts.get(lvl, 0) + 1

print(f"\n  PG_HIGH: {pg_counts.get('PG_HIGH',0)}")
print(f"  PG_MEDIUM: {pg_counts.get('PG_MEDIUM',0)}")
print(f"  PG_LOW: {pg_counts.get('PG_LOW',0)}")
print(f"  WATCHLIST: {pg_counts.get('WATCHLIST',0)}")
print(f"  SKIP: {pg_counts.get('SKIP',0)}")
print(f"\n  ⚠️ ZERO betting recommendations — WATCHLIST only.")
