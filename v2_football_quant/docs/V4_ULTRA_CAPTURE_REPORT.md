# V4 Ultra Capture Mode — 走地盘口采集系统 技术报告

> 版本：v1.0  
> 日期：2026-05-12  
> 状态：已部署运行

---

## 一、系统定位

走地盘口采集系统（Ultra Capture Mode）是 V4 的数据基础设施层。目标：**用 API-Football 75,000 次/天的预算，对白名单联赛所有比赛进行分层走地盘口快照，5月31日前自校准 line_decay_model 的衰减曲线。**

此前依赖外部数据源（OpticOdds $200+/月），现在可以通过高频自采集替代。

---

## 二、架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    Ultra Capture Mode                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐                                         │
│  │ v4_runner.py    │  每日扫描 → universe + scout            │
│  └────────┬────────┘                                         │
│           ↓                                                  │
│  ┌─────────────────┐                                         │
│  │ v4_live_capture │  分层调度器                             │
│  │ _scheduler.py   │  A/B/C 三层任务生成 + 预算分配          │
│  └────────┬────────┘                                         │
│           ↓                                                  │
│  ┌─────────────────┐                                         │
│  │ v4_live_odds    │  采集执行器                             │
│  │ _collector.py   │  --once 模式, Cron 驱动                 │
│  │                 │  三层落库: raw/normalized/missing       │
│  └────────┬────────┘                                         │
│           ↓                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                  │
│  │ v4_api_budget   │    │ v4_live_capture │                  │
│  │ _audit.py       │    │ _audit.py       │                  │
│  │ 预算消耗+429审计 │    │ 覆盖率+完整率审计│                  │
│  └─────────────────┘    └─────────────────┘                  │
│                                                              │
│  数据源模块:                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                  │
│  │ api_football    │    │ market          │                  │
│  │ _live_odds.py   │    │ _normalizer.py  │                  │
│  │ odds/live 分页  │    │ HT O/U 标准化   │                  │
│  └─────────────────┘    └─────────────────┘                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、三层采集模型（A/B/C）

### 3.1 分层定义

| 层级 | 来源 | 频率 | 采集窗口 | 用途 |
|:---|:---|:---:|:---|:---|
| **A_candidate** | 入池候选（best_score≥70） | **每2分钟** | 0-20分钟 | 主策略信号验证 |
| **B_shadow** | Universe全量（未入池也采） | **每2分钟** | 0-20分钟 | 选择偏差检测 |
| **C_slice** | 全量补充 | 关键分钟快照 | [0,5,8,10,12,15,20,45] | 衰减曲线校准 |

### 3.2 A 通道双源

```
A_strict:  market_focus=HT_LIVE_OVER + coverage=GOOD/FULL
A_relaxed: best_score >= 70 + coverage=BASIC/GOOD/FULL
```

当前 A=12（全部 relaxed，strict=0）。严格通道需要更高的数据覆盖和 HT_LIVE_OVER 标记。

### 3.3 预算分配策略

```
75,000 总预算
  65,000 soft_limit (到达后C暂停、B降频)
  10,000 reserve (A始终保留)

分配顺序: A优先 → 剩余给B → 剩余给C
降级策略: 到达soft_limit → C暂停、B降频50%、A保持
```

---

## 四、模块清单

### 4.1 配置层

| 文件 | 功能 |
|:---|:---|
| `config/live_capture_profile.yaml` | ultra / may_sprint 双套采集策略配置 |
| `engine/live_capture_profile.py` | profile 加载器（支持名称切换） |

### 4.2 调度层

| 文件 | 功能 |
|:---|:---|
| `engine/v4_live_capture_scheduler.py` | A/B/C 任务生成 + 预算分配 + 成本估算 |

**关键参数**：
- `--profile may_sprint`：冲刺模式（A优先、C压缩）
- `--lookback-days 7 --lookahead-days 7`：跨日加载 universe
- `--min-b 120 --min-c 80`：B/C 最低保底
- `--budget 75000 --rate-limit 350`：预算与限速

**成本估算**：
```
A_candidate: 3端点 × 20分钟 × 每10秒 ≈ 360次/场
B_shadow:   3端点 × 20分钟 × 每25秒 ≈ 144次/场
C_slice:    3端点 × 8分钟快照 ≈ 24次/场
```

### 4.3 采集执行层

| 文件 | 功能 |
|:---|:---|
| `engine/v4_live_odds_collector.py` | 采集主脚本（26,680 行） |

**核心功能**：
- 三层落库：`live_odds_raw.jsonl` → `live_odds_normalized.jsonl` → `live_market_missing.jsonl`
- API 调用日志：`api_call_log_YYYYMMDD.jsonl`
- 失败重试 + 错误落库：`live_capture_errors.jsonl`
- 连续失败（≥5）自动暂停
- 断点续跑：`v4_capture_runtime_state_YYYYMMDD.json`

**采集端点**：
```
odds/live?fixture={id}    → 盘口快照
fixtures?id={id}          → 比赛状态+比分
fixtures/events?fixture={id} → 进球事件
fixtures/statistics?fixture={id} → 赛中统计
```

### 4.4 数据源层

| 文件 | 功能 |
|:---|:---|
| `engine/data_sources/api_football_live_odds.py` | odds/live 分页拉取 |
| `engine/data_sources/market_normalizer.py` | HT O/U 市场识别 + line 标准化 |

**标准化规则**：
- 原始值 "Over 1.0" → line=1.0, side=OVER
- 原始值 "Under 0.5" → line=0.5, side=UNDER
- 去重：同 fixture_id × 同 line × 同 bookmaker
- missing 记录：期望 line（0.5/0.75/1.0/1.25/1.5）中缺失的写入 missing.jsonl

### 4.5 审计层

| 文件 | 功能 |
|:---|:---|
| `engine/v4_api_budget_audit.py` | 预算消耗 + 峰值RPM + 429错误 + A/B/C/relaxed拆分 |
| `engine/v4_live_capture_audit.py` | 覆盖率 + 完整率 + HT_O/U识别率 + A通道统计 |

---

## 五、运行流水线

### 5.1 Cron 调度矩阵

| 时间 | 作业 | 频率 |
|:---|:---|:---|
| 12:05 | V4扫描-午间 | 每天 |
| 16:05 | V4扫描-傍晚 | 每天 |
| **17:30** | **采集调度（生成任务文件）** | **每天** |
| **18-05** | **A_candidate 采集** | **每2分钟** |
| **18-05** | **B_shadow 采集** | **每2分钟** |
| **18-05** | **C_slice 采集** | **每5分钟** |
| **18-05** | **预算审计** | **每30分钟** |
| 10:30 | V4每日复盘 | 每天 |

### 5.2 手动命令

```bash
# 生成任务
python3 engine/v4_live_capture_scheduler.py --date 20260512 --profile may_sprint --budget 75000 --rate-limit 350

# 单次采集（A通道）
python3 engine/v4_live_odds_collector.py --date 20260512 --profile may_sprint --tier A_candidate --task-file data/live_monitor/v4_capture_tasks_20260512.json --once --budget-aware

# 预算审计
python3 engine/v4_api_budget_audit.py --date 20260512 --hard-limit 75000

# 质量审计
python3 engine/v4_live_capture_audit.py --date 20260512
```

---

## 六、数据输出结构

### 6.1 原始快照 (live_odds_raw.jsonl)
```json
{
  "fixture_id": 123456,
  "captured_at": "2026-05-12T20:05:00",
  "minute": 8,
  "score": "0-0",
  "odds_live": { ... }
}
```

### 6.2 标准化盘口 (live_odds_normalized.jsonl)
```json
{
  "fixture_id": 123456,
  "captured_at": "2026-05-12T20:05:00",
  "minute": 8,
  "ht_ou_lines": [
    {"line": 0.5, "over": 1.35, "under": 3.10},
    {"line": 1.0, "over": 1.85, "under": 1.95},
    {"line": 1.5, "over": 3.00, "under": 1.38}
  ]
}
```

### 6.3 预算审计
```json
{
  "daily_calls_used": 660,
  "daily_calls_remaining": 74340,
  "calls_by_tier": {"A_candidate": 36, "B_shadow": 99, "C_slice": 525},
  "a_source_calls": {"relaxed": 36},
  "peak_requests_per_minute": 289,
  "http_429_count": 0
}
```

---

## 七、当前状态

| 指标 | 值 |
|:---|:---|
| 部署日期 | 2026-05-12 |
| 今日任务 | A=12, B=7, C=26 |
| A 来源 | relaxed=12, strict=0 |
| 预算使用 | 660/75,000 (<1%) |
| 快照积累 | 采集中 |
| 目标 | 18天(5月31日前)自校准 line_decay_model |

---

## 八、下一步

1. **连续跑 7 天**：universe 堆到 7 天+，B_shadow 池从 7 涨到 100+
2. **采集器稳定**：确保 Cron 在 match window 内不中断
3. **7天后**：首次 line_decay_model 自校准
4. **月底达标**：A 样本 50+, B 影子 200+, 0.75-1.25 线覆盖率 >80%
