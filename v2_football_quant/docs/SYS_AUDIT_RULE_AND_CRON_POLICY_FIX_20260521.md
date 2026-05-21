# SYS Audit Rule & Cron Policy Fix 最终报告

**日期**: 2026-05-21
**阶段**: SYS-AUDIT-RULE-AND-CRON-POLICY-FIX-20260521
**结论**: **SYS_AUDIT_RULE_AND_CRON_POLICY_FIX_PASS**

---

## 一、问题修复摘要

### 问题
1. V33 audit 将 docs/archive 历史引用和 checker 自身检测逻辑误判为 BLOCKER
2. cron one-shot `delivery.mode=announce` 导致非异常结果推 QQ
3. "仅报告却推QQ" — SYS-架构审计守卫 cron job (41a21ce1) agentTurn payload 绕过 delivery.mode

### 修复
1. V33 审计规则增强：动态日期输出、排除 node_modules 哈希误报、识别 meta-audit 上下文
2. `sys_daily_settlement_summary.py` 新增 `--mode exception_only` / `--mode silent` 参数
3. 创建 `config/notification_severity_map.json` 路由规则表
4. SYS 状态中控增加 V33 审计结果解读（historical_doc → INFO, active_v33_path → exception_alert）
5. 新建 `check_sys_audit_notification_policy.py` 验证全部规则

---

## 二、变更文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `tools/check_v33_residual_audit.py` | 修改 | 动态日期、排除 node_modules、meta-audit 分类 |
| `tools/check_sys_audit_notification_policy.py` | **新建** | 24 项检查的通知策略验证器 |
| `config/notification_severity_map.json` | **新建** | 18 个 checker 的路由规则 + 严重级别定义 |
| `engine/sys_daily_settlement_summary.py` | 修改 | --mode exception_only/silent + V33 审计解读 |
| `docs/SYS_AUDIT_RULE_AND_CRON_POLICY_FIX_ISSUE_LIST_20260521.md` | **新建** | 问题清单文档 |
| `data/runtime/status/sys_audit_rule_and_cron_policy_fix_issue_inventory_20260521.json` | **新建** | 问题清单 JSON |

---

## 三、检查器运行结果

### check_sys_audit_notification_policy (新建)
| 状态 | 数量 |
|------|------|
| PASS | 24 |
| FAIL | 0 |
| WARN_ONLY | 0 |
| **结论** | **PASS** |

### check_v33_residual_audit (修复后)
| 状态 | 数量 |
|------|------|
| active_v33_path | 0 ← must be 0 |
| allowed_guard | 28 |
| historical_doc | 83 |
| **结论** | **PASS** |

### 关键验证项
- `sys_daily_settlement_summary.py` 正确分类为 `allowed_guard`（meta-audit，非 active V33）
- `engine/data_sources/node_modules/` 文件不再出现在 historical_doc（哈希误报已排除）
- `--mode exception_only` 模式下 CHAIN_INCOMPLETE/MISSING 推 QQ，COMPLETE 只写文件

---

## 四、通知路由修复

### 修复前
```
checker → PASS/FAIL → cron --push → systemEvent → QQ push (无条件)
```

### 修复后
```
checker → PASS  → --mode exception_only → should_push=false → 只写状态文件 ✅
checker → FAIL  → --mode exception_only → should_push=true  → QQ push ⚠️
checker → PASS  → --mode silent         → should_push=false → 只写状态文件 ✅
checker → FAIL  → --mode silent         → should_push=false → 只写状态文件 ✅
checker → PASS  → --mode announce       → should_push=true  → QQ push (兼容旧行为)
```

### 严重级别映射
| 级别 | QQ 推送 | 触发条件 |
|------|---------|---------|
| **exception_alert** | ✅ 是 | scan missed, one-shot missed, cloud mismatch, D13/V33/HOURLY active, chain=MISSING |
| **status_only** | ❌ 否 | chain=COMPLETE, daily summary normal, historical_doc V33 refs, allowed_guard V33 refs |

---

## 五、禁令合规审计

| 禁令 | 状态 |
|------|------|
| 不运行 capture | ✅ |
| 不真实推送测试 | ✅ |
| 不启用任何推送开关 | ✅ |
| 不执行 D13/V33/HOURLY | ✅ |
| 不改 V2/V4 策略 | ✅ |
| 不删除历史 docs/archive | ✅ |
| 不把所有异常都静默（exception_alert 仍推 QQ） | ✅ |
| 不把 active runtime V33 降级（active_v33_path 仍为 BLOCKER） | ✅ |

---

## 六、未完成项（需 BOSS 操作）

1. **cron job 41a21ce1 agentTurn payload 修改**：需外部 CLI 修改 agentTurn 消息，移除 "使用 systemEvent 发送到主会话" 替换为 "只写状态文件，不推送"。此为 cron 配置变更，非策略/代码变更。

---

## 七、最终结论

```
SYS_AUDIT_RULE_AND_CRON_POLICY_FIX_PASS
```

**依据**：
- `check_v33_residual_audit` → PASS (active_v33_path=0, allowed_guard=28, historical_doc=83)
- `check_sys_audit_notification_policy` → PASS (24/24 checks, 0 FAIL, 0 WARN)
- `sys_daily_settlement_summary.py` → 支持 `--mode exception_only` / `--mode silent`
- `notification_severity_map.json` → 18 个 checker 路由规则完整
- 全部 8 条禁令合规
- 所有变更均为 SYS 审计/通知基础设施，未触碰 V2/V4 策略
