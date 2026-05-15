# STATE_CURRENT.md — 当前运行状态

> 本文件只记录短期状态，每天覆盖更新。长期原则以 MEMORY.md 为准。
> 不写入 API Key/Token/密钥。冲突时以当前代码和最新报告为准。

---

## 0. 更新时间

- 更新时间：2026-05-15 19:32
- 更新人：OpenClaw（治理分支已合并到 main）
- GitHub 仓库：whoerixxz/v2-football-quant
- 最新 commit：`488522b` acceptance fixes + governance merge
- 当前运行环境：生产
- 当前阶段：纸盘验证
- 治理分支已合并：openclaw-architecture-governance-20260515 → main ✅
- 本周末：周六高比赛量重点观察

---

## 1. OpenClaw 系统状态

- **Gateway**：running (pid 9474, state active, loopback 127.0.0.1:18789)
- **Connectivity probe**：ok
- **DeepSeek auth**：restored（曾 401 一次，已恢复）
- **QQ Bot**：initializing（通道启动中，实际投递待确认）
- **BOOT循环**：已修复，boot-md disabled
- **Health event loop**：degraded（event_loop_utilization，CPU 0.99，无运行影响）
- **Architecture Audit**：PASS_WITH_REFERENCES（0 real BLOCKER，0 SECRET BLOCKER）
- **Cron Policy**：PASS（13 required，0 forbidden）

## 1a. 多Agent状态

### AlertAgent（🚨 告警员）
- **状态**：active
- **角色**：异常通知员
- **权限**：只读状态文件 / 输出异常摘要（systemEvent）
- **禁止**：不修复、不重跑、不kill、不分析比赛
- **测试结果**：✅ --json 模式格式化精准通过

### ReportAgent（📋 报告格式员）
- **状态**：active
- **角色**：报告格式员
- **权限**：读取正式 brief / 输出 QQ移动端排版
- **禁止**：不重算评级、不改A/B/C/SKIP、不读取 raw scout 作评级依据、不直接推送
- **测试结果**：✅ 正确保留等级分布和验证信息，格式适配QQ阅读

### ClawOps（main）
- **身份**：🦞 系统总控（默认 Agent）
- **权限**：所有操作。唯一正式调度和推送入口
- **QQ 推送**：所有 QQ systemEvent 由 ClawOps 统一发送
- **调度规则**：异常类→AlertAgent，排版类→ReportAgent，研究/代码不委派
- **约束**：AlertAgent / ReportAgent 不直接联系 BOSS，不直接接管 cron

### shell 空输出问题
- 记录为命令抓取方式问题（`openclaw agent` 非 TTY 输出路径限制）
- `--json` 模式测试已通过，payloads 文本完整
- 不作为 Agent 故障

---

## 2. V2 今日状态

- **系统**：v2.3.1
- **当前运行模式**：v2_window_checker_with_watchdog.py — 窗口驱动，非全量扫描
- **执行频率**：每小时 05/35 分运行窗口检查
- **DAILY_POOL**：每天 12:35 合法建池（daily_runner.py --run_tag DAILY_POOL）
- **V2 正式推荐只认 BET_LOCKED**（T-90m / T-45m 锁定）
- **WATCH_EARLY / CANDIDATE / FINAL_RECORD 不是投注推荐**
- **HOURLY 全量扫描**：不再运行（已添加硬阻断，exit code 77）
- **V33**：已废弃，禁止任何引用
- **BET_LOCKED**：12 场
- **WATCH_EARLY**：正常
- **CANDIDATE**：正常
- **ODDS_OUT**：0
- **WATCH_HIGH**：正常
- **SKIP_LOW**：正常
- **LOCK_CANCELLED**：0
- **今日异常**：无

---

## 3. V3 今日状态

- **系统状态**：enabled=false
- **当前阶段**：OFF（战备）
- **今日异常**：无

---

## 4. V4 今日状态

- **当前阶段**：纸盘验证
- **唯一入口**：v4_scan_and_brief.py（不单独运行 v4_runner / v4_dashboard 直推）
- **V4正式输出**：A/B/C/SKIP（不引用 V33 / 旧口径 / 交叉参考）
- **QQ 推送**：只推 v4_openclaw_brief_qq_YYYYMMDD.txt，systemEvent 原样推送，无 AI 二次加工
- **禁止推 QQ**：raw scout / dashboard / market_scores / 全场大球 / 下半场大球 / V33
- **今日扫描**：19:00 手动扫描完成（17 条球探报告，496 API calls，1084s）
- **A 级强推荐**：0 场
- **B 级达标推荐**：3 场
  - Ajman vs Al Nasr — 阿联酋超 22:10 | HT71 | 80% | 2.00球
  - 瓦斯尔 vs Al-Ittihad Kalba — 阿联酋超 00:45 | HT62 | 60% | 0.80球
  - 阿斯顿维拉 vs 利物浦 — 英超 03:00 | HT76 | 80% | 1.50球
- **C 级观察**：10 场
- **HT_SKIP**：6 场
- **A+B 覆盖率**：15.8%
- **v4_scan_worker.py AttributeError**：已修复（NoneType guard + dict type check）
- **V4扫描-傍晚 TIMEOUT**：已定位，等待下一次自然验证（下一轮 16:20 cron）

---

## 5. 昨日 V4 复盘

- **复盘日期**：2026-05-13
- **归因文件**：data/v4_archive/v4_result_attribution_20260513.jsonl

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

---

## 6. 当前 WARNING（不阻塞生产）

1. allowInsecureAuth=true（loopback-only，风险可控，暂不动）
2. QQ Bot initializing（通道启动中）
3. 838 orphan transcripts（doctor 可归档）
4. V4傍晚 TIMEOUT（已修复，等待自然验证）
5. APIFOOTBALL_KEY shell/env 映射待统一（仅记录，暂不改）
6. 昨日复盘 MODEL_TOO_STRICT ×9（规则偏严，样本不足不改规则）

---

## 7. QQ Bot 规则（多Agent共用）

- ClawOps 是唯一正式推送入口
- AlertAgent 只生成异常报告内容，不直接推送 QQ
- ReportAgent 只生成格式化报告内容，不直接推送 QQ
- 所有 QQ systemEvent 必须由 ClawOps 统一发送
- AlertAgent / ReportAgent 不得绕过 ClawOps 直接联系 BOSS
- 不新增 QQ Bot，不新增 QQ App，不复制 appSecret/token
- 周六高比赛量期间禁止调整 QQ Bot 结构
- 多Agent共用现有 QQ Bot，由 ClawOps 统一调度和推送

## 8. 当前禁止事项

- 不 push 新变更
- 不修改 V2/V4 策略
- 不修改 cron
- 不创建 Agent
- 不改 allowInsecureAuth
- 不改 env
- 不引用 V33
- 不运行 V4重扫描
- 不自由 kill/retry
- 不运行重任务
- 日报阶段禁止提出核心规则修改

---

## 8. 下一步待办（低风险推进）

1. allowInsecureAuth → 待稳定后安全硬化（设置 false + 配置 ownerAllowFrom）
2. APIFOOTBALL_KEY shell/env 映射统一
3. AlertAgent / ReportAgent 待低风险推进
4. 明日周六高比赛量重点观察
5. QQ Bot 上线后验证实际投递
