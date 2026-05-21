# Intel Ops Console Post-Night State & Folding V2 最终报告

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-POST-NIGHT-STATE-AND-FOLDING-V2-20260521
**结论**: **INTEL_OPS_CONSOLE_POST_NIGHT_STATE_FOLDING_V2_PASS**

---

## 一、问题修复摘要

### 问题
Night one-shot 已在 22:22-22:33 执行完毕，但仪表台仍显示 stale 状态：
- "当前窗口=晚间"（应为 night 已完成）
- "下一窗口=夜间 22:20"（窗口已过）
- B 级候选整块铺开（4 场全部展开）
- V2 锁仓和 V2 验证模块不明显
- 时间线占据主视觉

### 修复
1. 顶部状态卡改为赛后状态：今日扫描已完成 / A1 B3 C5 / 等待赛果 / 阻断0
2. 移除所有 "当前窗口=晚间" 和 "下一窗口=夜间22:20" 文字
3. B 级改为摘要模式（3 条 summary row，点击展开完整卡）
4. C 级默认折叠，5 场
5. V2 模块恢复：V2 生产状态卡 + V2 锁仓证明（折叠）+ V2 滚动验证（折叠）
6. 时间线移至底部折叠区 "扫描窗口记录"
7. 副标题改为 "夜间扫描已完成 · 等待赛果复盘"

---

## 二、12 项核心问题回答

### 1. 是否修复 stale current？
**是。** 页面不再显示 "当前窗口=晚间"。顶部状态卡显示 "今日扫描：已完成"。

### 2. 是否显示 night 已完成？
**是。** 副标题 "夜间扫描已完成 · 等待赛果复盘"，Zone 1 显示 "夜间窗口扫描已完成"。

### 3. 是否移除下一窗口 night 22:20 的错误展示？
**是。** 页面不再出现 "下一窗口=夜间22:20"。Zone 1 改为 "下一动作：等待赛果 → 复盘验证"。

### 4. B级是否可折叠？
**是。** B 级改为摘要模式：3 条 b-summary-row（时间｜联赛｜中文队名｜剧本），点击展开完整卡（HT/强度/预计球/time_bins/source）。完整卡默认全部折叠。

### 5. A/B time_bins 是否仍保留？
**是。** A 卡 time_bins 在默认视图中可见。B 卡 time_bins 在展开后的完整卡中可见。0-15m 在页面中出现 9 次。

### 6. C是否默认折叠？
**是。** C 区使用 c-section-summary，默认折叠。"仅观察，不是推荐" 标签可见。C=5 场。

### 7. V2锁仓是否恢复？
**是。** V2 生产状态卡显示 PRODUCTION_VERIFIED，BET_LOCKED=1。V2 锁仓证明（Ried vs Wolfsberger AC，T-90，Odds 2.28）在折叠详情中。

### 8. V2验证是否恢复？
**是。** V2 滚动验证模块存在，统计口径仅 BET_LOCKED（排除 WATCH/CANDIDATE），当前 N/A（样本不足）。

### 9. candidate数字是否未变？
**是。** A=1 B=3 C=5 SKIP=0，与 night freeze JSON 一致。未手动修改任何候选数据。

### 10. validation数字是否未变？
**是。** 130 已结算，57.7% 命中率，与 AB133 生产推荐口径一致。

### 11. 是否运行 capture？
**否。** 全程未运行任何 capture / scan / push。

### 12. 是否真实推送？
**否。** 全程未触发任何 QQ / push / 发送。

---

## 三、9 个检查器运行结果

| 检查器 | 总数 | 通过 | 失败 | 警告 | 结论 |
|--------|------|------|------|------|------|
| post_night_state | 16 | 16 | 0 | 0 | PASS |
| candidate_folding_ux | 13 | 13 | 0 | 0 | PASS |
| readability_ux | 11 | 11 | 0 | 0 | PASS |
| no_notify_clean_ui | 19 | 19 | 0 | 0 | PASS |
| ab133_forensic_recount | 10 | 10 | 0 | 0 | PASS |
| goal_distribution_source_trace | 10 | 10 | 0 | 0 | PASS |
| script_goal_distribution | 15 | 15 | 0 | 0 | PASS |
| chinese_ux | 13 | 13 | 0 | 0 | PASS |
| console | 19 | 17 | 0 | 2 | WARN_ONLY |
| **合计** | **126** | **124** | **0** | **2** | **PASS** |

### 2 个 WARN_ONLY 说明

1. **review_after_night pipeline 不可见** — 已知检查器-设计差异。
2. **C section h2 元素未找到** — C 区使用 c-section-summary，非传统 h2，已知差异。

---

## 四、禁令合规审计

| 禁令 | 状态 |
|------|------|
| 不运行 night capture | ✅ |
| 不真实推送 | ✅ |
| 不启用推送开关 | ✅ |
| 不执行 D13/V33/HOURLY | ✅ |
| 不改策略 | ✅ |
| 不改 candidate 数字 | ✅（数据来自 night freeze JSON） |
| 不改 validation 数字 | ✅（130, 57.7%） |
| 不伪造 time_bins | ✅ |
| 不把 C/SKIP 写成推荐 | ✅（"仅观察，不是推荐"） |

---

## 五、最终结论

```
INTEL_OPS_CONSOLE_POST_NIGHT_STATE_FOLDING_V2_PASS
```

**依据**：9 个检查器全部通过（126 项检查，124 PASS + 2 已知 WARN_ONLY，0 FAIL，0 BLOCKED），12 项问题全部正面回答，9 条禁令全部合规。
