"""
V4 智能比赛解释器（HT赛前情报推荐版）
==================================
主目标：
1) 产出 HT A/B/C/SKIP 推荐等级
2) 输出可解释的时间分布与风险提示
3) SH 仅作为独立观察，不污染 HT 主推荐
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _pct_text(value: float) -> str:
    return f"{value * 100:.0f}%"


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


BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = BASE_DIR / "config" / "v4_ht_recommendation_rules.yaml"

DEFAULT_RULES = {
    "rule_version": "v4_ht_recommend_20260513",
    "coverage_target": {"ab_ratio_min_pct": 5.0, "ab_ratio_max_pct": 15.0},
    "sample_policy": {
        "min_for_ab": 3,
        "a_downgrade_to_b_if_sample_lt": 5,
        "a_mark_medium_sample_if_lt": 8,
        "confidence_boost_if_sample_gte": 10,
    },
    "grades": {
        "A": {
            "min_ht_score": 70,
            "min_h2h_ht_goal_rate": 0.65,
            "min_recent_ht": 0.70,
            "min_ht_attack": 0.70,
            "min_late_11_45": 0.55,
            "min_sample_size": 5,
            "allow_early_only": False,
        },
        "B": {
            "min_ht_score": 60,
            "min_h2h_ht_goal_rate": 0.55,
            "min_recent_ht": 0.60,
            "min_ht_attack": 0.60,
            "min_late_11_45": 0.45,
            "min_sample_size": 3,
            "allow_early_only": True,
        },
        "C": {"min_ht_score": 50},
    },
    "skip": {
        "min_h2h_ht_goal_rate": 0.50,
        "min_ht_avg_goals": 0.60,
        "min_late_11_45": 0.45,
    },
}

_RULES_CACHE: dict[str, Any] | None = None


def _load_rules() -> dict[str, Any]:
    """
    读取 YAML 配置。为避免额外依赖，采用 JSON 兼容 YAML（YAML 是 JSON 超集）。
    """
    global _RULES_CACHE
    if _RULES_CACHE is not None:
        return _RULES_CACHE

    rules = dict(DEFAULT_RULES)
    if RULES_PATH.exists():
        try:
            loaded = json.loads(RULES_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                # 仅做一层 merge，内层按 key 更新
                for k, v in loaded.items():
                    if isinstance(v, dict) and isinstance(rules.get(k), dict):
                        merged = dict(rules[k])
                        merged.update(v)
                        rules[k] = merged
                    else:
                        rules[k] = v
        except Exception:
            pass

    _RULES_CACHE = rules
    return rules


def _best_focus_label(focus: str) -> str:
    return {
        "HT_LIVE_OVER": "上半场",
        "SECOND_HALF_OVER": "下半场",
        "FULLTIME_OVER": "全场",
    }.get(focus, focus)


def _time_bins_with_fallback(factors: dict) -> tuple[dict, str]:
    tb = factors.get("time_bins", {}) or {}
    rtb = factors.get("recent_time_bins", {}) or {}
    tb_has_data = any(_float(v, 0.0) > 0 for v in tb.values())
    if tb_has_data:
        return tb, "h2h"
    return rtb, "recent_fallback"


def _script_type_from_bins(time_bins: dict) -> str:
    p0_15 = _float(time_bins.get("0_15"))
    p16_30 = _float(time_bins.get("16_30"))
    p31_45 = _float(time_bins.get("31_45"))
    if p31_45 >= max(p0_15, p16_30) and p31_45 >= 0.40:
        return "中后段发力型"
    if p0_15 >= max(p16_30, p31_45) and p0_15 >= 0.30:
        return "开局冲击型"
    if p16_30 >= max(p0_15, p31_45):
        return "中段发力型"
    return "均衡波动型"


def _sort_risks(risks: list[dict]) -> list[dict]:
    return sorted(risks, key=lambda x: (int(x.get("priority", 99)), x.get("code", "")))


def build_ht_recommendation(record: dict) -> dict:
    """
    赛前 HT 情报推荐器（不含投注动作）：
    A/B/C/SKIP
    """
    rules = _load_rules()
    gA = (rules.get("grades") or {}).get("A", {})
    gB = (rules.get("grades") or {}).get("B", {})
    gC = (rules.get("grades") or {}).get("C", {})
    sp = rules.get("sample_policy", {}) or {}
    skip_rules = rules.get("skip", {}) or {}
    rule_version = str(rules.get("rule_version") or DEFAULT_RULES["rule_version"])

    factors = record.get("factors", {}) or {}
    scores = record.get("market_scores") or factors.get("market_scores") or {}
    market_focus = str(record.get("market_focus") or "HT_LIVE_OVER")
    best_focus = str(record.get("best_focus_by_score") or factors.get("best_focus_by_score") or market_focus)

    ht_score = _float(scores.get("HT_LIVE_OVER"))
    h2h_ht = _float(factors.get("h2h_ht_goal_rate"))
    avg_ht_goals = _float(factors.get("h2h_avg_ht_goals"))
    recent_ht = _float(factors.get("recent_form_avg"))
    ht_attack = _float(factors.get("ht_attack_vs_defense"))
    sample_size = int(_float(factors.get("h2h_sample_size"), 0.0))
    early_only_flag = bool(factors.get("early_only_flag") or factors.get("recent_early_only_flag"))
    pullback_fit_raw = factors.get("pullback_fit") or "-"
    recent_timing_fit = factors.get("recent_timing_fit") or "-"
    # 当 H2H time_bins 全 0 且 recent_timing_fit 有有效值时，用 recent 回退
    h2h_tb = factors.get("time_bins", {}) or {}
    tb_has_data = any(_float(v or 0, 0.0) > 0 for v in h2h_tb.values())
    if tb_has_data:
        pullback_fit = str(pullback_fit_raw)
    else:
        pullback_fit = str(recent_timing_fit) if str(recent_timing_fit) not in ("-", "WEAK") else str(pullback_fit_raw)

    effective_tb, tb_source = _time_bins_with_fallback(factors)
    p0_15 = _float(effective_tb.get("0_15"))
    p16_30 = _float(effective_tb.get("16_30"))
    p31_45 = _float(effective_tb.get("31_45"))
    late_11_45 = _float(effective_tb.get("11_45"))
    script_type = _script_type_from_bins(effective_tb)

    reason_candidates: list[tuple[int, str]] = [
        (100, f"H2H上半场有球率 {_pct_text(h2h_ht)}"),
        (95, f"上半场场均进球 {avg_ht_goals:.2f}"),
        (92, f"11-45分钟压力 {_pct_text(late_11_45)}"),
        (88, f"近期HT动能 {_pct_text(recent_ht)}"),
        (86, f"HT攻防交叉 {_pct_text(ht_attack)}"),
        (84, f"进球剧本：{script_type}"),
    ]

    risks: list[dict] = []
    if sample_size < 3:
        risks.append({"priority": 1, "code": "sample_lt_3", "text": "样本数<3，可靠性不足"})
    elif sample_size < 5:
        risks.append({"priority": 2, "code": "sample_3_4", "text": "样本数仅3-4场，建议保守"})
    elif sample_size < 8:
        risks.append({"priority": 3, "code": "sample_5_7", "text": "样本中等（5-7场）"})

    if h2h_ht < _float(skip_rules.get("min_h2h_ht_goal_rate"), 0.50):
        risks.append({"priority": 1, "code": "low_h2h_ht", "text": "HT有球率偏低"})
    if avg_ht_goals < _float(skip_rules.get("min_ht_avg_goals"), 0.60):
        risks.append({"priority": 1, "code": "low_ht_goals", "text": "上半场场均进球偏低"})
    if late_11_45 < _float(skip_rules.get("min_late_11_45"), 0.45):
        risks.append({"priority": 1, "code": "low_11_45", "text": "11-45分钟压力不足"})
    if early_only_flag:
        risks.append({"priority": 2, "code": "early_only", "text": "早球型，节奏持续性偏弱"})
    if pullback_fit == "WEAK":
        risks.append({"priority": 2, "code": "pullback_weak", "text": "回调适配偏弱"})
    if tb_source != "h2h":
        risks.append({"priority": 2, "code": "tb_fallback", "text": "时间分布使用近期回退样本"})

    # 先按规则分级
    grade = "SKIP"
    if (
        ht_score >= _float(gA.get("min_ht_score"))
        and h2h_ht >= _float(gA.get("min_h2h_ht_goal_rate"))
        and recent_ht >= _float(gA.get("min_recent_ht"))
        and ht_attack >= _float(gA.get("min_ht_attack"))
        and late_11_45 >= _float(gA.get("min_late_11_45"))
        and sample_size >= int(_float(gA.get("min_sample_size"), 5))
        and (bool(gA.get("allow_early_only", False)) or not early_only_flag)
    ):
        grade = "A"
    elif (
        ht_score >= _float(gB.get("min_ht_score"))
        and h2h_ht >= _float(gB.get("min_h2h_ht_goal_rate"))
        and recent_ht >= _float(gB.get("min_recent_ht"))
        and ht_attack >= _float(gB.get("min_ht_attack"))
        and late_11_45 >= _float(gB.get("min_late_11_45"))
        and sample_size >= int(_float(gB.get("min_sample_size"), 3))
        and (bool(gB.get("allow_early_only", True)) or not early_only_flag)
    ):
        grade = "B"
    elif ht_score >= _float(gC.get("min_ht_score"), 50.0):
        grade = "C"

    # 样本可信度降级策略
    min_for_ab = int(_float(sp.get("min_for_ab"), 3))
    a_to_b_if_lt = int(_float(sp.get("a_downgrade_to_b_if_sample_lt"), 5))
    a_medium_if_lt = int(_float(sp.get("a_mark_medium_sample_if_lt"), 8))
    if sample_size < min_for_ab and grade in ("A", "B"):
        grade = "C" if ht_score >= _float(gC.get("min_ht_score"), 50.0) else "SKIP"
        risks.append({"priority": 1, "code": "sample_force_downgrade", "text": "样本数<3，强制降级"})
    elif sample_size < a_to_b_if_lt and grade == "A":
        grade = "B"
        risks.append({"priority": 1, "code": "a_to_b_sample_lt_5", "text": "样本数<5，A级降为B级"})
    elif sample_size < a_medium_if_lt and grade == "A":
        risks.append({"priority": 3, "code": "a_medium_sample", "text": "A级样本中等（5-7场）"})
    elif sample_size >= int(_float(sp.get("confidence_boost_if_sample_gte"), 10)):
        reason_candidates.append((82, "样本量较充足（>=10场）"))

    # 方向冲突提示（按最终 grade 输出不同文案）
    if market_focus != "HT_LIVE_OVER":
        best_focus_label = _best_focus_label(best_focus)
        if grade in ("A", "B"):
            text = f"方向提示：系统总分最强为{best_focus_label}，但HT数据达到推荐级，人工决策时注意区分"
        elif grade == "C":
            text = f"方向提示：系统总分最强为{best_focus_label}，HT仅观察，不作为主推荐"
        else:
            text = f"方向提示：系统总分最强为{best_focus_label}；HT数据未达推荐级，本场跳过上半场推荐"
        risks.append({"priority": 2, "code": "direction_conflict", "text": text})

    sorted_risks = _sort_risks(risks)
    risk_texts = [x["text"] for x in sorted_risks]
    risk_top = risk_texts[0] if risk_texts else ""
    risk_severity = "LOW"
    if sorted_risks:
        p = int(sorted_risks[0].get("priority", 3))
        risk_severity = "HIGH" if p <= 1 else ("MID" if p == 2 else "LOW")

    # 推荐理由 Top3（跳过时优先给跳过原因）
    if grade == "SKIP":
        skip_reason_candidates: list[tuple[int, str]] = []
        if h2h_ht < _float(skip_rules.get("min_h2h_ht_goal_rate"), 0.50):
            skip_reason_candidates.append((100, f"HT有球率 {_pct_text(h2h_ht)} < 50%"))
        if avg_ht_goals < _float(skip_rules.get("min_ht_avg_goals"), 0.60):
            skip_reason_candidates.append((98, f"上半场场均进球 {avg_ht_goals:.2f} < 0.60"))
        if late_11_45 < _float(skip_rules.get("min_late_11_45"), 0.45):
            skip_reason_candidates.append((96, f"11-45分钟压力 {_pct_text(late_11_45)} 偏弱"))
        if early_only_flag:
            skip_reason_candidates.append((90, "early_only_flag=true"))
        if pullback_fit == "WEAK":
            skip_reason_candidates.append((88, "pullback_fit=WEAK"))
        reasons_top3 = [t for _, t in sorted(skip_reason_candidates, reverse=True)[:3]]
        if not reasons_top3:
            reasons_top3 = ["综合评分不足，未达上半场推荐标准"]
    else:
        reasons_top3 = [t for _, t in sorted(reason_candidates, reverse=True)[:3]]

    status_map = {"A": "HT_PREMATCH_RECOMMEND", "B": "HT_PREMATCH_RECOMMEND", "C": "HT_OBSERVE", "SKIP": "HT_SKIP"}
    bucket_map = {"A": "HT_MAIN", "B": "HT_MAIN", "C": "HT_OBSERVE", "SKIP": "HT_SKIP"}
    reason_map = {
        "A": "上半场强推荐",
        "B": "上半场达标推荐",
        "C": "仅情报观察",
        "SKIP": "上半场基因不足",
    }
    return {
        "rule_version": rule_version,
        "grade": grade,
        "status": status_map[grade],
        "bucket": bucket_map[grade],
        "reason": reason_map[grade],
        "reasons": reasons_top3,
        "risks": risk_texts[:3],
        "risk_top": risk_top,
        "risk_severity": risk_severity,
        "script_type": script_type,
        "time_bins_source": tb_source,
        "ht_score": ht_score,
        "h2h_ht_goal_rate": h2h_ht,
        "ht_avg_goals": avg_ht_goals,
        "time_bins": {"0_15": p0_15, "16_30": p16_30, "31_45": p31_45},
        "sample_size": sample_size,
        "direction_focus": _best_focus_label(best_focus),
    }


def explain_match(record: dict) -> dict:
    factors = record.get("factors", {}) or {}
    scores = record.get("market_scores") or factors.get("market_scores") or {}
    market_focus = str(record.get("market_focus") or "HT_LIVE_OVER")
    phase_bias = factors.get("phase_bias", "BALANCED")

    ht_score = _float(scores.get("HT_LIVE_OVER"))
    sh_score = _float(scores.get("SECOND_HALF_OVER"))
    ft_score = _float(scores.get("FULLTIME_OVER"))
    h2h_ht = _float(factors.get("h2h_ht_goal_rate"))
    recent_ht = _float(factors.get("recent_form_avg"))
    recent_sh = _float(factors.get("recent_sh_avg"))
    ht_attack = _float(factors.get("ht_attack_vs_defense"))

    effective_tb, _tb_source = _time_bins_with_fallback(factors)
    sh_tb = factors.get("second_half_bins", {}) or {}
    early_0_10 = _float(effective_tb.get("0_10"))
    late_11_45 = _float(effective_tb.get("11_45"))
    pullback_fit = factors.get("pullback_fit") or factors.get("recent_timing_fit") or "-"
    # 当 H2H time_bins 全 0 且 recent_timing_fit 有有效值时，用 recent 回退
    _tb_has = any(float(v or 0) > 0 for v in (effective_tb or {}).values())
    if not _tb_has and factors.get("recent_timing_fit") not in (None, "-", "WEAK"):
        pullback_fit = factors.get("recent_timing_fit")

    match_type: list[str] = []
    why: list[str] = []
    wait_for: list[str] = []
    avoid_if: list[str] = ["红牌", "重大伤退"]

    early_flash = early_0_10 >= 0.35 and pullback_fit == "WEAK"
    sh_surge = (
        market_focus == "SECOND_HALF_OVER"
        or phase_bias == "SECOND_HALF_BIAS"
        or (sh_score >= max(ht_score, ft_score) and sh_score - ht_score >= 12 and recent_sh >= 0.70)
    )
    ft_open = ft_score >= max(ht_score, sh_score)

    if early_flash:
        match_type.append("EARLY_FLASH")
        why.append(f"0-10分钟热度 {_pct_text(early_0_10)}，但回调适配 WEAK")
    if late_11_45 >= 0.50 and pullback_fit in ("OK", "STRONG"):
        match_type.append("HT_PULLBACK")
        why.append(f"11-45压力 {_pct_text(late_11_45)}")
    if sh_surge:
        match_type.append("SH_SURGE")
        why.append(f"下半场信号更强：SH {sh_score:.1f} vs HT {ht_score:.1f}")
    if ft_open:
        match_type.append("FT_OPEN_GAME")
    if not match_type:
        match_type.append("NO_CLEAR_EDGE")
        why.append("HT/SH/FT方向不够集中")

    ht_recommendation = build_ht_recommendation(record)
    grade = ht_recommendation.get("grade", "SKIP")
    ht_decision = {
        "action": f"HT_{grade}",
        "bucket": ht_recommendation.get("bucket", "HT_SKIP"),
        "is_main_recommendation": grade in ("A", "B"),
        "reason": ht_recommendation.get("reason", ""),
    }

    sh_observation = None
    if sh_surge:
        sh_observation = {
            "action": "SH_OBSERVE_ONLY",
            "bucket": "SH_OBSERVE",
            "is_main_recommendation": False,
            "reason": "下半场倾向更强，但不计入HT主推荐",
            "trade_action": "下半场观察：不属于V4_HT主推荐",
        }

    action_code = ht_decision["action"]
    recommendation_bucket = ht_decision["bucket"]
    primary_direction = "HT"
    is_live_radar = bool(record.get("is_watch")) and market_focus == "HT_LIVE_OVER"

    if grade in ("A", "B"):
        execution_status = f"上半场推荐 {grade}级"
        trade_action = "情报推荐：由你决定是否投注与入场时机"
        profile = f"画像：HT赛前推荐({ht_recommendation.get('script_type')})"
        summary = "结论：推荐进入今日上半场重点关注清单"
        wait_for = ["关注0-15/16-30/31-45分布", "结合临场节奏自行决策"]
    elif grade == "C":
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

    confidence = 40
    confidence += min(max(ht_score, sh_score, ft_score), 90) * 0.35
    confidence += 10 if h2h_ht >= 0.70 else 0
    confidence += 8 if recent_ht >= 0.70 or recent_sh >= 0.70 else 0
    confidence += 6 if ht_attack >= 0.65 else 0
    confidence = int(max(0, min(round(confidence), 95)))

    if grade == "SKIP":
        risk_level = "HIGH"
    elif grade in ("A", "B"):
        risk_level = "LOW"
    else:
        risk_level = "MID"

    ev_label = "情报推荐"
    if confidence >= 75:
        ev_label = "推荐强"
    elif confidence >= 60:
        ev_label = "推荐中"

    execution_label = "仅情报"
    if grade in ("A", "B"):
        execution_label = "主推荐"
    elif grade == "C":
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

