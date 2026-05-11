"""
V4 首发强度识别器
=================
用途:
  1. 用球队最近 N 场首发自动构建 expected_core_xi
  2. 用当前比赛首发比对常规主力阵容
  3. 给走地半场大球策略输出 KEEP_WATCH / BOOST / DROP 信号

设计原则:
  - 不靠人工记名字，优先用历史首发频率识别主力。
  - 大球方向拆成攻击完整度和防线不稳定度，而不是笼统的"战力下降"。
  - 如果当前首发或历史首发覆盖不足，返回 LINEUP_PENDING / LINEUP_UNKNOWN，不硬判。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable, Optional


RECENT_MATCHES = 10
MIN_HISTORY_LINEUPS = 4


ATTACK_POS = {"F"}
MID_POS = {"M"}
DEFENSE_POS = {"G", "D"}
ATTACK_UNIT_POS = {"F", "M"}
DEFENSE_UNIT_POS = {"G", "D", "M"}


@dataclass
class PlayerProfile:
    player_id: str
    name: str
    pos: str
    starts: int
    start_rate: float
    importance: float


def _safe_response(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    data = resp.get("response", [])
    return data if isinstance(data, list) else []


def _extract_team_lineup(lineups: list, team_id: int) -> Optional[dict]:
    for lineup in lineups:
        team = lineup.get("team", {}) if isinstance(lineup, dict) else {}
        if str(team.get("id", "")) == str(team_id):
            return lineup
    return None


def _extract_start_xi(lineup: Optional[dict]) -> list[dict]:
    if not lineup:
        return []
    starters = []
    for item in lineup.get("startXI", []) or []:
        player = item.get("player", {}) if isinstance(item, dict) else {}
        pid = player.get("id")
        name = player.get("name") or player.get("firstname") or "Unknown"
        pos = player.get("pos") or player.get("position") or "?"
        if not pid:
            continue
        starters.append({
            "id": str(pid),
            "name": str(name),
            "pos": str(pos)[:1].upper() if pos else "?",
        })
    return starters


def _role_weight(pos: str) -> float:
    """半场大球方向的位置权重。"""
    pos = (pos or "?").upper()
    if pos == "F":
        return 1.20
    if pos == "M":
        return 1.00
    if pos == "D":
        return 0.90
    if pos == "G":
        return 0.80
    return 0.70


class LineupStrengthAnalyzer:
    """基于 API-Football lineups 的主力阵容识别器。"""

    def __init__(self, api_client: Callable[[str], Optional[dict]], recent_matches: int = RECENT_MATCHES):
        self.api_client = api_client
        self.recent_matches = recent_matches
        self._fixture_lineup_cache: dict[int, list] = {}
        self._team_core_cache: dict[int, dict] = {}

    def _get_lineups(self, fixture_id: int) -> list:
        if fixture_id in self._fixture_lineup_cache:
            return self._fixture_lineup_cache[fixture_id]
        resp = self.api_client(f"fixtures/lineups?fixture={fixture_id}")
        lineups = _safe_response(resp)
        self._fixture_lineup_cache[fixture_id] = lineups
        return lineups

    def _get_recent_fixture_ids(self, team_id: int) -> list[int]:
        resp = self.api_client(f"fixtures?team={team_id}&last={self.recent_matches}&status=FT")
        ids = []
        for item in _safe_response(resp):
            fid = item.get("fixture", {}).get("id")
            if fid:
                ids.append(int(fid))
        return ids

    def build_core_xi(self, team_id: int) -> dict:
        """用最近 N 场首发频率构建常规主力 XI。"""
        if team_id in self._team_core_cache:
            return self._team_core_cache[team_id]

        fixture_ids = self._get_recent_fixture_ids(team_id)
        start_counts = Counter()
        name_by_id = {}
        pos_by_id = {}
        usable_lineups = 0

        for fid in fixture_ids:
            lineups = self._get_lineups(fid)
            lineup = _extract_team_lineup(lineups, team_id)
            starters = _extract_start_xi(lineup)
            if not starters:
                continue
            usable_lineups += 1
            for p in starters:
                pid = p["id"]
                start_counts[pid] += 1
                name_by_id[pid] = p["name"]
                pos_by_id[pid] = p["pos"]

        profiles = []
        denominator = max(usable_lineups, 1)
        for pid, starts in start_counts.items():
            pos = pos_by_id.get(pid, "?")
            start_rate = starts / denominator
            importance = round(start_rate * _role_weight(pos), 4)
            profiles.append(PlayerProfile(
                player_id=pid,
                name=name_by_id.get(pid, "Unknown"),
                pos=pos,
                starts=starts,
                start_rate=round(start_rate, 3),
                importance=importance,
            ))

        profiles.sort(key=lambda x: (x.importance, x.starts), reverse=True)
        core_xi = profiles[:11]

        result = {
            "team_id": team_id,
            "history_fixture_count": len(fixture_ids),
            "usable_lineups": usable_lineups,
            "coverage": round(usable_lineups / max(len(fixture_ids), 1), 3),
            "core_xi": [p.__dict__ for p in core_xi],
            "core_ids": {p.player_id for p in core_xi},
        }
        self._team_core_cache[team_id] = result
        return result

    def analyze_team_lineup(self, fixture_id: int, team_id: int, team_name: str = "") -> dict:
        """分析单队当前首发强度。"""
        core = self.build_core_xi(team_id)
        lineups = self._get_lineups(fixture_id)
        current_lineup = _extract_team_lineup(lineups, team_id)
        actual_xi = _extract_start_xi(current_lineup)

        base = {
            "team_id": team_id,
            "team_name": team_name,
            "history_usable_lineups": core["usable_lineups"],
            "history_coverage": core["coverage"],
            "core_xi": core["core_xi"],
            "actual_xi": actual_xi,
        }

        if core["usable_lineups"] < MIN_HISTORY_LINEUPS:
            return {
                **base,
                "lineup_signal": "LINEUP_UNKNOWN",
                "warning": f"历史首发样本不足: {core['usable_lineups']} < {MIN_HISTORY_LINEUPS}",
            }

        if not actual_xi:
            return {
                **base,
                "lineup_signal": "LINEUP_PENDING",
                "warning": "当前首发名单暂未公布",
            }

        actual_ids = {p["id"] for p in actual_xi}
        core_profiles = [PlayerProfile(**p) for p in core["core_xi"]]
        core_ids = {p.player_id for p in core_profiles}

        present_core = [p for p in core_profiles if p.player_id in actual_ids]
        missing_core = [p for p in core_profiles if p.player_id not in actual_ids]
        rotation_count = max(0, 11 - len(present_core))

        def _availability(positions: set[str]) -> float:
            bucket = [p for p in core_profiles if p.pos in positions]
            if not bucket:
                return 1.0
            total = sum(max(p.importance, 0.01) for p in bucket)
            present = sum(max(p.importance, 0.01) for p in bucket if p.player_id in actual_ids)
            return round(present / total, 3)

        attack_core_available = _availability(ATTACK_POS)
        midfield_available = _availability(MID_POS)
        defense_core_available = _availability(DEFENSE_POS)
        attack_available = _availability(ATTACK_UNIT_POS)
        defense_available = _availability(DEFENSE_UNIT_POS)
        defense_instability = round(1.0 - defense_available, 3)

        attack_core = [p for p in core_profiles if p.pos in ATTACK_POS]
        midfield_core = [p for p in core_profiles if p.pos in MID_POS]
        defense_core = [p for p in core_profiles if p.pos in DEFENSE_POS]
        missing_attackers = [p.__dict__ for p in missing_core if p.pos in ATTACK_POS]
        missing_midfielders = [p.__dict__ for p in missing_core if p.pos in MID_POS]
        missing_defenders = [p.__dict__ for p in missing_core if p.pos in DEFENSE_POS]

        attack_signal = (
            "ATTACK_FULL"
            if attack_core_available >= 0.80
            else "ATTACK_OK"
            if attack_available >= 0.70
            else "ATTACK_WEAK"
        )
        defense_signal = (
            "DEFENSE_STABLE"
            if defense_instability < 0.20
            else "DEFENSE_GAP"
            if defense_instability < 0.40
            else "DEFENSE_HEAVY_GAP"
        )

        if rotation_count >= 5:
            signal = "DROP_HEAVY_ROTATION"
        elif attack_available < 0.50 or attack_core_available < 0.45:
            signal = "DROP_ATTACK_WEAK"
        elif attack_available >= 0.75 and defense_instability >= 0.30:
            signal = "BOOST_OVER"
        elif attack_available >= 0.70:
            signal = "KEEP_WATCH"
        else:
            signal = "WATCH_CAUTION"

        return {
            **base,
            "formation": current_lineup.get("formation") if current_lineup else None,
            "core_present": len(present_core),
            "rotation_count": rotation_count,
            "attack_core_count": len(attack_core),
            "attack_core_present": len([p for p in attack_core if p.player_id in actual_ids]),
            "midfield_core_count": len(midfield_core),
            "midfield_core_present": len([p for p in midfield_core if p.player_id in actual_ids]),
            "defense_core_count": len(defense_core),
            "defense_core_present": len([p for p in defense_core if p.player_id in actual_ids]),
            "attack_core_available": attack_core_available,
            "midfield_available": midfield_available,
            "defense_core_available": defense_core_available,
            "attack_unit_available": attack_available,
            "defense_unit_available": defense_available,
            "defense_instability": defense_instability,
            "missing_key_attackers": missing_attackers,
            "missing_key_midfielders": missing_midfielders,
            "missing_key_defenders": missing_defenders,
            "attack_signal": attack_signal,
            "defense_signal": defense_signal,
            "lineup_signal": signal,
            "warning": None,
        }

    def analyze_fixture(self, fixture: dict) -> dict:
        """分析一场比赛双方首发，输出 V4 走地观察决策。"""
        fixture_id = int(fixture["id"])
        home = self.analyze_team_lineup(fixture_id, int(fixture["homeId"]), fixture.get("home", ""))
        away = self.analyze_team_lineup(fixture_id, int(fixture["awayId"]), fixture.get("away", ""))

        signals = {home.get("lineup_signal"), away.get("lineup_signal")}
        if "LINEUP_PENDING" in signals:
            action = "LINEUP_PENDING"
            reason = "首发尚未公布，保持赛前观察池"
        elif "LINEUP_UNKNOWN" in signals:
            action = "KEEP_WATCH_LIGHT"
            reason = "历史首发覆盖不足，阵容因子降权"
        elif any(s in signals for s in ("DROP_HEAVY_ROTATION", "DROP_ATTACK_WEAK")):
            action = "DROP"
            reason = "首发攻击端不足或大轮换"
        elif "BOOST_OVER" in signals and min(
            home.get("attack_unit_available", 0),
            away.get("attack_unit_available", 0),
        ) >= 0.55:
            action = "BOOST"
            reason = "攻击端可用且存在防线缺口，走地大球优先级提升"
        elif min(home.get("attack_unit_available", 0), away.get("attack_unit_available", 0)) >= 0.65:
            action = "KEEP_WATCH"
            reason = "双方攻击核心可用，继续等待走地买点"
        else:
            action = "WATCH_CAUTION"
            reason = "阵容没有否决，但进攻完整度一般"

        return {
            "fixture_id": fixture_id,
            "checked_at_stage": "T_MINUS_30_LINEUP_GATE",
            "home": home,
            "away": away,
            "lineup_action": action,
            "lineup_reason": reason,
        }
