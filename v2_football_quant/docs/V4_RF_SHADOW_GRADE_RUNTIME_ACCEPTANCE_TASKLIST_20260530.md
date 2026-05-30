# V4_RF_SHADOW_GRADE — 运行态验收补验方案

**生成时间：** 2026-05-31 00:05 CST

## 背景

e47031e 代码已完成（CODE_READY），静态规则验证通过（STATIC_RULE_PASS），但运行态验收尚未闭环（RUNTIME_PENDING）。以下为三个补验方案，由 BOSS 选择或授权执行。

## 方案 A：等待真实白名单样本

**适用场景：** 有真实白名单日期，且有有效 H2H 数据产生 A/B 候选。

| 项目 | 条件 |
|------|------|
| 入口 | 正式入口 serial / whitelist / no-push |
| 不 kill | 等待 watchdog 正常推进，不干预 |
| 不 retry | 一次失败即停止报告 |
| 新 scout | ≥ 5 行 |
| 验证字段 | rf_shadow_grade / balance_reason / market_reason |
| 候选现场 | A/B 候选 ≥ 1 场 |
| 耗时 | 视 API 速度，约 10-40 分钟 |

**优点：** 最真实的运行态闭环。  
**缺点：** 依赖白名单有效样本 + API 速度，周中可能无合适数据。

## 方案 B：新增轻量 runtime acceptance 工具

**适用场景：** 不调 API，使用 e47031e 代码 + 已存在 scout 数据生成临时验收产物。

| 项目 | 条件 |
|------|------|
| API 调用 | ❌ 不调用 |
| 输入 | 已有 scout 数据 |
| 输出 | 临时 runtime acceptance artifact（进 docs/ 或 data/runtime/status/） |
| 覆盖 | 不覆盖正式业务产物 |
| 验证 | rf_shadow_grade / balance_reason / market_reason 字段闭环 |
| 耗时 | ＜ 10 秒 |

**实现思路：**
1. 读取已有 scout 的 factors + H2H 数据
2. 调用 `build_rf_shadow_grade_layer()` 生成 shadow 字段
3. 写入 `data/runtime/status/v4_rf_shadow_runtime_acceptance_artifact_<date>.json`
4. checker 读取该 artifact 验证字段完整性

**需要 Codex 单独实现。**  
**OpenClaw 不主动实现，但可协助设计。**

## 方案 C：新增 max-fixtures / sample-mode 参数

**适用场景：** 正式入口提供安全参数，限制扫描场次。

| 项目 | 条件 |
|------|------|
| 参数 | `--max-fixtures N` 或 `--sample-mode` |
| 入口 | 正式入口 serial / whitelist / no-push |
| 安全 | 只跑前 N 场，控制时间 |
| 不触发 | validation / QQ / live bet / cron |
| 产物 | 正常 scout（N 行），正常 candidate_view |
| 耗时 | N × ~40秒 |

**需要 Codex 单独在 v4_scan_and_brief.py 中实现 --max-fixtures 参数。**  
**OpenClaw 不主动实现。**

## 补验前提条件

| 条件 | 状态 |
|------|------|
| HEAD 为 e47031e 或更新 | ✅ 已确认 |
| DEFAULT_RULES 未改 | ✅ 已验证 |
| cron 未改 | ✅ 已验证 |
| validation 未重算 | ✅ 已验证 |
| live bet 未改 | ✅ 已验证 |
| QQ 未推 | ✅ 已验证 |

## 禁止事项

- ❌ 本阶段完成前不得进入 Phase 4/5/6
- ❌ 不得修改 official grade
- ❌ 不得修改 DEFAULT_RULES
- ❌ 不得再次长时间无限制 serial dry-run
- ❌ 不得实现 CPL
