# 🔬 低成本进阶数据管道 — 行动书

> 提出：2026-05-06 | 优先级：V2 纸盘完成后启动
> 目标：零成本获取 Opta 级别的 xG、首发、PPDA 数据

---

## 一、数据源优先级矩阵

| 方案 | 成本 | 实时性 | 数据质量 | ROI |
|:---|:--:|:--:|:--:|:--:|
| 1. FotMob 逆向 API | 免费 | ⚡ 实时 | Opta 级别 | 🔥🔥🔥 |
| 2. Understat 库 | 免费 | 赛后 | xG+PPDA | 🔥🔥 |
| 3. API-Football 深挖 | 已付费 | 实时 | 首发+伤停 | 🔥🔥 |
| 4. FBref CSV 下载 | 免费 | T+1天 | 最全 | 🔥 |
| 5. DIY 伪 xG | 免费 | 实时 | ~85% 相关 | 🔥 |

---

## 二、分阶段实施

### Phase 1: FotMob 逆向工程（1-2天工作量）

```python
# 目标：赛前 60 分钟抓取首发 + xG 历史
# 抓包发现的关键端点：
# 1. 比赛详情：https://www.fotmob.com/api/matchDetails?matchId={id}
# 2. 球队赛程：https://www.fotmob.com/api/teams?id={id}&tab=fixtures

# 返回的 JSON 关键字段：
# content.matchFacts.expectedGoals      → xG
# content.lineup.lineup                 → 首发阵容
# content.general.teamColors            → 球队信息
# content.shotmap.shots                 → 每脚射门坐标

# 实施要点：
# - User-Agent 伪装（模拟 Chrome/Mac）
# - 请求间隔 ≥ 2 秒
# - 缓存机制（同场比赛不重复请求）
# - 赛前 60 分钟 → 每 5 分钟轮询
```

**实现文件**: `engine/data_sources/fotmob.py`

### Phase 2: Understat 历史数据库（半天工作量）

```python
# pip install understat
import asyncio
from understat import Understat

async def fetch_league_xg(league_name="EPL", season="2025"):
    """抓取英超整赛季 xG 数据"""
    async with Understat() as understat:
        fixtures = await understat.get_league_results(league_name, season)
        # 每条包含: xG_home, xG_away, ppda_home, ppda_away
```

**实现文件**: `engine/data_sources/understat.py`
**运行频率**: 每周二凌晨 Cron（赛季中）

### Phase 3: API-Football 深度利用（半天工作量）

```python
# 已经付费的端点，直接调用：
# GET /fixtures/lineups?fixture={id}     → 首发阵容 + 阵型
# GET /injuries?team={id}                → 伤停名单
# GET /players?team={id}&season={year}    → 球员数据

# 构建"伪 xG"（作为 FotMob 失效时的 fallback）：
def proxy_xg(shots_on_target_in_box, shots_on_target_outside, big_chances_missed):
    return (shots_on_target_in_box * 0.11) + 
           (shots_on_target_outside * 0.03) + 
           (big_chances_missed * 0.3)
```

**实现文件**: `engine/data_sources/apifootball_deep.py`

### Phase 4: FBref 定时爬取（2-3天工作量）

```python
# 策略：不用高频爬虫，利用 CSV 导出功能
# 1. Selenium 打开 FBref 球队页面
# 2. 点击 "Share & Export" → "Get table as CSV"
# 3. 解析 CSV 入库
# 4. 请求间隔 ≥ 30 秒，周中凌晨跑

# 目标数据：
# - Squad Stats: xG, xGA, xG/90, xGA/90
# - Goalkeeping: PSxG（预期扑救后失球）
# - Shooting: SoT%（射正率）、G/Sh（进球转化率）
```

**实现文件**: `engine/data_sources/fbref.py`
**运行频率**: 每周二凌晨 Cron

---

## 三、总架构

```
                    ┌─────────────────┐
                    │  data_sources/  │
                    ├─────────────────┤
赛前 60min ───────→ │  fotmob.py      │ ← 首发阵容 + xG 实时
赛后 24h  ───────→ │  understat.py   │ ← xG/xGA/PPDA 存档
随时     ───────→ │  apifootball.py │ ← 赛程/赔率/伤停
每周二   ───────→ │  fbref.py       │ ← 完整进阶数据
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │  feature_store  │ ← SQLite/CSV
                    ├─────────────────┤
                    │ xG_diff         │
                    │ ppda_index      │
                    │ injury_impact   │
                    │ perception_gap  │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │  V4 策略路由     │
                    ├─────────────────┤
                    │ advanced_xg.py  │ ← 五大联赛
                    │ wc_model.py     │ ← 世界杯
                    │ v2_ht_draw.py   │ ← 其他联赛
                    └─────────────────┘
```

## 四、时间线

| 日期 | 任务 |
|:---|:---|
| 5/6-5/12 | V2 纸盘跑完 |
| 5/13-5/14 | Phase 1: FotMob 逆向 + 测试 |
| 5/15-5/16 | Phase 2+3: Understat + API-Football 深挖 |
| 5/17-5/20 | Phase 4: FBref 爬取 |
| 5/20+ | V4 因子计算 + 回测 |

> 💡 **核心原则**：先抓最便宜的（FotMob/Understat），再补全最全的（FBref），API-Football 做骨干。
> 🎯 **预算**：$0（仅现有 API-Football $19/月）
