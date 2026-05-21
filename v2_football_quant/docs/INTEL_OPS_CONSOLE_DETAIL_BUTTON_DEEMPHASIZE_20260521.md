# Intel Ops Console Detail Button De-emphasize — 最终报告

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-DETAIL-BUTTON-DEEMPHASIZE-20260521

---

## 变更摘要

### 问题

单场卡片中的"展开详情"按钮存在以下问题：
- 使用 `border:1px solid` + `border-radius:5px` + `padding:4px 12px`，外观类似操作按钮
- 视觉权重过高，干扰核心情报阅读
- 技术详情（英文队名/source/hash/model tag）属于低频审计信息，不应抢主卡片空间

### 解决方案

将 card-r5 中的 `<details><summary>` 从按钮样式弱化为底部小字文本链接：

**CSS 变更**：
```css
/* 旧：按钮样式 */
.card-r5 details>summary{border:1px solid var(--border-subtle); border-radius:5px; padding:4px 12px; color:var(--text-dim)}

/* 新：小字链接 */
.card-r5 details>summary{padding:2px 0; color:#6b7d8e; opacity:0.75}
.card-r5 details>summary:active{opacity:1; color:var(--blue)}
.card-r5 details[open]>summary{color:var(--blue); opacity:0.85}
```

**文本变更**：`展开详情 ▾` → `技术详情 ▾`

**保持不变**：
- `min-height:44px` 触控目标
- `font-size:var(--font-tiny)` = 15px
- 原生 `<details><summary>` 零 JS 依赖
- 详情内容：英文队名、source、hash、model tag（无 push/QQ 字段）
- card-r5 仍在卡片底部，不占右侧列

---

## 问题回答

1. **大号展开详情按钮是否已删除？** 是。移除 `border`、`border-radius`、大 padding，不再呈按钮外观。
2. **是否仍保留轻量技术详情入口？** 是。`<details><summary>技术详情 ▾</summary>`，原生折叠，零 JS。
3. **详情是否不再占右侧列？** 是。card-r5 始终在卡片底部行，从不占右侧列。
4. **详情是否不再挤压球队名？** 是。球队名在 card-r2，详情在 card-r5，各行独立。
5. **A/B/C组折叠是否保持？** 是。native `<details class="candidate-group">` + `<summary>`，A 默认 open，B/C 默认 closed。
6. **B级 time_bins 是否仍可见？** 是。card-r4 保持可见：0-15m / 16-30m / 31-45m。
7. **V2验证是否保留？** 是。V2 multi-day table + BET_LOCKED caliber + lock proof + rolling r7/r14/r30。
8. **V4 B unknown明细是否保留？** 是。3 场 B unknown（Arsenal/Burnley，浙江/山东，Ilves/Inter Turku）。
9. **candidate数字是否未变？** 是。A=1 B=3 C=5 SKIP=0。
10. **validation数字是否未变？** 是。130 settled，57.7%。
11. **是否运行capture？** 否。
12. **是否真实推送？** 否。

---

## Checker 验证结果

| Checker | 结论 | Total | Pass | Fail |
|----------|------|-------|------|------|
| check_intel_ops_console_detail_button_deemphasize | PASS | 28 | 28 | 0 |
| check_intel_ops_console_ab_collapsible_unified_card_layout | PASS | 37 | 37 | 0 |
| check_intel_ops_console_mobile_candidate_layout | PASS | 25 | 25 | 0 |
| check_intel_ops_console_candidate_folding_ux | PASS | 23 | 23 | 0 |
| check_intel_ops_console_readability_ux | PASS | 11 | 11 | 0 |
| check_intel_ops_console_validation_detail_restore | PASS | 28 | 28 | 0 |
| check_intel_ops_console_no_notify_clean_ui | PASS | 19 | 19 | 0 |
| check_intel_ops_console_post_night_state | PASS | 16 | 16 | 0 |

**总: 187 checks | 187 PASS | 0 FAIL | 0 BLOCKER**

---

## A/B 卡片最终结构

| 行 | CSS class | 内容 |
|----|-----------|------|
| card-r1 | `flex-wrap:nowrap` | 时间 \| 联赛 \| 等级 badge |
| card-r2 | `white-space:nowrap` | 中文主队 vs 中文客队 |
| card-r3 | inline | HTxx \| 强度xx% \| x.xx球 \| 剧本：xxxx |
| card-r4 | `border-top:1px` | 0-15m xx% \| 16-30m xx% \| 31-45m xx% |
| card-r5 | 弱化小字链接 | 技术详情 ▾（原生 details，无边框，灰蓝色，opacity:0.75） |

B级确认不存在：右侧剧本列、右侧详情列、大号详情按钮、单独占空间的按钮块。

---

## 修改文件

| 文件 | 动作 |
|------|------|
| data/runtime/dashboard/intel_ops_console.html | CSS：card-r5 按钮→小字链接；HTML：summary 文本 "展开详情 ▾"→"技术详情 ▾" |
| tools/check_intel_ops_console_detail_button_deemphasize.py | 新建：28 项检查 |
| tools/check_intel_ops_console_ab_collapsible_unified_card_layout.py | 更新：新增 3 项 de-emphasize 检查 |

## 结论

**INTEL_OPS_CONSOLE_DETAIL_BUTTON_DEEMPHASIZE_PASS**
