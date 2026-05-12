"""
V4 智能比赛解释器
================
把底层因子转成交易员可读的比赛标签、主方向、建议动作和解释。

第一阶段保持规则型、可解释，不做黑盒模型。
"""

from __future__ import annotations

from dataclasses import dataclass


def _float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class MatchIntelligence:
    match_type: list[str]
    primary_direction: str
    trade_action: str
    confidence: int
    profile: str
    summary: str
    why: list[str]
    wait_for: list[str]
    avoid_if: list[str]
    execution_status: str
    is_live_radar: bool
    action_code: str
    risk_level: str
    ev_label: str
    execution_label: str

    def to_dict(self) -> dict:
        return {
            "match_type": self.match_type,
            "primary_direction": self.primary_direction,
            "trade_action": self.trade_action,
            "confidence": self.confidence,
            "profile": self.profile,
            "summary": self.summary,
            "why": self.why,
            "wait_for": self.wait_for,
            "avoid_if": self.avoid_if,
            "execution_status": self.execution_status,
            "is_live_radar": self.is_live_radar,
            "action_code": self.action_code,
            "risk_level": self.risk_level,
            "ev_label": self.ev_label,
            "execution_label": self.execution_label,
        }


def explain_match(record: dict) -> dict:
    factors = record.get("factors", {}) or {}
    scores = record.get("market_scores") or factors.get("market_scores") or {}
    data_coverage = record.get("data_coverage", {}) or {}
    schedule_pressure = record.get("schedule_pressure", {}) or {}
    motivation = record.get("motivation", {}) or {}
    motivation_gate = motivation.get("gate", {}) or {}

    market_focus = record.get("market_focus") or "HT_LIVE_OVER"
    best_focus = record.get("best_focus_by_score") or factors.get("best_focus_by_score") or ""
    phase_bias = factors.get("phase_bias", "BALANCED")
    data_action = data_coverage.get("data_gate_action", "-")
    schedule_action = schedule_pressure.get("action", "-")

    ht_score = _float(scores.get("HT_LIVE_OVER"))
    sh_score = _float(scores.get("SECOND_HALF_OVER"))
    ft_score = _float(scores.get("FULLTIME_OVER"))
    h2h_ht = _float(factors.get("h2h_ht_goal_rate"))
    recent_ht = _float(factors.get("recent_form_avg"))
    recent_sh = _float(factors.get("recent_sh_avg"))
    ht_attack = _float(factors.get("ht_attack_vs_defense"))
    tb = factors.get("time_bins", {}) or {}
    sh_tb = factors.get("second_half_bins", {}) or {}
    early_0_10 = _float(tb.get("0_10"))
    late_11_45 = _float(tb.get("11_45"))
    late_sh = max([_float(v) for v in sh_tb.values()] or [0.0])
    pullback_fit = factors.get("pullback_fit", "-")

    match_type: list[str] = []
    why: list[str] = []
    wait_for: list[str] = []
    avoid_if: list[str] = ["红牌", "重大伤退", "盘口水位异常"]

    early_flash = early_0_10 >= 0.35 and pullback_fit == "WEAK"
    ht_pullback = (
        market_focus == "HT_LIVE_OVER"
        and best_focus == "HT_LIVE_OVER"
        and ht_score >= 50
        and late_11_45 >= 0.50
        and pullback_fit in ("OK", "STRONG")
    )
    sh_surge = (
        market_focus == "SECOND_HALF_OVER"
        or best_focus == "SECOND_HALF_OVER"
        or phase_bias == "SECOND_HALF_BIAS"
        or (sh_score >= max(ht_score, ft_score) and sh_score - ht_score >= 12 and recent_sh >= 0.70)
    )
    ft_open = best_focus == "FULLTIME_OVER" or ft_score >= max(ht_score, sh_score)
    data_weak = data_action in ("WATCH_ONLY", "SKIP_DATA_WEAK")
    market_missing = data_action == "WATCH_MARKET_MISSING"
    pre_ht_line = record.get("pre_ht_line")
    pre_ht_line_val = None
    if isinstance(pre_ht_line, dict):
        pre_ht_line_val = pre_ht_line.get("line")
    elif isinstance(pre_ht_line, (int, float, str)):
        pre_ht_line_val = pre_ht_line
    price_expensive = _float(pre_ht_line_val or record.get("pre_ht_line_float")) >= 1.75
    dull_trap = ht_score >= 50 and pullback_fit == "WEAK" and late_11_45 < 0.50 and not early_flash

    if early_flash:
        match_type.append("EARLY_FLASH")
        why.append(f"0-10分钟热度 {early_0_10:.0%}，但回调适配 WEAK")
    if ht_pullback:
        match_type.append("HT_PULLBACK")
        why.append(f"11-45压力 {late_11_45:.0%}，适合等待无球后降盘")
    if sh_surge:
        match_type.append("SH_SURGE")
        why.append(f"下半场信号更强：SH {sh_score:.1f} vs HT {ht_score:.1f}")
    if ft_open:
        match_type.append("FT_OPEN_GAME")
        why.append(f"全场大球分 {ft_score:.1f} 是主要开放信号")
    if price_expensive:
        match_type.append("PRICE_TOO_EXPENSIVE")
        why.append("赛前半场盘口偏高，不能追高")
    if data_weak:
        match_type.append("DATA_TOO_WEAK")
        why.append(f"API覆盖为 {data_coverage.get('coverage_level', '-')} / {data_action}")
    elif market_missing:
        match_type.append("MARKET_MISSING")
        why.append(f"统计可用，但盘口端待赛中确认：{data_coverage.get('coverage_level', '-')} / {data_action}")
    if dull_trap:
        match_type.append("DULL_TRAP")
        why.append("分数不低但10分钟后回调质量差")

    if not match_type:
        match_type.append("NO_CLEAR_EDGE")
        why.append("HT/SH/FT方向不够集中")

    is_live_radar = (
        bool(record.get("is_watch"))
        and market_focus == "HT_LIVE_OVER"
        and data_action == "ALLOW_V4_LIVE"
        and ht_pullback
    )

    primary_direction = "SKIP"
    execution_status = "观察不入场"
    trade_action = "跳过：只记录情报"
    action_code = "SKIP"
    profile = "画像：方向不够集中"
    summary = "结论：不作为交易候选"

    if ht_pullback and is_live_radar:
        primary_direction = "HT"
        execution_status = "滚球雷达"
        trade_action = "上半场：0-15分钟等降盘，满足节奏再进"
        action_code = "WAIT_LINE"
        profile = "画像：上半场回调型"
        summary = "结论：上半场走地候选"
        wait_for = ["0-10分钟无进球", "盘口降到大1.0或大0.75", "赛中节奏不沉闷"]
    elif sh_surge:
        primary_direction = "SH"
        execution_status = "下半场观察"
        trade_action = "上半场：只防闪击；下半场：半场后再评估" if early_flash else "上半场：跳过；下半场：半场后再评估"
        action_code = "PAPER_ONLY"
        profile = "画像：下半场倾向更强，且上半场早段有闪击风险" if early_flash else "画像：下半场倾向更强"
        summary = "结论：不做上半场回调，半场后看下半场盘口"
        wait_for = ["半场比分0-0/1-0/0-1/1-1", "上半场射门和危险进攻不沉闷", "SH Over 0.75/1.0合理水位"]
    elif early_flash:
        primary_direction = "EARLY_HT"
        execution_status = "早段闪击观察"
        trade_action = "上半场：只防闪击，不做0-10后回调追入"
        action_code = "SKIP"
        profile = "画像：上半场早段有球风险高，但不是回调型"
        summary = "结论：回调适配WEAK不代表上半场不进，只代表等待降盘买点差"
        wait_for = ["赛前盘口是否已过热", "开场前是否有更低风险表达"]
    elif ft_open:
        primary_direction = "FT"
        execution_status = "全场观察"
        trade_action = "上半场：跳过；全场：只做参考"
        action_code = "PAPER_ONLY"
        profile = "画像：全场开放局，不等于下半场单边优势"
        summary = "结论：不强行分时进场"
        wait_for = ["盘口价格回到合理区间", "场面持续开放"]

    # 节奏弱时直接等待节奏，不给可进场信号
    if "节奏不沉闷" in " ".join(wait_for) and late_11_45 < 0.55 and action_code == "WAIT_LINE":
        action_code = "WAIT_TEMPO"

    if data_action == "WATCH_ONLY":
        avoid_if.append("API覆盖不足导致实时统计/盘口缺失")
        action_code = "PAPER_ONLY"
    elif data_action == "WATCH_MARKET_MISSING":
        avoid_if.append("盘口端暂缺/延迟，待赛中盘口恢复")
        if action_code in ("WAIT_LINE", "WAIT_TEMPO", "WAIT_CONFIDENCE", "PAPER_BUY_NOW"):
            action_code = "PAPER_ONLY"
    if schedule_action == "WATCH_CAUTION":
        avoid_if.append("赛程压力高")
        if action_code in ("WAIT_LINE", "WAIT_TEMPO"):
            action_code = "PAPER_ONLY"
    if motivation_gate.get("action") == "WATCH_ONLY":
        avoid_if.append("战意不清晰")
        action_code = "PAPER_ONLY"
    if pullback_fit == "WEAK" and primary_direction == "HT":
        avoid_if.append("0-10无球后继续追入")
    rg = record.get("risk_guard") or {}
    if isinstance(rg, dict) and (rg.get("allow") is False):
        action_code = "RISK_BLOCKED"
        avoid_if.append(f"风控拦截: {rg.get('reason', 'RISK_GUARD')}")
        trade_action = "风控拦截：不允许进场"
        execution_status = "风控拦截"

    confidence = 40
    confidence += min(max(ht_score, sh_score, ft_score), 90) * 0.35
    confidence += 10 if h2h_ht >= 0.70 else 0
    confidence += 8 if recent_ht >= 0.70 or recent_sh >= 0.70 else 0
    confidence += 6 if ht_attack >= 0.65 else 0
    confidence -= 12 if data_weak else 0
    confidence -= 8 if schedule_action == "WATCH_CAUTION" else 0
    confidence = int(max(0, min(round(confidence), 95)))
    if action_code == "WAIT_LINE" and confidence < 72:
        action_code = "WAIT_CONFIDENCE"
    if action_code == "WAIT_LINE" and confidence >= 72 and pullback_fit in ("OK", "STRONG"):
        action_code = "PAPER_BUY_NOW"
    if "红牌" in " ".join(avoid_if):
        pass
    risk_level = "MID"
    if action_code in ("SKIP", "RISK_BLOCKED"):
        risk_level = "HIGH"
    elif action_code == "PAPER_BUY_NOW":
        risk_level = "MID" if schedule_action == "WATCH_CAUTION" else "LOW"
    elif action_code == "PAPER_ONLY":
        risk_level = "MID"
    ev_label = "EV观察"
    if confidence >= 75:
        ev_label = "EV强"
    elif confidence >= 60:
        ev_label = "EV合格"
    execution_label = "可成交"
    if action_code in ("WAIT_LINE", "WAIT_TEMPO", "WAIT_CONFIDENCE"):
        execution_label = "等待条件"
    elif action_code in ("PAPER_ONLY", "SKIP"):
        execution_label = "仅观察"
    elif action_code == "RISK_BLOCKED":
        execution_label = "风控拦截"

    return MatchIntelligence(
        match_type=match_type,
        primary_direction=primary_direction,
        trade_action=trade_action,
        confidence=confidence,
        profile=profile,
        summary=summary,
        why=why[:5],
        wait_for=wait_for[:5],
        avoid_if=avoid_if[:5],
        execution_status=execution_status,
        is_live_radar=is_live_radar,
        action_code=action_code,
        risk_level=risk_level,
        ev_label=ev_label,
        execution_label=execution_label,
    ).to_dict()
