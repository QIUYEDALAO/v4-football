#!/usr/bin/env python3
"""pre_match_reminder.py — macOS 赛前5分钟弹窗提醒

读取最新 V4 扫描简报中的 A/B 比赛列表，
在赛前5分钟弹一次「⚽ A/B级 即将开赛」，
开赛后5分钟内弹一次「🔴 A/B级 已开赛」。

由 crontab 每2分钟调用一次。
"""

import glob, json, os, subprocess, sys, re
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTIFIED_FILE = os.path.expanduser("~/.openclaw/v4_notified.json")


def find_latest_brief():
    """Find the latest V4 brief QQ file from data/daily_reports."""
    brief_dir = os.path.join(WORKSPACE, "v2_football_quant", "data", "daily_reports")
    files = sorted(glob.glob(os.path.join(brief_dir, "v4_openclaw_brief_qq_2026*.txt")))
    if not files:
        # Fallback to corrected version
        files = sorted(glob.glob(os.path.join(brief_dir, "v4_openclaw_brief_qq_2026*_corrected*.txt")))
    if not files:
        print("no brief file found")
        sys.exit(1)
    text = open(files[-1]).read()
    
    matches = []
    lines = text.split('\n')
    current = None
    
    for line in lines:
        # Match A/B entries: "1. TeamA vs TeamB｜League｜kickoff"
        m = re.match(r'\d+\.\s*(.+?)\s+vs\s+(.+?)\s*[｜|]\s*(.+?)\s*[｜|]\s*(\d{2}-\d{2}\s+\d{2}:\d{2})', line)
        if m:
            home = m.group(1).strip()
            away = m.group(2).strip()
            league = m.group(3).strip()
            kickoff = m.group(4).strip()
            # Determine grade from context (lines above)
            current = {
                'fid': hash(home + away + kickoff) & 0x7FFFFFFF,
                'grade': '?',
                'home': home,
                'away': away,
                'league': league,
                'kickoff_raw': kickoff,
            }
            continue
        
        # Check for grade info in "等级：A" or "HTxx" lines
        if current:
            gm = re.search(r'等级：([AB])', line)
            if gm:
                current['grade'] = gm.group(1)
            sm = re.search(r'HT(\d+)', line)
            if sm:
                current['ht_score'] = sm.group(1)
            rm = re.search(r'(\d+)%', line)
            if rm and 'HT率' not in str(current.get('ht_rate', '')):
                current['ht_rate'] = rm.group(1)
            
            # At next separator or empty line, finalize
            if line.startswith('━') or line.strip() == '':
                if current and current.get('home'):
                    matches.append(current)
                current = None
    
    # Also parse corrected_v2 format with @① prefix
    for block in text.split('━' * 10):
        if '等级：A' in block or '等级：B' in block:
            tm = re.search(r'(.+?) vs (.+?)\n', block)
            gm = re.search(r'等级：([AB])', block)
            lm = re.search(r'联赛：(.+?)[｜|]', block)
            tim = re.search(r'开赛：(\d{2}-\d{2} \d{2}:\d{2})', block)
            sm = re.search(r'HT(\d+)', block)
            rm = re.search(r'(\d+)%', block)
            if tm and gm:
                kickoff_str = tim.group(1) if tim else '?'
                matches.append({
                    'fid': hash(tm.group(1).strip() + tm.group(2).strip() + kickoff_str) & 0x7FFFFFFF,
                    'grade': gm.group(1),
                    'home': tm.group(1).strip(),
                    'away': tm.group(2).strip(),
                    'league': lm.group(1) if lm else '?',
                    'kickoff_raw': kickoff_str,
                    'ht_score': sm.group(1) if sm else '?',
                    'ht_rate': rm.group(1) if rm else '?',
                })
    
    return matches


def notify(title, msg):
    # Use AppleScript (more reliable, works even in Do Not Disturb if configured)
    try:
        escaped_msg = msg.replace('"', '\\"')
        escaped_title = title.replace('"', '\\"')
        script = f'display notification "{escaped_msg}" with title "{escaped_title}" sound name "default"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception:
        pass
    # Fallback: terminal-notifier
    try:
        subprocess.run(["terminal-notifier", "-title", title, "-message", msg,
                        "-sound", "default", "-group", "v4-reminder", "-timeout", "5"],
                       capture_output=True, timeout=5)
    except Exception:
        pass
    print(f"  {title}: {msg}")


def load_notified():
    if os.path.exists(NOTIFIED_FILE):
        try:
            return set(json.load(open(NOTIFIED_FILE)))
        except Exception:
            pass
    return set()


def main():
    data = find_latest_brief()
    if not data:
        print("pre_match | 0 A/B matches parsed")
        return
    
    print(f"pre_match | {len(data)} A/B matches")
    now = datetime.now(TZ)
    notified = load_notified()
    new_notified = set()
    cnt = 0

    for m in data:
        kstr = m.get('kickoff_raw', '?')
        if '?' in str(kstr) or kstr == '?':
            continue
        # Parse "05-17 19:30" → datetime
        try:
            parts = kstr.split(' ')
            md = parts[0]  # "05-17"
            hr = parts[1]  # "19:30"
            mo, da = md.split('-')
            hh, mm = hr.split(':')
            kt = datetime(2026, int(mo), int(da), int(hh), int(mm), tzinfo=TZ)
        except Exception:
            continue
        
        if kt < now:
            continue  # already started
        
        dm = (kt - now).total_seconds() / 60
        fid = m['fid']
        home, away = m['home'], m['away']
        gr = m.get('grade', '?')
        sc = m.get('ht_score', '?')
        rt = m.get('ht_rate', '?')
        lg = m.get('league', '?')

        # 赛前5分钟弹一次
        if 4 <= dm <= 6 and fid not in notified:
            notify(f"⚽ {gr}级 即将开赛",
                   f"{home} vs {away}\n{lg} | 评分：HT{sc} | HT率：{rt}%")
            new_notified.add(fid)
            cnt += 1

        # 开赛后5分钟内弹一次
        elif -1 <= dm <= 5:
            km = f"{fid}_ko"
            if km not in notified:
                notify(f"🔴 {gr}级 已开赛",
                       f"{home} vs {away} | {kt.strftime('%H:%M')}开球 | 上半场进行中")
                new_notified.add(km)
                cnt += 1

    # 清理已过期记录
    keep = set()
    for item in notified:
        if isinstance(item, str) and str(item).endswith('_ko'):
            keep.add(item)
        elif isinstance(item, int):
            for m in data:
                if m['fid'] == item:
                    try:
                        parts = m['kickoff_raw'].split(' ')
                        mo, da = parts[0].split('-')
                        hh, mm = parts[1].split(':')
                        kt = datetime(2026, int(mo), int(da), int(hh), int(mm), tzinfo=TZ)
                        if kt > now - timedelta(hours=2):
                            keep.add(item)
                    except Exception:
                        pass
                    break
    
    save_set = keep | new_notified
    os.makedirs(os.path.dirname(NOTIFIED_FILE), exist_ok=True)
    json.dump(list(save_set), open(NOTIFIED_FILE, 'w'))
    print(f"  notified: {cnt}, saved: {len(save_set)}")


if __name__ == "__main__":
    main()
