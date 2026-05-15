# STATE_CURRENT.md — 当前运行状态

> 本文件只记录短期状态，每天覆盖更新。长期原则以 MEMORY.md 为准。
> 不写入 API Key/Token/密钥。冲突时以当前代码和最新报告为准。

---

## 0. 更新时间

- 更新时间：2026-05-15 19:23
- 更新人：OpenClaw（加速验收）
- GitHub 仓库：whoerixxz/v2-football-quant
- 最新 commit：`ebad827` V4日报: SKIP反杀详情
- 当前运行环境：生产
- 当前阶段：纸盘验证
- 今日是否允许改规则：否

---

## 1. Gateway 状态

- Gateway：running（pid 9474, state active）
- Gateway event loop：degraded（event_loop_utilization, cpu=1.00）
- Health check：QQ Bot configured
- allowInsecureAuth：true（当前配置，Gateway loopback-only）
- Doctor：Legacy config keys detected，838 orphan transcripts，skills 45 missing requirements
- Gateway 绑定：127.0.0.1:18789（loopback-only，外网不可达）

---

## 2. 加速验收结果（2026-05-15 19:23）

验收结果：**CONDITIONAL PASS** — 未允许进入下一阶段

发现异常：
1. daily_runner.py HOURLY 代码残留（DEPRECATED_DEAD_CODE）
2. V4扫描-傍晚 cron TIMEOUT（需确认原因）
3. allowInsecureAuth=true（loopback-only，风险可控）
4. QQ Bot 初始化中（未完成 connected）
5. 3个内存文件含 API Key 文字提及（无明文值，仅策略文档，脱敏完成）
6. STATE_CURRENT 之前 18h 未更新（本次已更新）

---

## 3. 今日总览

### V2 今日状态

- 系统版本：v2.3.1
- 当前使用 **v2_window_checker_with_watchdog.py**（每小时 05/35 窗口检查器）
- V2 不再运行 HOURLY 全量扫描
- DAILY_POOL 每天 12:35 合法建池（daily_runner.py --run_tag DAILY_POOL）
- V2窗口检查器只读 state 文件，无 active window 时快速退出
- 只有 T-90/T-45 才允许 BET_LOCKED
- T-15m 只做 FINAL_RECORD
- V2 正式推荐只认 BET_LOCKED
- BET_LOCKED：12 场
- WATCH_EARLY：正常
- CANDIDATE：正常
- ODDS_OUT：0
- WATCH_HIGH：正常
- SKIP_LOW：正常
- LOCK_CANCELLED：0
- V33：已废弃，禁止任何推送引用
- 今日异常：无

今日判断：V2 窗口检查器正常，12 场 BET_LOCKED。

---

### V3 今日状态

- 系统状态：enabled=false
- 当前阶段：OFF（战备）
- 今日异常：无

今日判断：enabled=false 只做战备观察，不输出正式推荐。

---

### V4 今日状态

- 当前阶段：纸盘验证
- 当前系统：V4 上半场情报系统（A/B/C/SKIP）
- 今日扫描状态：19:00 手动扫描完成（17条球探报告，496 API calls，1084s）
- A 级强推荐：0 场
- B 级达标推荐：3 场
  - Ajman vs Al Nasr — 阿联酋超 22:10 | HT71 | 80% | 2.00球
  - 瓦斯尔 vs Al-Ittihad Kalba — 阿联酋超 00:45 | HT62 | 60% | 0.80球
  - 阿斯顿维拉 vs 利物浦 — 英超 03:00 | HT76 | 80% | 1.50球
- C 级观察：10 场
- HT_SKIP：6 场
- A+B 覆盖率：15.8%
- 今日是否有 A/B 主推荐：是（3场 B 级）
- V33：已废弃，禁止引用。简报末尾有禁止追加声明

今日主要跳过原因：

- HT有球率不足：3 场
- 回调适配偏弱：2 场
- 上半场场均进球不足：1 场
- 11-45分钟压力不足：1 场
- 综合评分不足：1 场

今日判断：今日有 3 场 B 级主推荐，V4 扫描正常。今日禁止改规则。

---

## 4. 昨日 V4 复盘

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

## 5. Architecture Audit 状态

- allowInsecureAuth：true（当前配置，loopback-only 风险可控）
- API Key 明文：无（3个内存文件为策略文档，无实际 key 值）
- V33 废弃引用：无
- Secret blocker：0
- Real blocker：0
- 838 孤儿 transcript 文件（doctor 建议归档）
- 45 个 skill 缺依赖

---

## 6. Cron Policy 状态

- 总任务数：16（最终版）
- 所有 required job 均存在
- daily_runner.py 含 HOURLY 调度代码残留（DEPRECATED_DEAD_CODE，未被任何 cron 调用）
- V4扫描-傍晚（16:20）最后一次执行 TIMEOUT（待确认原因）
- 无 forbidden 命令被 cron 调度
- 无旧 HOURLY 扫描复活

---

## 7. QQ Bot 状态

- 配置：enabled=true，已有 appId
- 连接状态：initializing（启动中）
- 推送方式：systemEvent 原样推送，无 AI 二次加工
- 推送通道：announce -> qqbot:fbc6f797a5c3b6fe2680a8b25f95e143

---

## 8. 今日需要人工关注的比赛

B 级 3 场主推荐：
1. Ajman vs Al Nasr — 阿联酋超 22:10 | HT71
2. 瓦斯尔 vs Al-Ittihad Kalba — 阿联酋超 00:45 | HT62
3. 阿斯顿维拉 vs 利物浦 — 英超 03:00 | HT76

C 级 10 场仅供参考。

---

## 9. 今日异常与报警

### 数据异常
- API Key：正常（无 401 重发）
- API 429：无
- scout 文件：正常（17条球探报告）
- 天气/盘口：部分缺失（FAST_MODE正常）

### 策略异常
- MODEL_TOO_STRICT 偏多：是（9/22，规则偏严但样本不足）
- V4傍晚扫描 16:20 TIMEOUT：待确认

### 工程异常
- Cron：基本正常（V4傍晚扫描 TIMEOUT 例外）
- V4赛中快照：正常
- DeepSeek API：曾 401 一次（已恢复）
- QQ Bot：初始化中未 connected
- allowInsecureAuth：true（loopback-only 可控）

---

## 10. 当前 BLOCKER / WARNING

### WARNING（不阻塞生产）
1. allowInsecureAuth=true → 等候 BOSS 确认是否改 false
2. QQ Bot 初始化未完成 → 等候自动连接
3. 838 孤儿 transcript 文件 → doctor 可归档
4. V4傍晚扫描 cron TIMEOUT → 需确认原因（P1-2）
5. daily_runner.py HOURLY 残留 → 需加硬阻断（P1-1）

### BLOCKER（无）
所有异常均为 WARNING 级别，无生产阻塞。

---

## 11. 当前禁止事项

- 不 merge main
- 不创建多 Agent
- 不继续 P1 权重校准
- 不继续仪表盘/V38/xG/世界杯模型
- 不 push 新变更
- 不修改 V2/V4 策略
- 不自由 kill/retry
- 不运行重任务
- 不引用 V33
- 不改评分权重
- 日报阶段禁止提出核心规则修改

---

## 12. 治理分支 push 状态

- 当前分支：main（验收期间冻结，不 push）
- 最新 commit：`ebad827`（V4日报: SKIP反杀详情）
- 验收期间禁止 push

---

## 13. 明日待办

1. 检查 QQ Bot 是否 connected
2. 确认 V4傍晚扫描 TIMEOUT root cause
3. 确认 allowInsecureAuth 处理方案
4. 继续 P1 级问题修复（HOURLY残留代码、TIMEOT、AttributeError）
5. 完成 P2 级问题记录
6. 如需可重新验收
