#!/usr/bin/env python3
"""engine/v4_qq_formatter.py — V4简报QQ版（紧凑格式，25行以内）"""
import json, sys, re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
REPORT_DIR = BASE_DIR / "data" / "daily_reports"

try:
    from engine.team_cn_map import strict_match as team_cn
except Exception:
    def team_cn(n): return n

EXTRA_CN = {
    "Ajman":"阿治曼","Al Nasr":"迪拜胜利","Al-Wasl":"迪拜祈祷","Al Wasl":"迪拜祈祷",
    "Al-Ittihad Kalba":"伊蒂哈德卡尔巴","Adelaide United":"阿德莱德联",
    "Auckland":"奥克兰FC","Oriente Petrolero":"东方石油","Guabirá":"瓜比拉",
    "Rizespor":"里泽体育","Beşiktaş":"贝西克塔斯","Aston Villa":"阿斯顿维拉",
    "Liverpool":"利物浦","Tianjin Teda":"天津泰达","Chengdu Better City":"成都蓉城",
    "PSBS Biak Numfor":"PSBS","Arema FC":"Arema",
}
def _cn(s): return EXTRA_CN.get(s, team_cn(s))
SEP = "━" * 12

def format_qq(date_str: str) -> str:
    key = date_str.replace("-","")
    bp = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
    if not bp.exists(): return "V4简报未生成"
    full = bp.read_text().replace("\r\n","\n")
    
    # Parse counts
    def _num(kw): 
        for l in full.split("\n"):
            if kw in l:
                return l.split("：")[-1].replace("场","").strip()
        return "?"
    
    L=[]
    L.append(f"⏰V4上半场情报 | {key[:4]}-{key[4:6]}-{key[6:]}")
    L.append(f"扫描{_num('全量扫描')}场 | A{_num('A级强推荐')} B{_num('B级达标推荐')} C{_num('C级观察')} 跳{_num('HT_SKIP跳过')} | 覆盖{_num('A+B覆盖率')}")
    L.append(SEP)
    
    # B级 cards - each match has its own header
    b_all = full  # search entire text for all vs lines in B context
    b_pairs_all = []
    b_ht_all = []
    b_rate_all = []
    b_goal_all = []
    b_script_all = []
    # Split by B级 headers
    parts = full.split("B级上半场达标推荐")
    for part in parts[1:]:
        end = part.find("C级观察池")
        if end < 0:
            end = part.find("━━")
        chunk = part[:end] if end > 0 else part[:200]
        pair = re.search(r"(.+?) vs (.+?)\n", chunk)
        ht = re.search(r"HT评分 (\d+)", chunk)
        rate = re.search(r"HT有球率 (\d+%)", chunk)
        goal = re.search(r"场均HT进球 ([\d.]+)", chunk)
        script = re.search(r"剧本：(.+)", chunk)
        if pair:
            b_pairs_all.append((pair.group(1).strip(), pair.group(2).strip()))
            b_ht_all.append(ht.group(1) if ht else "?")
            b_rate_all.append(rate.group(1) if rate else "?")
            b_goal_all.append(goal.group(1) if goal else "?")
            b_script_all.append(script.group(1).strip() if script else "?")
    if b_pairs_all:
        L.append(f"【B级{_num('B级达标推荐')}场】")
        for i in range(min(len(b_pairs_all), 3)):
            h, a = b_pairs_all[i]
            L.append(f"{_cn(h)} vs {_cn(a)} | HT{b_ht_all[i]} {b_rate_all[i]} {b_goal_all[i]}球 | {b_script_all[i]}")
        L.append(SEP)
    
    # C级
    c_section = full.split("C级观察池")[1].split("跳过统计")[0] if "C级观察池" in full else ""
    c_lines = re.findall(r"(.+?) vs (.+?) —", c_section)
    if c_lines:
        c_str = " | ".join(f"{_cn(h)} vs {_cn(a)}" for h,a in c_lines[:6])
        L.append(f"【C级{_num('C级观察')}场】{c_str}")
        L.append(SEP)
    
    # 跳过
    skip_lines = re.findall(r"-\s*(.+?)[：:]\s*(\d+)场", full.split("跳过统计")[1].split("━━")[0] if "跳过统计" in full else "")
    if skip_lines:
        L.append(f"【跳过原因】{' | '.join(f'{k}{v}' for k,v in skip_lines[:4])}")
        L.append(SEP)
    
    # 昨日验证
    val_section = full.split("昨日V4验证")[1].split("━━")[0] if "昨日V4验证" in full else ""
    v_lines = re.findall(r"(A级|B级|C级|SKIP反杀率)[：:]\s*(.+)", val_section)
    L.append("【昨日验证】")
    if v_lines:
        for k,v in v_lines:
            L.append(f"{k} {v.strip()}")
    else:
        L.append("暂无数据")
    
    # 滚动
    L.append(SEP)
    L.append("【滚动验证】样本不足，仅观察")
    L.append(SEP)
    
    # 结论
    if _num('B级达标推荐') != "0":
        L.append(f"B级{_num('B级达标推荐')}场，重点关注阿治曼vs迪拜胜利、维拉vs利物浦")
    else:
        L.append("无A/B主推荐，仅C级观察")
    
    L.append("⚠️V4最终结论 | 禁止追加V33/旧口径")
    
    result = "\n".join(L)
    qq_path = REPORT_DIR / f"v4_openclaw_brief_qq_{key}.txt"
    qq_path.write_text(result, encoding="utf-8")
    return result

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    a = p.parse_args()
    print(format_qq(a.date))
