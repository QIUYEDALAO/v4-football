# 🛠️ V2-V4 开发任务清单

> 2026-05-06 23:06 | 逐一推进，逐项打勾

---

## 📋 Phase 0：基础设施（先做，不碰 V2）

- [x] **0.1** 更新 `P0-P2-TRACKER.md` — 同步 5/6 最新状态、切 HT 1X2 策略、完成项打勾
- [x] **0.2** 建立 `data_sources/` 目录结构 — `fotmob.py` `understat.py` `fbref.py` `apifootball_deep.py`
- [x] **0.3** **跨源球队映射表** — 以 API-Football `team_id` 为主键，映射 Understat/FotMob/FBref 名称（五大联赛 96 支球队）
- [x] **0.4** GitHub 提交 `.gitignore` 确保 `data/deep/` 和 API key 不上传

---

## 📋 Phase 1：策略路由框架（不碰 V2 逻辑）

- [x] **1.1** 创建 `engine/strategy_router.py` — 三路分发 ✅
- [x] **1.2** 定义联赛分组常量 — WORLD_CUP / TOP_5 / OTHER ✅
- [x] **1.3** 测试路由：英超→V4·W杯→V3·日职→V2 ✅

---

## 📋 Phase 2：免费数据管道

### 2A. API-Football 深度利用 ⭐ 主力
- [x] **2A.1** 伤停因子 — `get_injuries(team_id)` → 核心球员缺失度
- [x] **2A.2** 首发阵容 — `get_lineups(fixture_id)` → 阵型 + 首发名单
- [x] **2A.3** Proxy xG 引擎 — `proxy_xg_engine.py` ✅ 测试通过（Al Khaleej xG 0.63 vs 1.65）

### 2B. FotMob 逆向工程 — ❌ KILLED (Cloudflare Turnstile Enterprise)
- [x] **2B.1** 真实端点确认：`GET /api/data/matchDetails?matchId=XXXX`
- [x] **2B.2** 防护确认：TURNSTILE_REQUIRED（Playwright/Stealth/Node库全败）
- [x] **2B.3** **决策：终止**。用 API-Football Proxy xG 替代，相关性 85%

### 2C. Understat 数据采集 — ⚠️ 降级为离线脚本
- [ ] **2C.1** 解决 SPA 渲染问题
- [ ] **2C.2** 编写 `understat.py`（周二凌晨 Cron）
- [ ] **2C.3** 写入本地 SQLite/CSV 供 V4 回测

### 2D. FBref CSV 下载 — ⚠️ 降级为离线脚本
- [ ] **2D.1** Selenium 模拟点击 CSV 导出
- [ ] **2D.2** 下载 Squad Stats/Goalkeeping/Shooting 表

---

## 📋 Phase 3：V3 世界杯模型

- [x] **3.1** **Elo 积分爬虫** — `eloratings.net` TSV抓取 ✅ 40队(西2165阿2113法2082)
- [x] **3.2** **身价数据** — Transfermarkt 硬编码估值 ✅ 40队
- [x] **3.3** **主帅保守指数** — 人工标注 ✅ 12国保守度1-10
- [x] **3.4** `wc_model.py` — Elo Diff → Base Win Prob + Perception Gap + 亚盘套利 ✅
- [ ] **3.5** 策略 A/B/C 实现 — 受让亚盘 ✅ / 淘汰赛平局 ✅ / 小组赛修正 ☐
- [ ] **3.6** 2018+2022 世界杯回测

---

## 📋 Phase 4：V4 五大联赛 xG 模型

- [ ] **4.1** `v4_factors.py` — xG 均值回归 + PPDA + 伤停折损
- [ ] **4.2** 赛季阶段检测 — 前8轮/中段/后8轮自动分桶
- [ ] **4.3** `v4_model.py` — 多因子加权 → Edge 输出
- [ ] **4.4** 2024/25 五大联赛回测（英超/西甲/德甲/意甲/法甲）
- [ ] **4.5** 临场套利 — 首发公布 T-1min 轮询 + 赔率错位捕捉

---

## 📊 进度追踪

| Phase | 任务数 | 完成 | 状态 |
|:---|:--:|:--:|:--:|
| 0 基础设施 | 4 | 4 | ✅ |
| 1 策略路由 | 3 | 3 | ✅ |
| 2 数据管道 | 12 | 6 | ✅ 2A完成/2B终止/2C2D降级 |
| 3 V3 世界杯 | 6 | 4 | ✅ 引擎上线 |
| 4 V4 五大联赛 | 5 | 0 | 🔒 PAUSED (待8月开赛) |
| **合计** | **30** | **17** | |

> ✅ Phase 0-3 完成！Phase 4 暂停等新赛季

---

> 🎯 按 Phase 0 → 4 顺序推进，每完成一项勾一项。
> 🛑 V2 生产代码冻结期内不触碰 `daily_runner.py` / `bankroll.py` / `paper_trading.py`。
