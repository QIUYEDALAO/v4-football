# STATE_CURRENT.md — 当前运行状态

> 本文件只记录短期状态，每天覆盖更新。长期原则以 MEMORY.md 为准。
> 不写入 API Key/Token/密钥。冲突时以当前代码和最新报告为准。

---

## 0. 更新时间

- 更新时间：2026-05-15 01:06
- 更新人：OpenClaw
- GitHub 仓库：whoerixxz/v2-football-quant
- 最新 commit：`ebad827` V4日报: SKIP反杀详情
- 当前运行环境：生产
- 当前阶段：纸盘验证
- 今日是否允许改规则：否

---

## 1. 今日总览

### V2 今日状态

- 系统版本：v2.3.1
- 扫描频率：每小时
- BET_LOCKED：12 场
- WATCH_EARLY：正常
- CANDIDATE：正常
- ODDS_OUT：0
- WATCH_HIGH：正常
- SKIP_LOW：正常
- LOCK_CANCELLED：0
- 今日异常：无

今日判断：V2 每小时正常锁定，12 场 BET_LOCKED。

---

### V3 今日状态

- 系统状态：enabled=false
- 当前阶段：OFF（战备）
- 今日异常：无

今日判断：enabled=false 只做战备观察，不输出正式推荐。

---

### V4 今日状态

- 当前阶段：纸盘验证
- 今日全量扫描：7 场
- A 级强推荐：0 场
- B 级达标推荐：0 场
- C 级观察：2 场
- HT_SKIP：5 场
- A+B 覆盖率：0%
- 今日是否有 A/B 主推荐：否
- 今日是否只有 C 观察：是

今日 C 观察池：

1. FC Basel 1893 vs FC ST. Gallen — 瑞士超 | 22:30 | HT54 | 70% | 中后段发力型
2. Oriente Petrolero vs Guabirá — 玻利甲 | 08:00 | HT52 | 50% | 中后段发力型

今日主要跳过原因：

- 回调适配偏弱：5 场
- 11-45分钟压力不足：4 场
- HT评分不足：全部 <50

今日判断：今日无 A/B 主推荐，仅 C 观察。今日禁止改规则。

---

## 2. 昨日 V4 复盘

- 复盘日期：2026-05-13
- 归因文件：data/v4_archive/v4_result_attribution_20260513.jsonl
- 赛中快照文件：未运行

### 原始命中率

| 级别 | 命中 | 命中率 |
|:---|:---|:---|
| A | 1/1 | 100% |
| B | 1/1 | 100% |
| C | 6/7 | 85.7% |
| SKIP反杀率 | 10/13 | 76.9% |

### 去噪后标签

| 标签 | 场次 |
|:---|:---|
| MODEL_VALID_STRONG | 2 |
| MODEL_TOO_STRICT | 9 |
| NORMAL_VARIANCE | 其余 |

昨日结论：A+B 双双100%，分级单调性PASS。SKIP反杀率76.9%偏高（MODEL_TOO_STRICT×9），规则偏严但样本不够不改规则。日报阶段禁止提出核心规则修改。

---

## 3. 今日需要人工关注的比赛

无 A/B 主推荐。C 观察 2 场仅供参考。

---

## 4. 今日异常与报警

### 数据异常

- API Key：正常
- API 429：无
- scout 文件：正常
- 天气/盘口：部分缺失（FAST_MODE正常）

### 策略异常

- V4 A/B 连续为 0：是（5/14 赛程无HT型比赛）
- MODEL_TOO_STRICT 偏多：是（9/22，规则偏严但样本不足）

### 工程异常

- Cron：正常
- V4赛中快照：backoff（凌晨无比赛正常）
- DeepSeek API：间歇超时（服务端问题，非本地）

---

## 5. 今日运行命令

### V2
```bash
# 每小时自动
python3 engine/daily_runner.py --run_tag HOURLY --quick
# 建池
python3 engine/daily_runner.py --run_tag DAILY_POOL
```

### V4
```bash
python3 engine/v4_runner.py --scan-mode fast --lookahead-hours 24 --recent-prewarm off
python3 engine/v4_openclaw_brief.py --date 20260514
```

---

## 6. 最新报告文件

- scout：data/daily_reports/scout_v4_20260514.json (7场)
- brief：data/daily_reports/v4_openclaw_brief_20260514.txt
- validation：data/daily_reports/v4_ht_recommend_validation_20260513.json (A+B 100%)
- attribution：data/v4_archive/v4_result_attribution_20260513.jsonl
- V2 predictions：data/daily_reports/predictions_20260514.json (12场锁定)

---

## 7. 今日最终结论

V2：BET_LOCKED 12 场，每小时正常锁定。
V3：战备，enabled=false。
V4：今日无 A/B 主推荐，仅 C 观察 2 场。
昨日复盘：A+B 100% 优秀，SKIP 偏严（MODEL_TOO_STRICT×9）但样本不足不调规则。
今日禁止改规则。

---

## 8. 明日待办

1. 检查 V2 12 场 BET_LOCKED 结算。
2. 检查 V4 12:35 扫描是否有新比赛入池。
3. 10:30 复盘自动跑验证+归因。
4. 如 MODEL_TOO_STRICT 连续偏高，只记录不调。
5. 日报阶段禁止提出核心规则修改。
