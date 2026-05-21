# Intel Ops Console AB Collapsible Unified Card Layout — 最终报告

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-AB-COLLAPSIBLE-UNIFIED-CARD-LAYOUT-20260521

---

## 变更摘要

### 候选区重构：三组折叠 + 统一卡片

**旧结构**：
- A: 独立 candidate-card，始终展开
- B: b-summary-row (4-row) + b-full-card 逐个折叠
- C: c-section-summary + c-section-body 整组折叠

**新结构**：
- A组: `candidate-group-summary` → `candidate-group-body open`（默认展开，可折叠）
- B组: `candidate-group-summary` → `candidate-group-body`（默认折叠）
- C组: `candidate-group-summary` → `candidate-group-body`（默认折叠）

### A/B 统一候选卡格式（5行）

| 行 | CSS class | 内容 |
|----|-----------|------|
| card-r1 | `flex-wrap:nowrap` | time \| league \| grade badge |
| card-r2 | `white-space:nowrap` | 中文主队 vs 中文客队 |
| card-r3 | inline | HTxx \| 强度xx% \| x.xx球 \| 剧本：xxxx |
| card-r4 | `border-top:1px` | 0-15m xx% \| 16-30m xx% \| 31-45m xx% |
| card-r5 | `justify-content:flex-end` | 展开详情 ▾ 按钮（min-height:44px） |

### 关键改进
1. B级剧本不再右侧独立列 — inline 在 card-r3
2. B级展开按钮不再右侧独立列 — 移至 card-r5 底部
3. B级卡片与A级完全一致 — 统一 candidate-card 结构
4. 移除了所有旧 b-summary-row / bs-r* / b-full-card 结构
5. 移除了 toggleBCard / toggleCSection JS，统一为 toggleGroup

---

## 问题回答

1. **A组是否可折叠？** 是。candidate-group-summary + candidate-group-body，默认 open，点击折叠。
2. **B组是否可折叠？** 是。candidate-group-summary + candidate-group-body，默认 collapsed。
3. **B组是否默认折叠？** 是。`id="b-group"` 无 open 类。
4. **A/B卡片是否统一？** 是。同用 candidate-card + card-r1/r2/r3/r4/r5 + detail-panel。
5. **B级剧本是否不再单独右列？** 是。inline 在 card-r3。
6. **B级展开按钮是否不再单独右列？** 是。在 card-r5 底部。
7. **B级 time_bins 是否仍默认可见？** 是。card-r4 默认可见。
8. **V2验证是否保留？** 是。
9. **V4昨日B unknown明细是否保留？** 是。
10. **candidate数字是否未变？** 是。A=1 B=3 C=5。
11. **validation数字是否未变？** 是。130 settled, 57.7%。
12. **是否运行capture？** 否。
13. **是否真实推送？** 否。

---

## Checker 验证结果

| Checker | 结论 | Total | Pass | Fail |
|----------|------|-------|------|------|
| check_intel_ops_console_ab_collapsible_unified_card_layout | PASS | 30 | 30 | 0 |
| check_intel_ops_console_mobile_candidate_layout | PASS | 23 | 23 | 0 |
| check_intel_ops_console_candidate_folding_ux | PASS | 13 | 13 | 0 |
| check_intel_ops_console_validation_detail_restore | PASS | 28 | 28 | 0 |
| check_intel_ops_console_readability_ux | PASS | 11 | 11 | 0 |
| check_intel_ops_console_post_night_state | PASS | 16 | 16 | 0 |
| check_intel_ops_console_no_notify_clean_ui | PASS | 19 | 19 | 0 |
| intel_ops_console | WARN_ONLY | 19 | 17 | 0 |
| intel_ops_console_chinese_ux | WARN_ONLY | 13 | 12 | 0 |

**总: 172 checks | 169 PASS | 3 WARN_ONLY | 0 FAIL | 0 BLOCKER**

---

## 修改文件

| 文件 | 动作 |
|------|------|
| data/runtime/dashboard/intel_ops_console.html | 重构：ZONE 2 全部替换，新 CSS，新 JS |
| tools/check_intel_ops_console_ab_collapsible_unified_card_layout.py | 新建：30项检查 |
| tools/check_intel_ops_console_mobile_candidate_layout.py | 更新：适配新候选卡结构 |
| tools/check_intel_ops_console_candidate_folding_ux.py | 更新：适配新候选卡结构 |
| tools/check_intel_ops_console_readability_ux.py | 更新：适配新候选卡结构 |
| tools/check_intel_ops_console_validation_detail_restore.py | 更新：适配新 card-r4 结构 |
| tools/check_intel_ops_console_post_night_state.py | 更新：适配新 B 组折叠结构 |
