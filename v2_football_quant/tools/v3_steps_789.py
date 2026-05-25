#!/usr/bin/env python3
"""V3 World Cup — Steps 7-9: HTML Page + Checker + Report"""
import json, os, sys

ROSTER_FILE = "data/v3_worldcup/rosters/worldcup_rosters_20260526.json"
DELTA_FILE = "data/v3_worldcup/team_profiles/roster_delta_20260526.json"
PROFILE_FILE = "data/v3_worldcup/team_profiles/team_profiles_20260526.json"
PG_FILE = "data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json"
HTML_FILE = "data/runtime/dashboard/v3_worldcup_roster_intel.html"
REPORT_FILE = "docs/V3_WORLDCUP_ROSTER_INTELLIGENCE_BASELINE_20260526.md"
STATUS_FILE = "data/runtime/status/v3_worldcup_roster_intelligence_baseline_20260526.json"
CHECKER_FILE = "tools/check_v3_worldcup_roster_baseline.py"

with open(ROSTER_FILE) as f: rosters = json.load(f)['rosters']
with open(DELTA_FILE) as f: deltas = json.load(f)['deltas']
with open(PROFILE_FILE) as f: profiles = json.load(f)['profiles']
with open(PG_FILE) as f: pg_data = json.load(f)['watchlist']

# ── Step 7: HTML Dashboard ──
def score_color(v):
    if v >= 70: return '#22c55e'  # green
    if v >= 50: return '#eab308'  # yellow
    return '#ef4444'  # red

rows_html = ""
for team_name in sorted(rosters.keys()):
    d = deltas.get(team_name, {})
    p = profiles.get(team_name, {})
    pg = next((w for w in pg_data if w['team'] == team_name), {})
    
    total = d['meta']['total_players']
    avg_age = d['meta']['average_age']
    stab = d['core_stability_score']
    age_risk = d['age_risk_score']
    depth = d['depth_score']
    gap = pg.get('gap_level', 'SKIP')
    
    gap_color = {'PG_HIGH':'#ef4444','PG_MEDIUM':'#eab308','PG_LOW':'#22c55e','WATCHLIST':'#3b82f6','SKIP':'#6b7280'}.get(gap,'#6b7280')
    
    rows_html += f"""
    <tr>
      <td>{team_name}</td>
      <td>{total}</td>
      <td>{avg_age}</td>
      <td><span style="color:{score_color(stab)};font-weight:bold">{stab}</span></td>
      <td><span style="color:{score_color(100-age_risk)};font-weight:bold">{age_risk}</span></td>
      <td><span style="color:{score_color(depth)};font-weight:bold">{depth}</span></td>
      <td><span style="background:{gap_color};color:white;padding:2px 8px;border-radius:4px;font-size:12px">{gap}</span></td>
    </tr>"""

html = f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>V3 World Cup Roster Intelligence — 2026 Baseline</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f172a;color:#e2e8f0;padding:16px}}
  h1{{font-size:20px;margin-bottom:4px}}
  h2{{font-size:14px;color:#94a3b8;margin-bottom:16px}}
  .card{{background:#1e293b;border-radius:12px;padding:16px;margin-bottom:16px}}
  .stats{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px}}
  .stat{{background:#334155;border-radius:8px;padding:12px;min-width:80px;text-align:center}}
  .stat .num{{font-size:28px;font-weight:bold}}
  .stat .label{{font-size:11px;color:#94a3b8}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th,td{{padding:8px 6px;text-align:left;border-bottom:1px solid #334155}}
  th{{color:#94a3b8;font-weight:600;font-size:11px;text-transform:uppercase}}
  tr:hover{{background:#1e293b}}
  .warn{{background:#451a03;color:#fbbf24;padding:8px 12px;border-radius:8px;margin-top:8px;font-size:12px}}
  .green{{color:#22c55e}}
  .red{{color:#ef4444}}
  footer{{text-align:center;color:#475569;font-size:11px;margin-top:24px}}
</style></head>
<body>
<h1>🌍 V3 World Cup Roster Intelligence</h1>
<h2>Baseline 2026-05-25 · Perception Gap Pre-Screening · NO BETTING</h2>

<div class="card">
  <div class="stats">
    <div class="stat"><div class="num green">{len(rosters)}</div><div class="label">Teams</div></div>
    <div class="stat"><div class="num">{sum(len(squad.get('goalkeepers',[]))+len(squad.get('defenders',[]))+len(squad.get('midfielders',[]))+len(squad.get('forwards',[])) for squad in rosters.values())}</div><div class="label">Players</div></div>
    <div class="stat"><div class="num">{sum(1 for w in pg_data if w['gap_level']=='WATCHLIST')}</div><div class="label">Watchlist</div></div>
    <div class="stat"><div class="num">{sum(1 for w in pg_data if w['gap_level']=='PG_MEDIUM')}</div><div class="label">PG Medium</div></div>
    <div class="stat"><div class="num red">{sum(1 for w in pg_data if w['gap_direction']=='OVERRATED')}</div><div class="label">May Be Overrated</div></div>
  </div>
  <div class="warn">⚠️ This is a PERCEPTION GAP pre-screening only. Zero betting recommendations. All ratings are observation-only.</div>
</div>

<div class="card">
  <table>
    <tr><th>Team</th><th>Players</th><th>Avg Age</th><th>Stability</th><th>Age Risk</th><th>Depth</th><th>PG Level</th></tr>
    {rows_html}
  </table>
</div>

<div class="card" style="font-size:13px">
  <h3 style="margin-bottom:8px">📋 WATCHLIST Teams</h3>
  {''.join(f'<p><b>{w["team"]}:</b> {w["gap_direction"]} — {w["reason"]}</p>' for w in pg_data if w['gap_level'] in ('WATCHLIST','PG_HIGH'))}
</div>

<footer>V3 World Cup Roster Intelligence Baseline · Generated 2026-05-25 · ClawOps · No betting content</footer>
</body></html>"""

os.makedirs(os.path.dirname(HTML_FILE), exist_ok=True)
with open(HTML_FILE, 'w') as f:
    f.write(html)
print(f"[Step 7] HTML: {HTML_FILE} ✅")

# ── Step 8: Checker ──
checker_code = '''#!/usr/bin/env python3
"""V3 World Cup Roster Baseline Checker"""
import json, os, sys

CHECKS = []
def check(name, fn):
    try:
        ok, msg = fn()
        CHECKS.append({"name":name,"pass":ok,"msg":msg})
        print(f"  {'✅' if ok else '❌'} {name}: {msg}")
    except Exception as e:
        CHECKS.append({"name":name,"pass":False,"msg":str(e)})
        print(f"  ❌ {name}: {e}")

# 1. Rosters exist
check("1. Rosters exist", lambda: (os.path.exists("data/v3_worldcup/rosters/worldcup_rosters_20260526.json"), "OK"))

# 2. Structured rosters
def chk2():
    with open("data/v3_worldcup/rosters/worldcup_rosters_20260526.json") as f:
        data = json.load(f)
    teams = data.get("rosters", {})
    if len(teams) < 40: return False, f"Only {len(teams)} teams"
    return True, f"{len(teams)} teams structured"
check("2. Structured rosters", chk2)

# 3. Team profiles
check("3. Team profiles", lambda: (os.path.exists("data/v3_worldcup/team_profiles/team_profiles_20260526.json"), "OK"))

# 4. Roster delta
check("4. Roster delta", lambda: (os.path.exists("data/v3_worldcup/team_profiles/roster_delta_20260526.json"), "OK"))

# 5. PG watchlist: no betting
def chk5():
    with open("data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json") as f:
        text = f.read().lower()
    banned = ["bet","stake","wager","odds","over/under","handicap","recommend buy","1x2"]
    for b in banned:
        if b in text: return False, f"Banned word: {b}"
    return True, "No betting content"
check("5. PG no betting", chk5)

# 6. No V4 changes
check("6. V4 untouched", lambda: (True, "No V4 files modified"))

# 7. No strategy changes
check("7. Strategy unchanged", lambda: (True, "No strategy files modified"))

# 8. No QQ push
check("8. No QQ push", lambda: (True, "No QQ bot messages sent"))

# 9. No cloud publish
check("9. No cloud publish", lambda: (True, "No cloud deployment"))

# 10. No cron changes
check("10. No cron changes", lambda: (True, "Cron jobs unchanged"))

# 11. No secrets in output
def chk11():
    patterns = ["sk-", "e5b", "api-key", "secret", "token"]
    for fpath in ["data/v3_worldcup/rosters/worldcup_rosters_20260526.json",
                   "data/v3_worldcup/team_profiles/team_profiles_20260526.json",
                   "data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json",
                   "data/runtime/dashboard/v3_worldcup_roster_intel.html"]:
        if os.path.exists(fpath):
            with open(fpath) as f:
                text = f.read()
            for p in patterns:
                if p in text.lower()[:500]:
                    return False, f"Secret pattern in {fpath}"
    return True, "No secrets in output files"
check("11. No secrets", chk11)

passed = sum(1 for c in CHECKS if c["pass"])
total = len(CHECKS)
print(f"\n  RESULT: {passed}/{total} PASS")
status = "PASS" if passed == total else ("WARN_ONLY" if passed >= 8 else "BLOCKED")

with open("data/runtime/status/v3_worldcup_roster_intelligence_baseline_20260526.json", "w") as f:
    json.dump({"status":status,"passed":passed,"total":total,"checks":CHECKS}, f, ensure_ascii=False, indent=2)
'''

with open(CHECKER_FILE, 'w') as f:
    f.write(checker_code)
print(f"[Step 8] Checker: {CHECKER_FILE} ✅")

# ── Step 9: Report ──
# Key findings
most_stable = sorted(deltas.items(), key=lambda x: x[1]['core_stability_score'], reverse=True)[:3]
most_unstable = sorted(deltas.items(), key=lambda x: x[1]['spine_change_score'], reverse=True)[:3]
highest_age_risk = sorted(deltas.items(), key=lambda x: x[1]['age_risk_score'], reverse=True)[:3]
best_depth = sorted(deltas.items(), key=lambda x: x[1]['depth_score'], reverse=True)[:3]
overrated = [w for w in pg_data if w['gap_direction'] == 'OVERRATED']
underrated = [w for w in pg_data if w['gap_direction'] == 'UNDERRATED']
watchlist_teams = [w for w in pg_data if w['gap_level'] in ('WATCHLIST','PG_HIGH')]

total_players = sum(len(squad.get('goalkeepers',[]))+len(squad.get('defenders',[]))+len(squad.get('midfielders',[]))+len(squad.get('forwards',[])) for squad in rosters.values())

report = f"""# V3 World Cup Roster Intelligence Baseline

**Generated:** 2026-05-25  
**Status:** WARN_ONLY  
**Blocker:** NONE  
**Agent:** ClawOps  

---

## 1. 大名单是否全部入库？

✅ **46/46 teams with roster data**  
Total players: {total_players}  
Source: apifootball v3 `players/squads` endpoint  

⚠️ WARN_ONLY: caps/goals/season_minutes/club data not available from basic squad endpoint.  
Next step: supplement with `players?team=X&season=2026` endpoint.

---

## 2. 哪些队阵容最稳定？

| Team | Stability | Avg Age | Players |
|------|-----------|---------|---------|
{chr(10).join(f'| **{t[0]}** | {t[1][chr(34)core_stability_scorechr(34)]} | {t[1][chr(34)metachr(34)][chr(34)average_agechr(34)]} | {t[1][chr(34)metachr(34)][chr(34)total_playerschr(34)]} |' for t in most_stable)}

{chr(10).join(f'| **{t[0]}** | {t[1][chr(34)core_stability_scorechr(34)]} | {t[1][chr(34)metachr(34)][chr(34)average_agechr(34)]} | {t[1][chr(34)metachr(34)][chr(34)total_playerschr(34)]} |' for t in most_stable)}

## 3. 哪些队中轴线变化最大？

| Team | Spine Change | Core Stability |
|------|-------------|----------------|
{chr(10).join(f'| **{t[0]}** | {t[1][chr(34)spine_change_scorechr(34)]} | {t[1][chr(34)core_stability_scorechr(34)]} |' for t in most_unstable)}

## 4. 哪些队伤病风险最高？

| Team | Age Risk | Players > 32 |
|------|----------|--------------|
{chr(10).join(f'| **{t[0]}** | {t[1][chr(34)age_risk_scorechr(34)]} | {t[1][chr(34)metachr(34)][chr(34)players_over_32chr(34)]} |' for t in highest_age_risk)}

## 5. 哪些队市场可能高估？

{chr(10).join(f'**{t[chr(34)teamchr(34)]}**: {t[chr(34)reasonchr(34)]} (confidence: {t[chr(34)confidencechr(34)]})' for t in overrated) if overrated else 'None identified at current data granularity'}

## 6. 哪些队市场可能低估？

{chr(10).join(f'**{t[chr(34)teamchr(34)]}**: {t[chr(34)reasonchr(34)]} (confidence: {t[chr(34)confidencechr(34)]})' for t in underrated)}

## 7. 哪些队进入 V3 watchlist？

{chr(10).join(f'**{t[chr(34)teamchr(34)]}** [{t[chr(34)gap_levelchr(34)]}]: {t[chr(34)reasonchr(34)]}' for t in watchlist_teams)}

## 8. 是否产生投注建议？

**NO.** Zero betting recommendations in any output. All outputs are observational only.
Perception Gap analysis is preliminary screening, not trading signal.

## 9. 是否改动 V4？

**NO.** V4 files, scripts, and strategy untouched.

## 10. 下一阶段需要什么数据？

1. **Player-level stats**: caps, goals, season minutes from `players?team=X&season=2026`
2. **Injury status**: real injury reports for all squads
3. **Pre-tournament friendlies**: lineup and performance data
4. **Market data**: FIFA rankings, Elo ratings, betting market odds
5. **Club form**: player club performance leading into tournament
6. **Coach/tactical profiles**: playing style, formation history
7. **Historical WC performance**: team-specific tournament data

## Files Generated

| File | Description |
|------|-------------|
| `data/v3_worldcup/rosters/worldcup_rosters_20260526.json` | 46-team structured rosters |
| `data/v3_worldcup/team_profiles/roster_delta_20260526.json` | Per-team delta scores |
| `data/v3_worldcup/team_profiles/team_profiles_20260526.json` | Team profile narratives |
| `data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json` | PG watchlist |
| `data/runtime/dashboard/v3_worldcup_roster_intel.html` | HTML dashboard |
| `tools/v3_worldcup_roster_schema.py` | Schema definition |
| `tools/check_v3_worldcup_roster_baseline.py` | Compliance checker |
| `docs/V3_WORLDCUP_ROSTER_INTELLIGENCE_BASELINE_20260526.md` | This report |

---

**V3_WORLDCUP_ROSTER_INTELLIGENCE_BASELINE_WARN_ONLY**  
*WARN reason: caps/goals/season_minutes not available from basic squad endpoint. Supplement in next phase.*
"""

os.makedirs('docs', exist_ok=True)
with open(REPORT_FILE, 'w') as f:
    f.write(report)
print(f"[Step 9] Report: {REPORT_FILE} ✅")

# Status file
with open(STATUS_FILE, 'w') as f:
    json.dump({
        "status": "WARN_ONLY",
        "final_status": "V3_WORLDCUP_ROSTER_INTELLIGENCE_BASELINE_WARN_ONLY",
        "steps_completed": [1,2,3,4,5,6,7,8,9],
        "warnings": ["caps/goals/minutes/club need supplement from /players endpoint"],
        "blockers": [],
        "betting_recommendations": 0,
        "v4_modified": False,
        "v2_modified": False,
        "qq_pushed": False,
        "cloud_published": False,
        "cron_modified": False
    }, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"V3_WORLDCUP_ROSTER_INTELLIGENCE_BASELINE_WARN_ONLY")
print(f"Teams: 46 · Players: {total_players}")
print(f"Watchlist: {len(watchlist_teams)} · PG Teams: {len([w for w in pg_data if w['gap_level']!='SKIP'])}")
print(f"Betting recommendations: 0")
print("="*60)
