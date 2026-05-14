#!/usr/bin/env python3
"""engine/v4_qq_formatter.py — V4简报QQ移动端格式化
================================================
输入: v4_openclaw_brief_YYYYMMDD.txt (完整版)
输出: v4_openclaw_brief_qq_YYYYMMDD.txt (QQ版)

规则: 无markdown表格/无长分隔线/34宽/中文队名优先/卡片≤7行
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from engine.team_cn_map import strict_match as team_cn
except Exception:
    def team_cn(n: str) -> str: return n

# 本批补充中文映射
EXTRA_CN = {
    "Ajman": "阿治曼", "Al Nasr": "迪拜胜利", "Al-Wasl": "迪拜祈祷",
    "Al Wasl": "迪拜祈祷", "Al-Ittihad Kalba": "伊蒂哈德卡尔巴",
    "Ittihad Kalba": "伊蒂哈德卡尔巴", "Adelaide United": "阿德莱德联",
    "Auckland": "奥克兰FC", "Oriente Petrolero": "东方石油",
    "Guabirá": "瓜比拉", "Rizespor": "里泽体育",
    "Beşiktaş": "贝西克塔斯", "Besiktas": "贝西克塔斯",
    "Aston Villa": "阿斯顿维拉", "Liverpool": "利物浦",
    "Manchester City": "曼城", "Crystal Palace": "水晶宫",
}

def _cn(name: str) -> str:
    if name in EXTRA_CN:
        return EXTRA_CN[name]
    return team_cn(name)

SEP = "━" * 12
REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _cnt(text: str, keyword: str) -> int:
    return text.count(keyword)


def format_qq(date_str: str) -> str:
    key = date_str.replace("-", "")
    brief_path = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
    if not brief_path.exists():
        return "V4简报文件尚未生成。"
    
    full = brief_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    
    # 提取数据
    lines = full.split("\n")
    
    scan_total = "?"
    a_count = "0"
    b_count = "0"
    c_count = "0"
    skip_count = "0"
    ab_rate = "?"
    
    for line in lines:
        if "全量扫描：" in line:
            scan_total = line.split("：")[-1].replace("场", "").strip()
        elif "A级强推荐：" in line:
            a_count = line.split("：")[-1].replace("场", "").strip()
        elif "B级达标推荐：" in line:
            b_count = line.split("：")[-1].replace("场", "").strip()
        elif "C级观察：" in line:
            c_count = line.split("：")[-1].replace("场", "").strip()
        elif "HT_SKIP跳过：" in line:
            skip_count = line.split("：")[-1].replace("场", "").strip()
        elif "A+B覆盖率：" in line:
            ab_rate = line.split("：")[-1].strip()

    date_display = f"{key[:4]}-{key[4:6]}-{key[6:8]}"
    
    out = []
    out.append(f"⏰ V4上半场情报")
    out.append(f"日期：{date_display}")
    out.append("")
    out.append("【今日概览】")
    out.append(f"扫描：{scan_total}场")
    out.append(f"A强推：{a_count}场")
    out.append(f"B达标：{b_count}场")
    out.append(f"C观察：{c_count}场")
    out.append(f"跳过：{skip_count}场")
    out.append(f"A+B覆盖：{ab_rate}")
    
    # ── A级 ──
    out.append("")
    out.append(SEP)
    out.append("【A级强推】")
    a_cards = _extract_cards(full, "A级上半场强推荐", "B级上半场达标推荐", "🟢 B级")
    if a_cards:
        for card in a_cards[:2]:
            out.append("")
            out.append(_format_card_qq(card))
    else:
        out.append("无")
    
    # ── B级 ──
    out.append("")
    out.append(SEP)
    out.append(f"【B级达标 {b_count}场】")
    b_cards = _extract_cards(full, "B级上半场达标推荐", "C级观察池", "👁️ C级")
    if b_cards:
        for card in b_cards[:5]:
            out.append("")
            out.append(_format_card_qq(card))
    else:
        out.append("无")
    
    # ── C级 ──
    out.append("")
    out.append(SEP)
    out.append(f"【C级观察 {c_count}场】")
    c_lines = _extract_c_lines(full)
    if c_lines:
        for i, cl in enumerate(c_lines[:8]):
            out.append(cl)
        if len(c_lines) > 8:
            out.append(f"其余{len(c_lines)-8}场见完整报告。")
    else:
        out.append("无")
    
    # ── SKIP ──
    out.append("")
    out.append(SEP)
    out.append("【跳过原因】")
    skip_reasons = _extract_skip_reasons(full)
    if skip_reasons:
        for r in skip_reasons[:3]:
            out.append(r)
    else:
        out.append("无")
    
    # ── 昨日验证 ──
    out.append("")
    out.append(SEP)
    out.append("【昨日验证】")
    val_lines = _extract_validation(full)
    if val_lines:
        for vl in val_lines:
            out.append(vl)
    else:
        out.append("暂无昨日V4验证数据")
    
    # ── 滚动验证 ──
    out.append("")
    out.append(SEP)
    out.append("【滚动验证】")
    out.append("近7天：样本不足，仅观察")
    out.append("近30天：样本不足，仅观察")
    
    # ── 今日结论 ──
    out.append("")
    out.append(SEP)
    out.append("【今日结论】")
    
    has_a = a_count not in ("0", "?")
    has_b = b_count not in ("0", "?")
    
    if not has_a and not has_b:
        out.append("今日无A/B主推荐。")
    else:
        if not has_a:
            out.append("无A级强推。")
        if has_b:
            out.append(f"B级{b_count}场。")
        
        if b_cards:
            first_b = b_cards[0]
            # extract team names
            import re
            tm = re.findall(r"(.+?) vs", first_b)
            if tm:
                out.append(f"重点关注：{tm[0].strip()}。")
    
    out.append("")
    out.append("---")
    out.append("⚠️ 本简报为V4最终结论。")
    out.append("禁止追加V33/旧口径/独立分析。")
    
    result = "\n".join(out)
    
    # 保存
    qq_path = REPORT_DIR / f"v4_openclaw_brief_qq_{key}.txt"
    qq_path.write_text(result, encoding="utf-8")
    
    return result


def _extract_cards(text: str, start_marker: str, end_marker: str, alt_start: str = "") -> list[str]:
    """提取比赛卡片"""
    cards = []
    # Find the section
    idx = text.find(start_marker)
    if idx < 0 and alt_start:
        idx = text.find(alt_start)
    if idx < 0:
        return []
    
    section = text[idx:]
    end_idx = section.find(end_marker)
    if end_idx > 0:
        section = section[:end_idx]
    
    # Split by match delimiter (double newline or separator)
    raw = section.split("\n")
    current = []
    in_card = False
    for line in raw:
        stripped = line.strip()
        if not stripped:
            if in_card and current:
                cards.append("\n".join(current))
                current = []
            in_card = False
            continue
        if "━━" in stripped:
            if current:
                cards.append("\n".join(current))
                current = []
            in_card = False
            continue
        if "vs" in stripped and not stripped.startswith("👁") and not stripped.startswith("🟢") and not stripped.startswith("🔥"):
            if current:
                cards.append("\n".join(current))
            current = [stripped]
            in_card = True
        elif in_card:
            current.append(stripped)
    
    if current:
        cards.append("\n".join(current))
    
    return cards


def _format_card_qq(card_text: str) -> str:
    """格式化单场比赛卡片为QQ版"""
    import re
    lines = card_text.strip().split("\n")
    out = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        
        # 队名行
        if "vs" in stripped and i == 0:
            parts = stripped.split("vs", 1)
            home = _cn(parts[0].strip())
            away = _cn(parts[1].strip())
            out.append(f"① {home} vs {away}")
            continue
        
        if "vs" in stripped and "—" in stripped:
            # C级行
            continue
        
        # 联赛时间
        if "·" in stripped and ":" in stripped:
            out.append(f" {stripped.strip()}")
            continue
        
        # HT评分行
        if "HT评分" in stripped or "HT有球率" in stripped:
            nums = re.findall(r"[\d.]+%?", stripped)
            vals = "｜".join(nums[:4])
            if vals:
                out.append(f" {vals}")
            continue
        
        # 剧本
        if "剧本" in stripped:
            out.append(f" {stripped.replace('剧本：','')}")
            continue
        
        # 分布
        if "分布" in stripped:
            dist = stripped.replace("分布：", "")
            out.append(f" {dist}")
            continue
        
        # 风险
        if "风险" in stripped:
            risk = stripped.replace("风险：", "")[:40]
            out.append(f" 风险：{risk}")
            continue
    
    return "\n".join(out[:7])


def _extract_c_lines(text: str) -> list[str]:
    """提取C级观察行"""
    import re
    idx = text.find("C级观察池")
    if idx < 0:
        return []
    section = text[idx:]
    end_idx = section.find(SEP if SEP in text else "━━")
    if end_idx > 0:
        section = section[:end_idx]
    
    result = []
    for line in section.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("👁") or stripped.startswith("C级"):
            continue
        if "vs" in stripped and "—" in stripped:
            # Extract: TeamA vs TeamB — League Time | HTxx | xx% | type
            m = re.match(r"(.+?)\s+vs\s+(.+?)\s+—\s+(.+?)\s*\|\s*(.+)$", stripped)
            if m:
                home = _cn(m.group(1).strip())
                away = _cn(m.group(2).strip())
                info = m.group(3).strip() + "｜HT" + m.group(4).split("|")[0].replace("HT","").strip()
                result.append(f"{home} vs {away}")
                result.append(f" {info}")
            else:
                result.append(stripped)
    return result


def _extract_skip_reasons(text: str) -> list[str]:
    idx = text.find("跳过统计")
    if idx < 0:
        return []
    section = text[idx:]
    end_idx = section.find("━━")
    if end_idx > 0:
        section = section[:end_idx]
    
    result = []
    for line in section.split("\n"):
        stripped = line.strip()
        if stripped.startswith("-") or stripped.startswith("•"):
            result.append(stripped.lstrip("- •"))
    return result


def _extract_validation(text: str) -> list[str]:
    idx = text.find("昨日V4验证")
    if idx < 0:
        return []
    section = text[idx:]
    end_idx = section.find("━━", 10)
    if end_idx > 0:
        section = section[:end_idx]
    
    result = []
    for line in section.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("📌") or stripped.startswith("昨日"):
            continue
        if "命中率" in stripped or "反杀率" in stripped or "暂无" in stripped:
            result.append(stripped)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()
    text = format_qq(args.date)
    print(text)
