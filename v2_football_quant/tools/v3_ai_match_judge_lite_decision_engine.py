#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Decision = Literal["PLAY", "WAIT", "OBSERVE", "PASS"]
LineupStatus = Literal["CONFIRMED", "WAIT_EVENT", "MISSING"]
OddsHandicapStatus = Literal["PRESENT", "WAIT_EVENT", "MISSING"]
MarketCheck = Literal["SUPPORT", "NEUTRAL", "CONFLICT"]
MatchType = Literal["FRIENDLY", "WORLDCUP", "OTHER"]
RotationRisk = Literal["LOW", "MEDIUM", "HIGH"]


@dataclass(frozen=True)
class DecisionInput:
    lineup_status: LineupStatus
    odds_handicap_status: OddsHandicapStatus
    score_gap: float
    market_check: MarketCheck
    match_type: MatchType
    rotation_risk: RotationRisk


@dataclass(frozen=True)
class DecisionOutput:
    final_decision: Decision
    rule_id: str
    guard_result: dict[str, str]
    downgrade_reason: str | None
    ledger_required: bool


def deterministic_decision(decision_input: DecisionInput) -> DecisionOutput:
    """Fixed V3 Lite decision rules. Thresholds are intentionally not dynamic."""
    guard = {
        "lineup_check": "PASS" if decision_input.lineup_status == "CONFIRMED" else "WAIT",
        "odds_handicap_check": "PASS" if decision_input.odds_handicap_status == "PRESENT" else "WAIT",
        "mode_check": "DOWNGRADE_FRIENDLY" if decision_input.match_type == "FRIENDLY" else "PASS",
        "ledger_check": "REQUIRED",
    }

    if decision_input.lineup_status != "CONFIRMED":
        return _output("WAIT", "LINEUP_NOT_CONFIRMED", guard, "lineup_status_not_confirmed")
    if decision_input.odds_handicap_status != "PRESENT":
        return _output("WAIT", "ODDS_HANDICAP_NOT_PRESENT", guard, "odds_handicap_not_present")
    if decision_input.market_check == "CONFLICT":
        return _output("PASS", "MARKET_CONFLICT", guard, "market_conflict")

    if decision_input.rotation_risk == "HIGH":
        if decision_input.score_gap >= 8 and decision_input.market_check == "SUPPORT":
            return _output("OBSERVE", "HIGH_ROTATION_DOWNGRADE_PLAY_TO_OBSERVE", guard, "rotation_risk_high")
        return _output("PASS", "HIGH_ROTATION_DOWNGRADE_TO_PASS", guard, "rotation_risk_high")

    if (
        decision_input.score_gap >= 8
        and decision_input.market_check == "SUPPORT"
        and decision_input.match_type != "FRIENDLY"
    ):
        return _output("PLAY", "SCORE_GAP_8_MARKET_SUPPORT_NON_FRIENDLY", guard, None)
    if decision_input.score_gap >= 8 and decision_input.match_type == "FRIENDLY":
        return _output("OBSERVE", "SCORE_GAP_8_FRIENDLY_DOWNGRADE", guard, "friendly_mode")
    if 5 <= decision_input.score_gap < 8:
        return _output("OBSERVE", "SCORE_GAP_5_TO_7", guard, None)
    return _output("PASS", "SCORE_GAP_BELOW_5", guard, "score_gap_below_threshold")


def _output(
    final_decision: Decision,
    rule_id: str,
    guard_result: dict[str, str],
    downgrade_reason: str | None,
) -> DecisionOutput:
    guard = dict(guard_result)
    guard["overall"] = final_decision
    if final_decision == "PLAY":
        guard["overall"] = "PLAY"
    return DecisionOutput(
        final_decision=final_decision,
        rule_id=rule_id,
        guard_result=guard,
        downgrade_reason=downgrade_reason,
        ledger_required=True,
    )


def decision_to_dict(output: DecisionOutput) -> dict:
    return asdict(output)
