# Intel Ops Console Remove Per-Card Detail Link — 最终报告

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-REMOVE-PER-CARD-DETAIL-LINK-20260521

---

## 变更摘要

### 问题

BOSS 截图确认 A/B/C 分组折叠已正常，但每场卡片底部仍有"技术详情"入口。即使已弱化为小字链接，仍占用卡片空间。BOSS 明确要求不要每场卡片单独放技术详情。

### 解决方案

1. **彻底删除每场卡片内的"技术详情"入口**：从所有 A/B 候选卡中删除 `card-r5` 整行（包含 `<details><summary>技术详情 ▾</summary>...</details>`），A/B 卡仅保留 4 行主信息。

2. **技术血缘统一移至组级折叠区**：英文队名、source、hash、model tag 等信息统一放到 B 组关闭后、C 组开始前的 `<details class="lineage-details">` 折叠区，标题"展开：A/B候选技术血缘"，默认关闭。

3. **删除 card-r5 CSS 全部规则** + `card-detail-inner` CSS 规则。

### A/B 卡片最终结构（4 行）

| 行 | CSS class | 内容 |
|----|-----------|------|
| card-r1 | `flex-wrap:nowrap` | 时间 \| 联赛 \| 等级 badge |
| card-r2 | `white-space:nowrap` | 中文主队 vs 中文客队 |
| card-r3 | inline | HTxx \| 强度xx% \| x.xx球 \| 剧本：xxxx |
| card-r4 | `border-top:1px` | 0-15m xx% \| 16-30m xx% \| 31-45m xx% |

> 无第五行，无详情按钮，无详情链接，无单场 source/hash 入口。

---

## 问题回答

1. **每场卡片内技术详情是否已删除？** 是。0 个 card-r5，0 个 per-card `<details>`。
2. **是否仍有"展开详情"字样？** 否。HTML 中 0 处。
3. **是否仍有"技术详情"字样？** 否。A/B 卡片内 0 处。
4. **是否存在 card-r5？** 否。HTML 和 CSS 中完全移除。
5. **技术血缘是否统一移动到组底部折叠区？** 是。`<details class="lineage-details">`，标题"展开：A/B候选技术血缘"，默认关闭。
6. **A/B/C分组折叠是否保持？** 是。native `<details><summary>`，A 默认 open，B/C 默认 closed。
7. **B级 time_bins 是否仍可见？** 是。3/3 B 卡均有 0-15m/16-30m/31-45m。
8. **V2验证是否保留？** 是。multi-day table + BET_LOCKED + lock proof + rolling r7/r14/r30。
9. **V4 B unknown明细是否保留？** 是。3 场 B unknown（Arsenal/Burnley，浙江/山东，Ilves/Inter Turku）。
10. **candidate数字是否未变？** 是。A=1 B=3 C=5 SKIP=0。
11. **validation数字是否未变？** 是。130 settled，57.7%。
12. **todo 是否清零？** 是。0 in_progress，0 open。
13. **是否运行 capture？** 否。
14. **是否真实推送？** 否。

---

## Checker 验证结果

| Checker | 结论 | Total | Pass | Fail |
|----------|------|-------|------|------|
| check_intel_ops_console_remove_per_card_detail_link | PASS | 39 | 39 | 0 |
| check_intel_ops_console_detail_button_deemphasize | PASS | 30 | 30 | 0 |
| check_intel_ops_console_ab_collapsible_unified_card_layout | PASS | 39 | 39 | 0 |
| check_intel_ops_console_mobile_candidate_layout | PASS | 25 | 25 | 0 |
| check_intel_ops_console_candidate_folding_ux | PASS | 23 | 23 | 0 |
| check_intel_ops_console_validation_detail_restore | PASS | 28 | 28 | 0 |
| check_intel_ops_console_readability_ux | PASS | 11 | 11 | 0 |
| check_intel_ops_console_no_notify_clean_ui | PASS | 19 | 19 | 0 |

**总: 214 checks | 214 PASS | 0 FAIL | 0 BLOCKER**

---

## 修改文件

| 文件 | 动作 |
|------|------|
| data/runtime/dashboard/intel_ops_console.html | 删除 card-r5 CSS + HTML；删除 card-detail-inner CSS；新增 lineage-details CSS + HTML |
| tools/check_intel_ops_console_remove_per_card_detail_link.py | 新建：39 项检查 |
| tools/check_intel_ops_console_detail_button_deemphasize.py | 重写：30 项检查适配无 card-r5 状态 |
| tools/check_intel_ops_console_ab_collapsible_unified_card_layout.py | 更新：card-r5 检查→4-row + lineage |
| tools/check_intel_ops_console_mobile_candidate_layout.py | 更新：5-row→4-row，card-r5 移除检查 |
| tools/check_intel_ops_console_candidate_folding_ux.py | 更新：per-card details→no per-card details |
| tools/check_intel_ops_console_readability_ux.py | 更新：expand 检查→no card-r5 检查 |
| tools/check_intel_ops_console_validation_detail_restore.py | 更新：regex 边界适配 lineage |

## 结论

**INTEL_OPS_CONSOLE_REMOVE_PER_CARD_DETAIL_LINK_PASS**
