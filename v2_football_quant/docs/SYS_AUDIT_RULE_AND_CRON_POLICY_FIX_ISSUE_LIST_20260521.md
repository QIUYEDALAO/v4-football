# SYS Audit Rule & Cron Policy Fix — 问题清单

**日期**: 2026-05-21
**阶段**: SYS-AUDIT-RULE-AND-CRON-POLICY-FIX-20260521

---

## 问题总览

| # | 问题 | 严重级别 | 影响 | 根因 |
|---|------|---------|------|------|
| 1 | V33 audit 历史 docs 引用被误判为 BLOCKER | HIGH | audit checker 误报阻断，影响日常运维判断 | `check_v33_residual_audit.py` 的 `historical_doc` 分类被上游解读为 BLOCKER，且输出路径硬编码日期 |
| 2 | cron one-shot `delivery.mode=announce` 导致不必要的 QQ 推送 | CRITICAL | 每天 3 次非异常 QQ 推送噪音 | `sys_daily_settlement_summary.py --push` 无 severity 判断，任何链状态都推 |
| 3 | "仅报告却推QQ" 路由错误 | CRITICAL | 正常审计结果被当作异常推送到 QQ | SYS-架构审计守卫 cron job (41a21ce1) 的 agentTurn payload 内嵌了 systemEvent 推送指令 |

---

## 问题 1: V33 audit 误判

### 现状
- `tools/check_v33_residual_audit.py` 正确分类为 `allowed_guard` / `historical_doc` / `active_v33_path`
- BLOCKER 仅在 `active_v33_path_count > 0` 时触发
- 当前运行结果: PASS (0 active, 25 allowed_guard, 78 historical_doc)

### 需修复
1. 输出文件名硬编码为 `v33_residual_audit_20260520.json`，需改为动态日期
2. 确保 `historical_doc` 条目在任何上游 checker/SYS dashboard 中不会被解释为 BLOCKER/WARN
3. 在 SYS 状态中控中，`historical_doc_count` 应显示为 INFO 级别，非 WARN

### 涉及文件
- `tools/check_v33_residual_audit.py`（动态日期 + 增强注释）
- `engine/sys_daily_settlement_summary.py`（V33 audit 结果解读逻辑）

---

## 问题 2: cron delivery.mode=announce

### 现状
- `engine/sys_daily_settlement_summary.py` 的 `--push` 模式无条件推送
- 无 severity 过滤：COMPLETE/CHAIN_INCOMPLETE/MISSING 都推 QQ
- `push_via_system_event()` 写状态文件后触发 systemEvent

### 需修复
1. 新增 `--mode` 参数：`announce`（全推）/ `exception_only`（仅异常推）
2. `exception_only` 模式下：COMPLETE → 只写状态文件不推 QQ；CHAIN_INCOMPLETE/MISSING → 推 QQ 警告
3. cron job 41a21ce1 的 agentTurn payload 移除 "使用 systemEvent 发送" 指令
4. 所有 one-shot cron 统一 delivery_mode 为 `exception_only`

### 涉及文件
- `engine/sys_daily_settlement_summary.py`（push 逻辑 + --mode 参数）
- `engine/v2_daily_pool_summary.py`（第121行引用 delivery_mode，确认一致）

---

## 问题 3: 通知路由 "仅报告却推QQ"

### 现状
- SYS-架构审计守卫 cron job (ID: 41a21ce1) 每天 08:40/17:40/23:40 执行
- agentTurn payload 内嵌 "使用 systemEvent 发送到主会话" 指令
- 绕过 delivery.mode=none 限制，agent 在 isolated session 内主动调用 sessions_send
- QQ 噪音紧急静音已临时生效（mute marker: `sys_qq_noise_emergency_mute_20260521.json`）

### 需修复（BOSS 已批准 Option A）
1. 修改 agentTurn 消息：移除 "使用 systemEvent 发送到主会话"，替换为 "只写状态文件，不推送"
2. 创建通知严重级别映射表：`config/notification_severity_map.json`
3. 映射规则：
   - `exception_alert`：需 QQ 推送（scan interrupted, one-shot missed, cloud mismatch, D13/V33/HOURLY active）
   - `status_only`：只写状态文件不推 QQ（normal audit PASS/WARN, chain COMPLETE, daily summary）
4. 在 `check_sys_audit_notification_policy.py` 中验证路由正确性

### 涉及文件
- cron job 41a21ce1 agentTurn 配置（外部，需通过 CLI 修改）
- `engine/sys_daily_settlement_summary.py`
- `config/notification_severity_map.json`（新建）
- `tools/check_sys_audit_notification_policy.py`（新建）

---

## 执行计划

| Step | 动作 | 输出 |
|------|------|------|
| 1 | 建立问题清单 | 本文档 + JSON inventory |
| 2 | 修复 V33 audit 分类规则 | 动态日期 + 增强分类注释 |
| 3 | 修复 cron delivery.mode | sys_daily_settlement_summary.py --mode exception_only |
| 4 | 创建通知严重级别映射表 | config/notification_severity_map.json |
| 5 | 修复 SYS 状态中控渲染 | 解读 V33 historical_doc 为 INFO |
| 6 | 创建 sys audit notification policy checker | tools/check_sys_audit_notification_policy.py |
| 7 | 运行所有验证 checker | 全部 9+1 checker PASS |
| 8 | 生成最终报告 | docs/SYS_AUDIT_RULE_AND_CRON_POLICY_FIX_20260521.md |

---

## 禁令清单

| # | 禁令 | 状态 |
|---|------|------|
| 1 | 不运行 capture | ✅ |
| 2 | 不真实推送测试 | ✅ |
| 3 | 不启用任何推送开关 | ✅ |
| 4 | 不执行 D13/V33/HOURLY | ✅ |
| 5 | 不改 V2/V4 策略 | ✅ |
| 6 | 不删除历史 docs/archive | ✅ |
| 7 | 不把所有异常都静默 | ✅ |
| 8 | 不把 active runtime V33 降级 | ✅ |
