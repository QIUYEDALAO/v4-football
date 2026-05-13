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
    recommendation_bucket: str

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
            "recommendation_bucket": self.recommendation_bucket,
        }


def build_ht_recommendation(record: dict) -> dict:
    """
    赛前HT情报推荐器（不含投注动作）：
    A/B/C/HT_SKIP
    """
    factors = record.get("factors", {}) or {}
    scores = record.get("market_scores") or factors.get("market_scores") or {}
    market_focus = record.get("market_focus") or "HT_LIVE_OVER"

    ht_score = _float(scores.get("HT_LIVE_OVER"))
    h2h_ht = _float(factors.get("h2h_ht_goal_rate"))
    avg_ht_goals = _float(factors.get("h2h_avg_ht_goals"))
    recent_ht = _float(factors.get("recent_form_avg"))
    ht_attack = _float(factors.get("ht_attack_vs_defense"))
    tb = factors.get("time_bins", {}) or {}
    rtb = factors.get("recent_time_bins", {}) or {}
    # 优先用 H2H time_bins；全为 0 时（fast模式导致）回退到 recent_time_bins
    _tb_has_data = any(float(v or 0) > 0 for v in (tb or {}).values())
    effective_tb = tb if _tb_has_data else rtb
    late_11_45 = _float(effective_tb.get("11_45"))
    early_only_flag = bool(factors.get("early_only_flag") or factors.get("recent_early_only_flag"))
    pullback_fit = str(factors.get("pullback_fit") or factors.get("recent_timing_fit") or "-")
    sample_size = int(_float(factors.get("h2h_sample_size"), 0.0))

    reasons: list[str] = []
    risks: list[str] = []
    script_type = "均衡波动型"
    p0_15 = _float(tb.get("0_15"))
    p16_30 = _float(tb.get("16_30"))
    p31_45 = _float(tb.get("31_45"))
    if p31_45 >= max(p0_15, p16_30) and p31_45 >= 0.40:
        script_type = "中后段发力型"
    elif p0_15 >= max(p16_30, p31_45) and p0_15 >= 0.30:
        script_type = "开局冲击型"
    elif p16_30 >= max(p0_15, p31_45):
        script_type = "中段发力型"

    if market_focus != "HT_LIVE_OVER":
        best_focus_label = {"SECOND_HALF_OVER": "下半场", "FULLTIME_OVER": "全场"}.get(market_focus, market_focus)
        risks.append(f"方向冲突：系统总分最强为{best_focus_label}，但HT数据已达推荐级，人工决策时注意区分")

    if sample_size < 3:
        risks.append("样本数偏少")
    if early_only_flag:
        risks.append("early_only_flag=true")
    if pullback_fit == "WEAK":
        risks.append("pullback_fit=WEAK")

    reasons.append(f"HT综合评分 {ht_score:.1f}")
    reasons.append(f"H2H上半场有球率 {h2h_ht:.0%}")
    reasons.append(f"11-45分钟压力 {late_11_45:.0%}")

    # A级：强推荐
    if (
        ht_score >= 70
        and h2h_ht >= 0.65
        and recent_ht >= 0.70
        and ht_attack >= 0.70
        and late_11_45 >= 0.55
        and not early_only_flag
        and sample_size >= 3
    ):
        return {
            "grade": "A",
            "status": "HT_PREMATCH_RECOMMEND",
            "bucket": "HT_MAIN",
            "reason": "上半场强推荐",
            "reasons": reasons + ["近期HT攻防动能强", "11-45回调压力强", "非纯早球型"],
            "risks": risks[:3],
            "script_type": script_type,
            "ht_score": ht_score,
            "h2h_ht_goal_rate": h2h_ht,
            "ht_avg_goals": avg_ht_goals,
            "time_bins": {"0_15": p0_15, "16_30": p16_30, "31_45": p31_45},
            "sample_size": sample_size,
        }

    # B级：达标观察（仍在主推荐池）
    if (
        ht_score >= 60
        and h2h_ht >= 0.55
        and recent_ht >= 0.60
        and ht_attack >= 0.60
        and late_11_45 >= 0.45
        and sample_size >= 3
    ):
        return {
            "grade": "B",
            "status": "HT_PREMATCH_RECOMMEND",
            "bucket": "HT_MAIN",
            "reason": "上半场达标推荐",
            "reasons": reasons + ["HT基因达标，建议临场关注8-45节奏"],
            "risks": risks[:3],
            "script_type": script_type,
            "ht_score": ht_score,
            "h2h_ht_goal_rate": h2h_ht,
            "ht_avg_goals": avg_ht_goals,
            "time_bins": {"0_15": p0_15, "16_30": p16_30, "31_45": p31_45},
            "sample_size": sample_size,
        }

    # C级：仅情报观察
    if ht_score >= 50:
        return {
            "grade": "C",
            "status": "HT_OBSERVE",
            "bucket": "HT_OBSERVE",
            "reason": "仅情报观察",
            "reasons": reasons + ["信号不够强，保留观察"],
            "risks": risks[:3],
            "script_type": script_type,
            "ht_score": ht_score,
            "h2h_ht_goal_rate": h2h_ht,
            "ht_avg_goals": avg_ht_goals,
            "time_bins": {"0_15": p0_15, "16_30": p16_30, "31_45": p31_45},
            "sample_size": sample_size,
        }

    # SKIP
    skip_reasons = []
    if h2h_ht < 0.50:
        skip_reasons.append("HT有球率不足")
    if avg_ht_goals < 0.60:
        skip_reasons.append("上半场场均进球不足")
    if late_11_45 < 0.45:
        skip_reasons.append("11-45分钟压力弱")
    if pullback_fit == "WEAK":
        skip_reasons.append("回调适配弱")
    if early_only_flag:
        skip_reasons.append("早球型，不适合HT推荐")
    return {
        "grade": "SKIP",
        "status": "HT_SKIP",
        "bucket": "HT_SKIP",
        "reason": "上半场基因不足",
        "reasons": skip_reasons[:4] or ["综合评分不足"],
        "risks": risks[:3],
        "script_type": script_type,
        "ht_score": ht_score,
        "h2h_ht_goal_rate": h2h_ht,
        "ht_avg_goals": avg_ht_goals,
        "time_bins": {"0_15": p0_15, "16_30": p16_30, "31_45": p31_45},
        "sample_size": sample_size,
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
    avg_ht_goals = _float(factors.get("h2h_avg_ht_goals"))
    recent_ht = _float(factors.get("recent_form_avg"))
    recent_sh = _float(factors.get("recent_sh_avg"))
    ht_attack = _float(factors.get("ht_attack_vs_defense"))
    tb = factors.get("time_bins", {}) or {}
    rtb = factors.get("recent_time_bins", {}) or {}
    _tb_has_data = any(float(v or 0) > 0 for v in (tb or {}).values())
    effective_tb = tb if _tb_has_data else rtb
    sh_tb = factors.get("second_half_bins", {}) or {}
    early_0_10 = _float(effective_tb.get("0_10"))
    early_0_15 = _float(effective_tb.get("0_15"))
    late_11_45 = _float(effective_tb.get("11_45"))
    pullback_fit = factors.get("pullback_fit") or factors.get("recent_timing_fit") or "-"
    early_only_flag = bool(factors.get("early_only_flag") or factors.get("recent_early_only_flag"))
    pre_ht_line = record.get("pre_ht_line")
    pre_ht_line_val = None
    if isinstance(pre_ht_line, dict):
        pre_ht_line_val = pre_ht_line.get("line")
    elif isinstance(pre_ht_line, (int, float, str)):
        pre_ht_line_val = pre_ht_line
    pre_line = _float(pre_ht_line_val or record.get("pre_ht_line_float"))
    threat = _float(factors.get("both_sides_ht_threat"))

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
    price_expensive = pre_line >= 1.75
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
    if not match_type:
        match_type.append("NO_CLEAR_EDGE")
        why.append("HT/SH/FT方向不够集中")

    ht_recommendation = build_ht_recommendation(record)
    ht_decision = {
        "action": f"HT_{ht_recommendation.get('grade', 'SKIP')}",
        "bucket": ht_recommendation.get("bucket", "HT_SKIP"),
        "is_main_recommendation": ht_recommendation.get("grade") in ("A", "B"),
        "reason": ht_recommendation.get("reason", ""),
    }

    # --- 2) SH 仅附加观察，不覆盖主出口 ---
    sh_observation = None
    if sh_surge:
        sh_observation = {
            "action": "SH_OBSERVE_ONLY",
            "bucket": "SH_OBSERVE",
            "is_main_recommendation": False,
            "reason": "下半场倾向更强，但不计入HT主推荐",
            "trade_action": "下半场观察：不属于V4_HT主推荐",
        }

    # --- 3) 主展示动作只使用 HT 推荐结果 ---
    is_live_radar = bool(record.get("is_watch")) and market_focus == "HT_LIVE_OVER"
    action_code = ht_decision["action"]
    recommendation_bucket = ht_decision["bucket"]
    primary_direction = "HT"
    if ht_recommendation.get("grade") in ("A", "B"):
        execution_status = f"上半场推荐 {ht_recommendation.get('grade')}级"
        trade_action = "情报推荐：由你决定是否投注与入场时机"
        profile = f"画像：HT赛前推荐({ht_recommendation.get('script_type')})"
        summary = "结论：推荐进入今日上半场重点关注清单"
        wait_for = ["关注0-15/16-30/31-45分布", "结合临场节奏自行决策"]
    elif ht_recommendation.get("grade") == "C":
        execution_status = "上半场观察 C级"
        trade_action = "仅观察：不进入主推荐"
        profile = f"画像：HT仅情报观察({ht_recommendation.get('script_type')})"
        summary = "结论：保留观察，不作为主推荐"
        wait_for = []
    else:
        execution_status = "上半场跳过"
        trade_action = "HT_SKIP：上半场基因不足"
        profile = "画像：HT基因不足"
        summary = "结论：不进入上半场推荐"
        wait_for = []

    rg = record.get("risk_guard") or {}
    if isinstance(rg, dict) and (rg.get("allow") is False):
        action_code = "HT_SKIP_RISK_GUARD"
        recommendation_bucket = "HT_SKIP"
        avoid_if.append(f"风控拦截: {rg.get('reason', 'RISK_GUARD')}")
        trade_action = "风控拦截：仅保留观察"
        execution_status = "风控拦截"

    # 信心和执行标签
    confidence = 40
    confidence += min(max(ht_score, sh_score, ft_score), 90) * 0.35
    confidence += 10 if h2h_ht >= 0.70 else 0
    confidence += 8 if recent_ht >= 0.70 or recent_sh >= 0.70 else 0
    confidence += 6 if ht_attack >= 0.65 else 0
    confidence -= 12 if data_weak else 0
    confidence -= 8 if schedule_action == "WATCH_CAUTION" else 0
    confidence = int(max(0, min(round(confidence), 95)))

    risk_level = "MID"
    if ht_recommendation.get("grade") == "SKIP":
        risk_level = "HIGH"
    elif ht_recommendation.get("grade") in ("A", "B"):
        risk_level = "LOW"

    ev_label = "情报推荐"
    if confidence >= 75:
        ev_label = "推荐强"
    elif confidence >= 60:
        ev_label = "推荐中"

    execution_label = "仅情报"
    if ht_recommendation.get("grade") in ("A", "B"):
        execution_label = "主推荐"
    elif ht_recommendation.get("grade") == "C":
        execution_label = "观察池"
    elif action_code == "HT_SKIP_RISK_GUARD":
        execution_label = "风控拦截"

    out = MatchIntelligence(
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
        recommendation_bucket=recommendation_bucket,
    ).to_dict()
    out["ht_decision"] = ht_decision
    out["ht_recommendation"] = ht_recommendation
    out["sh_observation"] = sh_observation
    out["display_bucket"] = ht_decision["bucket"]
    out["is_ht_main_recommendation"] = bool(ht_decision.get("is_main_recommendation"))
    out["ht_reason"] = ht_decision.get("reason", "")
    return out
