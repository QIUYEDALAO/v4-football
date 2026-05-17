"""engine/v4_display_name_normalizer.py — V4中文队名/联赛名规范化

确定性中文队名映射，不调用LLM，不联网。
通过 .append_new() 方法逐步扩充别名表。
对未知名称保留原名并记录到 untranslated_names。
"""

# ── 球队名中文映射 ──
_TEAM_CN = {
    # 丹超
    "FC Copenhagen": "哥本哈根",
    "Randers FC": "兰讷斯",
    "FC Fredericia": "弗雷德里西亚",
    "Silkeborg": "锡尔克堡",
    "Odense": "欧登塞",
    "Vejle": "瓦埃勒",
    "FC Midtjylland": "中日德兰",
    "Brondby": "布隆德比",
    "Aarhus": "奥胡斯",
    "Viborg": "维堡",
    "Sonderjyske": "桑德捷斯基",
    "FC Nordsjaelland": "北西兰",
    # 荷甲
    "Twente": "特温特",
    "AZ Alkmaar": "阿尔克马尔",
    "NAC Breda": "布雷达",
    "FC Volendam": "福伦丹",
    "Telstar": "特尔斯塔",
    "Heerenveen": "海伦芬",
    "Ajax": "阿贾克斯",
    "Heracles": "赫拉克勒斯",
    "Groningen": "格罗宁根",
    "NEC Nijmegen": "奈梅亨",
    "GO Ahead Eagles": "前进之鹰",
    "PSV Eindhoven": "埃因霍温",
    "Sparta Rotterdam": "鹿特丹斯巴达",
    "Excelsior": "埃克塞尔西奥",
    "Utrecht": "乌得勒支",
    "Fortuna Sittard": "锡塔德福图纳",
    "PEC Zwolle": "兹沃勒",
    "Feyenoord": "费耶诺德",
    # 德乙
    "SV Darmstadt 98": "达姆施塔特98",
    "SC Paderborn 07": "帕德博恩07",
    "Hannover 96": "汉诺威96",
    "1. FC Nürnberg": "纽伦堡",
    "1. FC Magdeburg": "马格德堡",
    "1. FC Kaiserslautern": "凯泽斯劳滕",
    "FC Schalke 04": "沙尔克04",
    "Eintracht Braunschweig": "布伦瑞克",
    "Dynamo Dresden": "德累斯顿迪纳摩",
    "Holstein Kiel": "荷尔斯泰因基尔",
    "Arminia Bielefeld": "比勒费尔德",
    "Hertha BSC": "柏林赫塔",
    "SV Elversberg": "埃尔沃斯堡",
    "Preußen Münster": "明斯特普鲁士",
    "SpVgg Greuther Fürth": "菲尔特",
    "Fortuna Düsseldorf": "杜塞尔多夫",
    "Karlsruher SC": "卡尔斯鲁厄",
    "VfL Bochum": "波鸿",
    # 希腊超
    "Levadiakos": "莱瓦贾科斯",
    "Aris Thessalonikis": "塞萨洛尼基阿瑞斯",
    "OFI": "OFI克里特",
    "Volos NFC": "沃洛斯",
    "AEK Athens FC": "雅典AEK",
    "Olympiakos Piraeus": "奥林匹亚科斯",
    "Panathinaikos": "帕纳辛纳科斯",
    "PAOK": "PAOK塞萨洛尼基",
    # 冰岛超
    "FH hafnarfjordur": "FH哈夫纳夫约杜尔",
    "KA Akureyri": "KA阿克雷里",
    "Keflavik": "凯夫拉维克",
    "Stjarnan": "斯塔尔南",
    "Valur Reykjavik": "雷克雅未克瓦鲁尔",
    "Breidablik": "贝雷达比历克",
    "IBV Vestmannaeyjar": "韦斯特曼纳岛",
    "Vikingur Reykjavik": "雷克雅未克维京古",
    "KR Reykjavik": "雷克雅未克KR",
    "Fram Reykjavik": "雷克雅未克弗拉姆",
    # 墨西联
    "U.N.A.M. - Pumas": "美洲狮",
    "CF Pachuca": "帕丘卡",
    # 印尼超
    "Bali United": "巴厘联",
    "Bhayangkara FC": "巴杨卡拉",
    # 立陶甲
    "TransINVEST Vilnius": "特兰斯投资维尔纽斯",
    "FK Zalgiris Vilnius": "萨尔吉里斯",
    # 阿联酋超
    "Al-Dhafra": "迪哈夫拉",
    "Al Wahda FC": "阿布扎比统一",
    "Al Ain": "阿尔艾因",
    "Dibba Al-Fujairah": "迪巴富查伊拉",
    "Al Shabab": "沙巴布",
    "Al-Ittihad FC": "吉达联合",
    # 西乙
    "Almeria": "阿尔梅里亚",
    "Las Palmas": "拉斯帕尔马斯",
    # 日职联
    "Cerezo Osaka": "大阪樱花",
    "Nagoya Grampus": "名古屋鲸八",
    "V-varen Nagasaki": "长崎航海",
    "Kawasaki Frontale": "川崎前锋",
    "Machida Zelvia": "町田泽维亚",
    # 捷克甲
    "Karviná": "卡尔维纳",
    "Sigma Olomouc": "奥洛穆茨",
    "Baník Ostrava": "俄斯特拉发",
    "Zlin": "兹林",
    "Hradec Králové": "赫拉德茨克拉洛韦",
    "Slavia Praha": "布拉格斯拉维亚",
    "Slovan Liberec": "利贝雷茨",
    "Sparta Praha": "布拉格斯巴达",
    "Plzen": "比尔森胜利",
    "FK Jablonec": "亚布洛内茨",
    # 匈甲
    "Diosgyori VTK": "迪欧斯捷尔",
    "Paks": "帕克斯",
    "Debreceni VSC": "德布勒森",
    "Ujpest": "乌伊佩斯特",
    # 瑞士超
    "FC Winterthur": "温特图尔",
    "FC Luzern": "卢塞恩",
    "FC Zurich": "苏黎世",
    "Servette FC": "塞尔维特",
    "FC Lugano": "卢加诺",
    "FC Basel 1893": "巴塞尔",
    "FC ST. Gallen": "圣加仑",
    "FC Thun": "图恩",
    "BSC Young Boys": "伯尔尼年轻人",
    "FC Sion": "锡永",
    # 土超
    "Gaziantep FK": "加济安泰普",
    "Başakşehir": "伊斯坦布尔巴萨克赛尔",
    "Samsunspor": "萨姆松体育",
    "Göztepe": "戈兹特佩",
    "Fenerbahçe": "费内巴切",
    "Eyüpspor": "埃于普体育",
    "Kasımpaşa": "卡斯帕萨",
    "Galatasaray": "加拉塔萨雷",
    "Antalyaspor": "安塔利亚体育",
    "Kocaelispor": "科贾埃利体育",
    "Trabzonspor": "特拉布宗体育",
    "Kayserispor": "开塞利体育",
    "Konyaspor": "科尼亚体育",
    # 克亚甲
    "NK Slaven Belupo": "斯拉文贝鲁波",
    "Dinamo Zagreb": "萨格勒布迪纳摩",
    "Istra 1961": "伊斯特拉1961",
    "HNK Rijeka": "里耶卡",
    "NK Lokomotiva Zagreb": "萨格勒布火车头",
    "HNK Hajduk Split": "哈伊杜克斯普利特",
    # 塞尔超
    "Radnik Surdulica": "苏杜利察拉德尼克",
    "FK Crvena Zvezda": "贝尔格莱德红星",
    "Cukaricki": "丘卡里奇",
    "FK Partizan": "贝尔格莱德游击",
    "Novi Pazar": "新帕扎尔",
    "Vojvodina": "伏伊伏丁那",
    # 沙特联
    "利雅得青年": "利雅得青年",
    # 西甲
    "FC Barcelona": "巴塞罗那",
    "Real Betis": "皇家贝蒂斯",
    "Athletic Club": "毕尔巴鄂竞技",
    "Celta Vigo": "塞尔塔",
    "Sevilla": "塞维利亚",
    "Real Madrid": "皇家马德里",
    # 苏超
    "Dundee": "邓迪FC",
    "Aberdeen": "阿伯丁",
    "Livingston": "利文斯顿",
    "Kilmarnock": "基尔马诺克",
    "ST Mirren": "圣米伦",
    "Dundee Utd": "邓迪联",
    # 英超
    "Manchester United": "曼联",
    "Nottingham Forest": "诺丁汉森林",
    "Brentford": "布伦特福德",
    "Crystal Palace": "水晶宫",
    "Everton": "埃弗顿",
    "Sunderland": "桑德兰",
    "Leeds": "利兹联",
    "Brighton": "布莱顿",
    "Wolves": "狼队",
    "Fulham": "富勒姆",
    "Newcastle": "纽卡斯尔联",
    "West Ham": "西汉姆联",
    # 意甲
    "Inter": "国际米兰",
    "Hellas Verona": "维罗纳",
    "Genoa": "热那亚",
    "AC Milan": "AC米兰",
    "Juventus": "尤文图斯",
    "Fiorentina": "佛罗伦萨",
    "Pisa": "比萨",
    "Napoli": "那不勒斯",
    "AS Roma": "罗马",
    "Lazio": "拉齐奥",
    "Atalanta": "亚特兰大",
    "Bologna": "博洛尼亚",
    "Cagliari": "卡利亚里",
    "Torino": "都灵",
    "Sassuolo": "萨索洛",
    "Lecce": "莱切",
    "Udinese": "乌迪内斯",
    "Cremonese": "克雷莫纳",
    "Como": "科莫",
    "Parma": "帕尔马",
    # 法甲
    "Brestois 29": "布雷斯特",
    "Angers": "昂热",
    "Paris FC": "巴黎FC",
    "Paris Saint Germain": "巴黎圣日耳曼",
    "Strasbourg": "斯特拉斯堡",
    "Monaco": "摩纳哥",
    "Marseille": "马赛",
    "Rennes": "雷恩",
    "Nice": "尼斯",
    "Metz": "梅斯",
    "Lille": "里尔",
    "Auxerre": "欧塞尔",
    "Lorient": "洛里昂",
    "Le Havre": "勒阿弗尔",
    "Lyon": "里昂",
    "Lens": "朗斯",
    "Nantes": "南特",
    "Toulouse": "图卢兹",
    # 美职业
    "CF Montreal": "蒙特利尔CF",
    "Chicago Fire": "芝加哥火焰",
    "Houston Dynamo": "休斯顿迪纳摩",
    "Vancouver Whitecaps": "温哥华白帽",
    "San Jose Earthquakes": "圣何塞地震",
    "FC Dallas": "达拉斯FC",
    "Inter Miami": "迈阿密国际",
    "Portland Timbers": "波特兰伐木工",
    "Nashville SC": "纳什维尔SC",
    "Los Angeles FC": "洛杉矶FC",
    # 巴西甲
    "Atletico-MG": "米内罗竞技",
    "Mirassol": "米拉索尔",
    "Bahia": "巴伊亚",
    "Gremio": "格雷米奥",
    "Botafogo": "博塔弗戈",
    "Corinthians": "科林蒂安",
    "RB Bragantino": "布拉甘蒂诺",
    "Vitoria": "维多利亚",
    "Atletico Paranaense": "巴拉纳竞技",
    "Flamengo": "弗拉门戈",
    "Santos": "桑托斯",
    "Coritiba": "科里蒂巴",
    # 秘鲁甲
    "FBC Melgar": "梅尔加",
    "Sport Huancayo": "万卡约体育",
    "Sport Boys": "体育男孩",
    "Cusco": "库斯科",
    "Cienciano": "科学卡诺",
    "Alianza Lima": "利马联盟",
    # 玻利甲
    "Oriente Petrolero": "东方石油",
    "Guabirá": "瓜比拉",
    "The Strongest": "最强",
    "宾托大学": "宾托大学",
    "玻利瓦尔": "玻利瓦尔",
    # 阿联酋
    "Al Dhafra": "迪哈夫拉",
    "Ajman": "阿治曼",
    "Al Nasr": "迪拜胜利",
    "Al-Wasl": "迪拜祈祷",
    "Al Wasl": "迪拜祈祷",
    "Al-Ittihad Kalba": "伊蒂哈德卡尔巴",
    # 其他
    "Austria Vienna": "奥地利维也纳",
    "Lask Linz": "林茨",
    "Red Bull Salzburg": "萨尔茨堡红牛",
    "TSV Hartberg": "哈特贝格",
    "Sturm Graz": "格拉茨风暴",
    "Rapid Vienna": "维也纳快速",
    "GKS Katowice": "卡托维兹",
    "Jagiellonia": "雅盖隆尼亚",
    "Piast Gliwice": "皮亚斯特",
    "Raków Częstochowa": "琴斯托霍瓦拉科夫",
    "Lechia Gdansk": "莱吉亚",
    "Legia Warszawa": "华沙莱吉亚",
    "SC Delhi": "德里SC",
    "Inter Kashi": "卡什国际",
    "Kolos Kovalivka": "科洛斯",
    "Obolon'-Brovar": "奥博隆",
    "Karpaty": "卡尔帕蒂",
    "Veres Rivne": "维雷斯",
    "Kryvbas KR": "克里夫巴斯",
    "Shakhtar Donetsk": "顿涅茨克矿工",
    "CSKA Moscow": "莫斯科中央陆军",
    "Lokomotiv": "莫斯科火车头",
    "Dinamo Makhachkala": "马哈奇卡拉迪纳摩",
    "Spartak Moscow": "莫斯科斯巴达",
    "FC Rostov": "罗斯托夫",
    "Zenit": "泽尼特",
    "FC Krasnodar": "克拉斯诺达尔",
    "FC Orenburg": "奥伦堡",
    "Krylia Sovetov": "苏维埃之翼",
    "Akron": "阿克伦",
    "Rubin": "喀山红宝石",
    "Nizhny Novgorod": "下诺夫哥罗德",
    "FC Sochi": "索契",
    "Akhmat": "艾哈迈德格罗兹尼",
    "Club Brugge KV": "布鲁日",
    "Union St. Gilloise": "圣吉罗斯",
    "Anderlecht": "安德莱赫特",
    "KV Mechelen": "梅赫伦",
    "Lommel United": "洛默尔",
    "Dender": "登德尔",
    "Cercle Brugge": "色格拉布鲁日",
    "Gent": "根特",
    # 复盘补充
    "锡永": "锡永",
    "卢加诺": "卢加诺",
    "图恩": "图恩",
    "年轻人": "年轻人",
    "瓦伦西亚": "瓦伦西亚",
    "巴列卡诺": "巴列卡诺",
    "索菲亚火车头": "索菲亚火车头",
    "贝罗": "贝罗",
    "Always Ready": "时刻准备",
}

# ── 联赛名中文映射 ──
_LEAGUE_CN = {
    "Pro League": "阿联酋职业联赛",
    "Segunda División": "西乙",
    "Czech Liga": "捷克甲",
    "NB I": "匈牙利甲",
    "Super League": "瑞士超",
    "Süper Lig": "土超",
    "J1 League": "日职联",
    "Championship": "英冠",
    "League One": "英甲",
    "2. Bundesliga": "德乙",
    "Serie A": "意甲",
    "Serie B": "意乙",
    "Ligue 1": "法甲",
    "Ligue 2": "法乙",
    "Eredivisie": "荷甲",
    "Eerste Divisie": "荷乙",
    "Primeira Liga": "葡超",
    "Jupiler Pro League": "比甲",
    "Challenger Pro League": "比乙",
    "Premier League": "英超",
    "La Liga": "西甲",
    "Bundesliga": "德甲",
    "Major League Soccer": "美职业",
    "Liga MX": "墨西联",
    "Campeonato Brasileiro": "巴西甲",
    "Primera División": "阿甲",
    "Liga 1": "秘鲁甲",
    "LFPB": "玻利甲",
    "K League 1": "韩K联",
    "K League 2": "韩K2联",
    "A-League": "澳超",
    "Allsvenskan": "瑞典超",
    "Eliteserien": "挪超",
    "Superliga": "丹超",
    "Super Lig": "土超",
    "Greek Super League": "希腊超",
    "Super League Greece": "希腊超",
    "Uruguayan Primera División": "乌拉甲",
    "Liga 1 Indonesia": "印尼超",
    "Indian Super League": "印度超",
    "Saudi Pro League": "沙特联",
    "Russian Premier League": "俄超",
    "Ukrainian Premier League": "乌克超",
    "Croatian First League": "克亚甲",
    "Austrian Bundesliga": "奥甲",
    "Swiss Super League": "瑞士超",
    "Scottish Premiership": "苏超",
    "Icelandic League": "冰岛超",
    "Egyptian Premier League": "埃及超",
    "Czech First League": "捷克甲",
    "Slovak Super Liga": "斯洛伐超",
    "Hungarian NB I": "匈牙利甲",
    "Serbian Super Liga": "塞尔超",
    "Polish Ekstraklasa": "波兰超",
    "Liga Portugal": "葡超",
    "Pro League": "阿联酋职业联赛",
    "Czech Liga": "捷克甲",
    "NB I": "匈牙利甲",
    "Super League": "瑞士超",
    "Süper Lig": "土超",
    "J1 League": "日职联",
    "Segunda División": "西乙",
    "Liga 1 Indonesia": "印尼超",
    "Icelandic League": "冰岛超",
    "Liga 1": "秘鲁甲",
    "LFPB": "玻利甲",
    "Super Liga": "塞尔超",
    "Liga Portugal": "葡超",
}


def team_cn(name: str) -> str:
    """Convert team name to Chinese, fallback to original."""
    if not name:
        return name
    return _TEAM_CN.get(name, name)


def league_cn(name: str) -> str:
    """Convert league name to Chinese, fallback to original."""
    if not name:
        return name
    return _LEAGUE_CN.get(name, name)


def display_name(name: str, is_league: bool = False) -> str:
    """Normalize a display name (team or league) to Chinese. Records unknowns."""
    if is_league:
        return league_cn(name)
    return team_cn(name)


def append_new(cn_map: dict, name: str, cn_name: str) -> None:
    """Add a new translation to the in-memory map (for hot-patching).
    Does NOT persist to file.
    """
    cn_map[name] = cn_name


# ── Collect untranslated names from text ──
def find_untranslated(text: str) -> list:
    """Scan text for capitalized words that might be untranslated team names.
    Returns list of potential untranslated names.
    """
    import re
    # Find capitalized multi-word patterns that aren't Chinese
    candidates = set()
    # Simple heuristic: words with first letter uppercase, 2+ chars
    for word in re.findall(r'\b[A-Z][a-zA-ZÀ-ÿ\.\-]+\b', text):
        if len(word) >= 3 and word not in ("HT", "FT", "FC", "SC", "AC", "US", "CF", "RB", "KA", "FH",
                                             "NK", "FK", "AEK", "HNK", "OFI", "KR", "PAOK", "SC"):
            if word not in _TEAM_CN:
                candidates.add(word)
    return sorted(candidates)
