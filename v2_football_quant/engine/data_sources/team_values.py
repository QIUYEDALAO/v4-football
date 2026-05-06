"""
V3 世界杯: 球队估值数据
======================
来源: Transfermarkt 公开数据 (2026年近似值)
非实时爬虫 — 身价不常变, 赛前一次手工确认即可
"""

# 球队总身价 (亿欧元) — 基于公开 Transfermarkt 2026 年数据近似
TEAM_MARKET_VALUES = {
    "EN": 15.0,  # 英格兰
    "FR": 12.0,  # 法国
    "BR": 11.0,  # 巴西
    "ES": 10.0,  # 西班牙
    "AR": 9.0,   # 阿根廷
    "PT": 8.5,   # 葡萄牙
    "DE": 8.0,   # 德国
    "NL": 7.0,   # 荷兰
    "IT": 6.5,   # 意大利
    "BE": 5.5,   # 比利时
    "UY": 4.5,   # 乌拉圭
    "HR": 4.0,   # 克罗地亚
    "DK": 3.5,   # 丹麦
    "CO": 3.5,   # 哥伦比亚
    "CH": 3.0,   # 瑞士
    "RS": 3.0,   # 塞尔维亚
    "NO": 4.5,   # 挪威
    "TR": 3.5,   # 土耳其
    "AT": 3.0,   # 奥地利
    "PL": 3.0,   # 波兰
    "JP": 3.5,   # 日本
    "KR": 2.5,   # 韩国
    "IR": 1.5,   # 伊朗
    "AU": 1.5,   # 澳大利亚
    "MA": 4.0,   # 摩洛哥
    "SN": 3.0,   # 塞内加尔
    "NG": 2.5,   # 尼日利亚
    "EG": 2.0,   # 埃及
    "DZ": 1.5,   # 阿尔及利亚
    "US": 3.5,   # 美国
    "MX": 3.0,   # 墨西哥
    "CA": 2.0,   # 加拿大
    "EC": 2.0,   # 厄瓜多尔
    "PY": 1.5,   # 巴拉圭
    "VE": 1.0,   # 委内瑞拉
    "CZ": 2.5,   # 捷克
    "GR": 2.0,   # 希腊
    "UA": 2.0,   # 乌克兰
    "PA": 0.5,   # 巴拿马
    "UZ": 0.5,   # 乌兹别克斯坦
}


def get_team_value(code: str) -> float:
    """返回球队总身价 (亿欧元)"""
    return TEAM_MARKET_VALUES.get(code, 1.0)


def get_value_rank(code: str) -> int:
    """按身价排名 (1=最贵)"""
    sorted_teams = sorted(TEAM_MARKET_VALUES.items(), key=lambda x: x[1], reverse=True)
    for rank, (c, _) in enumerate(sorted_teams, 1):
        if c == code:
            return rank
    return 99
