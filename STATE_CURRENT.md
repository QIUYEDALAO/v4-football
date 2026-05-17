# STATE_CURRENT.md — 当前运行状态

> 本文件只记录短期状态，每天覆盖更新。长期原则以 MEMORY.md 为准。
> 不写入 API Key/Token/密钥。冲突时以当前代码和最新报告为准。

---

## 📋 2026-05-17 日终状态

### V2
- DAILY_POOL: 手动补跑成功 ✅ pool=155, BET_LOCKED=2(过期未推), WATCH_EARLY=135, CANDIDATE=1
- 窗口检查器: 正常运行 ✅
- 结算(05-16): NO_SETTLEMENT_NEEDED

### V4扫描
- 凌晨(01:20): CHAIN_INCOMPLETE ❌ 独立日志缺失，产物被早场覆盖
- 早场(07:20): PIPELINE_READY ⚠️ 旧QQ模板历史（已被覆盖）
- 午间(14:05): PIPELINE_READY ⚠️ 旧QQ模板历史
- 傍晚(16:20): CODE_READY ⚠️ 旧QQ模板
- 晚间(22:20): CODE_READY（未到时间）
- **QQ模板已永久修复** ✅ v4_qq_formatter.py v2.0 — A/B全量/开赛时间/分布/分隔线/C/SKIP摘要
- **Push marker已自动写入** ✅ 每个窗口独立marker
- **窗口独立日志已配置** ✅ late/morning/noon/evening/night
- **当前非PRODUCTION_VERIFIED** — 明日首次cron触发后方可验证

### V4复盘(20260516)
- 手动链路已验证通过 ✅ structured 49场 / full 18KB / qq 1.3KB / guard PASS / ReportAgent PASS
- **非cron生产验证** — renderer/guard/marker已纳入v4_review_with_watchdog.py
- 待明日12:35自然触发验证

### V4盘中快照
- cron ID 8e7abfa6, 每3分钟
- 今日文件 ✅ 39KB
- max-fixtures已部署
- dangerous_attacks=UNSUPPORTED_BY_API, 仅记录不参与评级

### 临时cron
- acaa39be (14:45): TEMP_VALIDATION_CRON
- 本轮未删除，建议明日12:35复盘自然PASS后处理

### Cron修复
- V2建池: model=null ✅ (运行层待明日13:15验证)
- V2结算补跑: 15:35→15:37 ✅

### 异常
- P1_SCHEDULER_STATE_INCONSISTENCY
- P1_DAILY_POOL_AGENTTURN_MODEL_NULL_NEEDS_RUNTIME_VERIFY
- P2_SYS_CHAIN_GUARD_GAP
- ✅ 今日无BLOCKER

---

## 0. 更新时间

- 更新时间：2026-05-17 17:26
- 更新人：ClawOps
- GitHub 仓库：whoerixxz/v2-football-quant
- 最新 commit：`13446c7` → V4: 修复每日复盘生产链路与QQ分层
- 当前运行环境：生产
- 当前阶段：纸盘验证，生产观察期
- **V2 DAILY_POOL cron 稳定性已修复（配置层）**
  - cron ID: 73ef5647
  - model=null（已移除不必要LLM依赖）
  - kind=agentTurn / sessionTarget=isolated（OpenClaw不支持纯command job）
  - delivery.mode=none
  - 日志路径：data/runtime/logs/v2_daily_pool_YYYYMMDD.log（含START/END/ERROR/exit_code）
  - 明天13:15后需核验运行层（P1_DAILY_POOL_AGENTTURN_MODEL_NULL_NEEDS_RUNTIME_VERIFY）
- **V2结算补跑时间错开**：15:35 → 15:37
- **今日V2 DAILY_POOL手动补跑成功**（13:15真实cron因LLM模型超时导致STALLED_RUNNING）
  - pool_count=155扫描
  - BET_LOCKED=2 | WATCH_EARLY=135 | CANDIDATE=1
  - BET_LOCKED=2未推QQ，根因：DAILY_POOL手动补跑时间过晚(14:11)，
    窗口检查器再次运行时比赛已开赛(SKIPPED_STARTED_OR_CLOSED)，非窗口检查器自身问题
- **V4午间扫描已完成**：78场，A7/B16/C34/SKIP21
- **V4扫描QQ模板已固化**：A/B完整展开+联赛/开赛/评分/分布/C/SKIP只汇总
- **20260516 V4复盘链路已修复**：full/qq分层、guard、QQ显示层
- **20260517 V4复盘QQ显示层已推送 corrected_v2**
- **V4复盘 cron 链路已补全**：renderer→guard→route→sent 已进入 watchdog 脚本
  - 等明日12:35自然cron触发验证
- **Scheduler 文件态异常**（P1_SCHEDULER_STATE_INCONSISTENCY）
  - 内存 timerArmed=true，但 jobs.json 中20/20的 nextRunAt=None
  - 不重启Gateway，不重建scheduler
  - cron固定表达式任务重启后由wall clock恢复，风险可控

## P2_SYS_CHAIN_GUARD_GAP（持续开放）
SYS守卫需覆盖（待BOSS确认后实现）：
- V2建池 pool文件 existence check
- V2 task_status RUNNING卡住检测
- V2 API_NO_KEY
- V4 scan scout/brief/QQ brief存在性
- V4 A/B>0推送状态
- V4 scan push marker
- 旧口径污染

**当前不实现，仅记录。**

## P1_DAILY_POOL_AGENTTURN_MODEL_NULL_NEEDS_RUNTIME_VERIFY
- DAILY_POOL cron 已移除LLM model依赖(model=null)
- OpenClaw cron 不支持纯command job，只能保留agentTurn/isolated
- agentTurn+model=null 运行时是否仍初始化默认LLM，需明日13:15后核验
- 若仍出现STALLED_RUNNING或LLM初始化，需改为systemEvent+外部调度

## P1_SCHEDULER_STATE_INCONSISTENCY（持续）
- jobs.json 中20/20 nextRunAt=None（序列化异常）
- 此前报告22/22，现为20/20。原因是历史清理删除了2个废弃job（旧V2每日结算等），非新增问题
- DAILY_POOL (73ef5647) 仍在jobs.json中 ✅
- DAILY_POOL 仍在内存cron列表中，下次触发显示为in 20h ✅
- 内存timerArmed=true，当前不影响触发
- Gateway重启后存在文件态恢复风险，但固定cron表达式可基于wall clock重算
- 不重启Gateway，不重建scheduler，不删除jobs

## 明日(2026-05-18) 13:15 验收清单
DAILY_POOL cron自动触发后检查：
1. cron 73ef5647 是否自动触发
2. 日志 data/runtime/logs/v2_daily_pool_20260518.log 是否存在
3. 日志含：V2 DAILY_POOL START / exit_code= / V2 DAILY_POOL END 或 ERROR
4. exit_code=0
5. selected_fixtures_20260518.json 生成
6. cron状态不再出现STALLED_RUNNING
7. 无LLM/model初始化痕迹
8. V2窗口检查器05/35正常
9. 未发生QQ推送
10. 策略未改

---

## 1. OpenClaw 系统状态

- **Gateway**：running (pid 9474, state active, loopback 127.0.0.1:18789)
- **Connectivity probe**：ok
- **DeepSeek auth**：restored（曾 401 一次，已恢复）
- **QQ Bot**：initializing（通道启动中，实际投递待确认）
- **BOOT循环**：已修复，boot-md disabled
- **Health event loop**：degraded（event_loop_utilization，CPU 0.99，无运行影响）
- **Architecture Audit**：PASS_WITH_REFERENCES（0 real BLOCKER，0 SECRET BLOCKER）
- **Cron Policy**：PASS（20 required，0 forbidden）— 20项确认 + 核心链路强校验（12:10/12:35/13:00/13:15/14:05）
- **Cron 清理**：删除旧 V2每日结算 `258c4286`，保留新任务 `2c0a07f2`（带 failureAlert）
- **V4昨日验证来源**：修复为只读 v4_review_guard + v4_review_qq，不再读 validation/attribution

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
- **排版固定流程**：所有日报/周报/月报/QQ简报排版必须先走 ReportAgent → ClawOps 校验 → systemEvent 推送
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

## 6. 天气数据状态

- 2026-05-14 复盘：7/7 场天气数据 DATA_UNAVAILABLE，不参与归因
- v4_weather/ 目录尚未创建
- V4扫描阶段未保存比赛时天气快照
- 后续接入方案：V4扫描对进入正式 brief 的样本保存 weather snapshot 至 data/v4_weather/（天气 API 不可用时写 WEATHER_DATA_UNAVAILABLE，不阻塞扫描，不改 A/B/C/SKIP）

## 7. 当前 WARNING（不阻塞生产）

1. allowInsecureAuth=true（loopback-only，风险可控，暂不动）
2. QQ Bot initializing（通道启动中）
3. 838 orphan transcripts（doctor 可归档）
4. V4傍晚 TIMEOUT（已修复，等待自然验证）
5. APIFOOTBALL_KEY shell/env 映射待统一（仅记录，暂不改）
6. 昨日复盘 MODEL_TOO_STRICT ×9（规则偏严，样本不足不改规则）
7. 天气数据 7/7 DATA_UNAVAILABLE（后续接入采集，不阻塞复盘）

---

## 7. Cron 20项最终确认（2026-05-16 20:14 BOSS确认）

| # | 时间 | 任务 | 类型 | 状态 |
|:-:|:----|:----|:----|:----:|
| 1 | 每3分钟 18:00-11:59 | V4赛中快照 | agentTurn | ✅ ok |
| 2 | 每小时 05/35 | V2窗口检查器 | agentTurn | ✅ ok |
| 3 | 01:20 | V4扫描-凌晨 | agentTurn | ⚠️ 上次被重启打断 |
| 4 | 07:20 | V4扫描-早场 | agentTurn | ✅ ok |
| 5 | 07:35 | V2早场兜底 | agentTurn | ✅ ok |
| 6 | 08:40/17:40/23:40 | SYS-架构审计守卫 | agentTurn | ✅ ok |
| 7 | 周一 11:20 | V4周报 | agentTurn | — |
| 8 | 12:10 | V2每日结算 | agentTurn | ✅（新，failureAlert） |
| 9 | 12:35 | V4每日复盘 | agentTurn | ✅ ok |
| 10 | 13:00 | SYS每日汇总 | agentTurn | ⚠️ Message failed |
| 11 | 13:15 | V2建池-每日 | agentTurn | ✅ ok |
| 12 | 14:05 | V4扫描-午间 | agentTurn | ✅ ok |
| 13 | 14:45 | V4午间最后验收 | systemEvent | ✅ ok |
| 14 | 15:35 | V2每日结算-补跑 | agentTurn | ✅ ok |
| 15 | 16:20 | V4扫描-傍晚 | agentTurn | ✅ ok |
| 16 | 17:25 | 每日状态更新 | systemEvent | ✅ ok |
| 17 | 18:35 | V2晚场兜底 | agentTurn | ✅ ok |
| 18 | 22:20 | V4扫描-晚间 | agentTurn | ✅ ok |
| 19 | 23:35 | V2夜间兜底 | agentTurn | ✅ ok |
| 20 | 每月1日 13:20 | V4月报 | agentTurn | — |

### 已知异常

1. **V4扫描-凌晨（01:20）** — 上次被 Gateway 重启打断（error），待下次自然触发验证，不补跑
2. **SYS每日汇总（13:00）** — 上次 Message failed（agentTurn路径），已换 openclaw message send，待下次自然触发验证

### V4链路定义

- **V4比赛推送**：来自V4扫描任务的当日简报，template_id=v4_scan_brief_qq_v1，不是复盘
- **V4结算**：**不是独立cron**，是V4每日复盘（12:35）内部阶段，只按official manifest统计，不决定样本范围
- **V4复盘**：赛后归因+剧本验证，template_id=v4_daily_review_qq_v1，可引用V4结算结果

### 明天生产流程

1. cron 自然运行
2. renderer 输出模板文本
3. guard PASS
4. ReportAgent PASS
5. `openclaw message send --channel qqbot --account report --target D1BC6F68CBBAC6A473947C53ECB861EC`
6. delivery log
7. marker=DELIVERED_UNCONFIRMED
8. BOSS确认后 marker=SENT

## 8. QQ Bot 规则（2026-05-16 收口版）

### 报告 QQBOT
- account=report，appid=1904021677
- target_id=D1BC6F68CBBAC6A473947C53ECB861EC

### 中控 QQBOT
- account=control，target_id=FBC6F797A5C3B6FE2680A8B25F95E143

### Safe Outbound

唯一正式推送路径：

```bash
openclaw message send --channel qqbot --account report --target D1BC6F68CBBAC6A473947C53ECB861EC --message "$(cat <template_file>)"
```

禁止推送路径：
- announce ❌
- agentTurn ❌
- model-call ❌
- wake ❌
- main session ❌
- stdout ❌
- Python relay ❌
- Gateway patch ❌

推送前置条件：
1. template registry命中
2. renderer输出
3. guard PASS
4. ReportAgent PASS
5. route marker allowed_to_push=true

### ClawOps 是唯一正式推送入口
- AlertAgent 只生成异常报告内容，不直接推送 QQ
- ReportAgent 只生成格式化报告内容，不直接推送 QQ
- 所有推送由 ClawOps 统一发送
- 不新增 QQ Bot，不新增 QQ App，不复制 appSecret/token

## 9. 推送纪律违纪记录

### P1_PUSH_BEFORE_BOSS_CONFIRM（2026-05-16）

问题：在 BOSS 确认完整版 V4复盘前，ClawOps 已通过 `--deliver --channel qqbot` 推送精简版。
来源：2026-05-16 02:29 BOSS 指令
处理：
- 后续 V4复盘必须 guard PASS + BOSS确认 + sent_marker 后才允许推送
- 不允许先推精简版再等确认
- 不允许绕过 BOSS确认

### P1_REPORTAGENT_BYPASS（2026-05-16）

问题：ClawOps 在生成/校验/推送 V4 QQ简报时绕过 ReportAgent，未执行格式审查。
来源：2026-05-16 03:12 BOSS 指令
处理：
- 后续所有 V4 QQ简报/日报/周报/月报排版必须经过 ReportAgent 格式审查
- ReportAgent 不改数据/结论/A/B/C/SKIP，只做 QQ/iPhone 阅读体验和格式合规
- ClawOps 只有 ReportAgent PASS + guard PASS 后才允许 systemEvent 推送
- 已推送到 QQ 的历史内容不重复处理

## 10. 任务汇报纪律

标记：TASK_REPORTING_VIOLATION（P1）
来源：2026-05-16 00:24 BOSS 指令
问题：ClawOps 完成 git push 后未主动汇报，直到 BOSS 追问才补报

纪律（已写入 AGENTS.md / MEMORY.md）：
- 任何任务完成后必须主动汇报
- 不允许沉默等待 BOSS 追问
- 3分钟以上运行中任务必须汇报进度
- git push/cron修改/配置修改/推送/systemEvent后必须立即出最终报告
- delivery.mode=none 不禁止正式回报

## 11. 已知异常（2项，不阻塞生产）

1. **V4扫描-凌晨（01:20）** — 上次被 Gateway 重启打断，待下次自然触发验证，不补跑
2. **SYS每日汇总（13:00）** — 上次 Message failed（agentTurn路径），已换 openclaw message send 直推，待下次自然触发验证

## 12. Guard 新增规则（本次收口新增）

- fixed_sections=10/10
- script_summary=2符合1偏早（瓦斯尔偏早）
- raw enum=0（MODELHIT/OFFICIALMANIFEST/v4officialsamples）
- compressed enum=0（QQDELIVERYTEST/APIKEYMISSING 等）
- command leak=0（EOF/cd/python3/2>&1）
- full report leak=0（天气/场地/累计归因详细表/赛前信号不泄漏到QQ版）
- C/SKIP=0条件固化
- V4污染样本=0（Pachuca/A6/B8/20260516）
- Alert code字段泄漏=0

---

## 13. 生产观察期禁止事项

- 不修改 V2/V4 策略
- 不修改 A/B/C/SKIP 规则
- 不修改 BET_LOCKED 规则
- 不恢复 announce
- 不改 delivery.mode
- 不改 cron 时间
- 不改 timeout
- 不自动重跑失败任务
- 不新增 cron（无BOSS明确指令）
- 不使用 announce/agentTurn/wake/main session 推送
- 不创建新 Agent
- 不禁用 healthcheck/weather
- 不推 full report 到 QQ
- 不绕过 ReportAgent / guard
- 不自动修复
