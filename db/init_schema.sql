-- v2_football_quant 数据库 schema
-- 引擎: SQLite (本地测试用) / PostgreSQL (生产)

-- 比赛结果表（赛后硬事实）
CREATE TABLE IF NOT EXISTS fixtures_results (
    fixture_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL,
    league_name TEXT,
    season INTEGER,
    kickoff_utc TEXT NOT NULL,
    status TEXT, -- FT / NS / LIVE

    home_team_id INTEGER,
    home_team_name TEXT,
    away_team_id INTEGER,
    away_team_name TEXT,

    ht_home_goals INTEGER,
    ht_away_goals INTEGER,
    ft_home_goals INTEGER,
    ft_away_goals INTEGER,

    et_home_goals INTEGER,
    et_away_goals INTEGER,
    penalty_home_goals INTEGER,
    penalty_away_goals INTEGER,

    created_at TEXT DEFAULT (datetime('now'))
);

-- 赔率快照表（赛前多时间点）
CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL,
    captured_at TEXT NOT NULL, -- UTC 时间戳
    bookmaker TEXT NOT NULL,   -- Pinnacle / Bet365 / 188bet
    market TEXT NOT NULL,      -- 标准化市场名: ht_over_under_0.5
    odds_type TEXT NOT NULL,   -- over / under / home / away / draw
    decimal_odds REAL NOT NULL,
    is_closing INTEGER DEFAULT 0, -- 是否为临场收盘代理(赛前30min)

    FOREIGN KEY(fixture_id) REFERENCES fixtures_results(fixture_id)
);
CREATE INDEX IF NOT EXISTS idx_odds_fixture ON odds_snapshots(fixture_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_odds_market ON odds_snapshots(fixture_id, market, is_closing);

-- API预测和特征缓存表
CREATE TABLE IF NOT EXISTS predictions_cache (
    fixture_id INTEGER PRIMARY KEY,
    raw_response TEXT,              -- 完整JSON
    advice TEXT,                    -- API的投注建议
    prob_home REAL,                 -- 主胜概率(%)
    prob_draw REAL,
    prob_away REAL,
    under_over TEXT,
    poisson_home REAL,
    poisson_away REAL,
    form_home TEXT,                 -- 近5场形式百分比
    form_away TEXT,
    att_home REAL,
    att_away REAL,
    def_home REAL,
    def_away REAL,
    captured_at TEXT DEFAULT (datetime('now'))
);

-- 回测结果表（评分引擎输出）
CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL,
    model_version TEXT,         -- v0.1_等权
    score_home REAL,            -- 多维评分
    score_away REAL,
    model_prob REAL,            -- 模型预测概率
    placed_odds REAL,           -- 投注时的赔率
    closing_odds REAL,          -- 临场收盘赔率
    clv REAL,                   -- 收盘线价值
    ev REAL,                    -- 期望价值
    recommended BOOLEAN,        -- 是否推荐
    actual_ht_goals INTEGER,    -- 实际半场进球
    actual_result TEXT,         -- hit / miss
    roi REAL,                   -- 单场ROI
    UNIQUE(fixture_id, model_version)
);
