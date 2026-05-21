# Intel Ops Console AB Collapsible Click Fix — 最终报告

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-AB-COLLAPSIBLE-CLICK-FIX-20260521

---

## 变更摘要

### 根因：自定义 JS onclick 在真机全部失效

上一轮（Phase D AB-COLLAPSIBLE-UNIFIED-CARD-LAYOUT）所有 9 个 checker 静态 PASS（172 checks），但 BOSS 真机测试 A/B/C 折叠全部失效：
- A 组无法折叠
- B 组无法展开
- C 组无法展开

**根因分析**：checker 只验证 DOM 静态属性（`candidate-group-body` class 存在、`open` class 存在、`onclick` 属性字符串存在），但无法验证：
1. `toggleGroup()` JS 函数是否被 CSP 阻止
2. `onclick` 属性是否被浏览器安全策略拦截
3. `<script>` 标签执行时序是否在 DOM ready 之前
4. 缓存是否使旧 JS 残留

任何一个环节失败 → UI 彻底卡死，因为自定义 JS 同时控制 `display:none/block` 切换 + hint text 更新。

### 修复方案：原生 `<details><summary>` 零 JS 依赖

全面替换为浏览器原生 `<details><summary>` 元素：
- A 组：`<details class="candidate-group group-a" open>` — 默认展开
- B 组：`<details class="candidate-group group-b">` — 默认折叠
- C 组：`<details class="candidate-group group-c">` — 默认折叠
- 卡片详情：`<div class="card-r5"><details><summary>展开详情 ▾</summary>...</details></div>`

移除所有自定义 JS：`toggleGroup`、`toggleDetail`、`toggleBCard`、`toggleCSection` 全部删除。

### CSS 适配

```css
/* 隐藏默认三角 marker */
.candidate-group>summary::-webkit-details-marker{display:none}
.candidate-group>summary::marker{display:none;content:''}

/* 展开/收起文字提示 */
.group-hint::after{content:'展开 ▸'}
.candidate-group[open]>summary .group-hint::after{content:'收起 ▴'}
```

---

## 问题回答

1. **为什么 false pass 发生？** checker 只做静态字符串匹配（`class="..."` + `onclick="..."` 存在性），无法模拟真机点击交互。CSS class 和 onclick 属性在 HTML 源码中存在即可 PASS，但 JS 运行时执行失败 checker 无法感知。

2. **A 组是否可折叠？** 是。`<details open>` + `<summary>`，原生浏览器行为，点击 summary 折叠/展开。

3. **B 组是否可折叠？** 是。`<details>` + `<summary>`（无 open 属性，默认折叠），原生浏览器行为。

4. **C 组是否可折叠？** 是。`<details>` + `<summary>`（无 open 属性，默认折叠），原生浏览器行为。

5. **是否不再依赖 onclick？** 是。0 个 `onclick="toggleGroup"` / `onclick="toggleDetail"`，全部由浏览器原生实现。

6. **A/B/C 是否使用 native details/summary？** 是。A/B/C 组 + 每张卡片详情均使用原生 `<details><summary>`。

7. **A 组默认展开？** 是。`<details ... open>`。

8. **B 组默认折叠？** 是。`<details>` 无 open。

9. **C 组默认折叠？** 是。`<details>` 无 open。

10. **candidate 数字是否未变？** 是。A=1 B=3 C=5。

11. **validation 数字是否未变？** 是。130 settled, 57.7%。

12. **是否运行 capture？** 否。

13. **是否真实推送？** 否。

---

## Checker 验证结果

| Checker | 结论 | Total | Pass | Fail |
|----------|------|-------|------|------|
| check_intel_ops_console_ab_collapsible_unified_card_layout | PASS | 34 | 34 | 0 |
| check_intel_ops_console_mobile_candidate_layout | PASS | 25 | 25 | 0 |
| check_intel_ops_console_candidate_folding_ux | PASS | 23 | 23 | 0 |
| check_intel_ops_console_readability_ux | PASS | 11 | 11 | 0 |
| check_intel_ops_console_validation_detail_restore | PASS | 28 | 28 | 0 |
| check_intel_ops_console_post_night_state | PASS | 16 | 16 | 0 |
| check_intel_ops_console_no_notify_clean_ui | PASS | 19 | 19 | 0 |

**总: 156 checks | 156 PASS | 0 FAIL | 0 BLOCKER**

---

## 新增行为检查（Checkers 更新要点）

| 检查项 | 说明 |
|--------|------|
| `<details class="candidate-group group-a">` 存在 | A 组使用原生 details |
| `<details class="candidate-group group-b">` 存在 | B 组使用原生 details |
| `<details class="candidate-group group-c">` 存在 | C 组使用原生 details |
| A 组 `open` attribute 存在 | 默认展开 |
| B 组 `open` attribute 不存在 | 默认折叠 |
| C 组 `open` attribute 不存在 | 默认折叠 |
| `toggleGroup` 不存在于 HTML | 旧 JS 已移除 |
| `toggleDetail` 不存在于 HTML | 旧 JS 已移除 |
| `onclick="toggleGroup` 不存在 | 无 onclick 依赖 |
| `::-webkit-details-marker{display:none}` 存在 | marker 隐藏 CSS |
| `::marker{display:none;content:''}` 存在 | marker 隐藏 CSS（Firefox） |
| `group-hint::after` expand/collapse text | 展开/收起 CSS 提示 |
| B 卡片详情使用 `<details>` | 不依赖 onclick button |
| 正则匹配 3 张 B 卡（含 B3 在 `</details>` 前） | regex 修复：`</details>\s*<!-- ===== C组` |

---

## 修改文件

| 文件 | 动作 |
|------|------|
| data/runtime/dashboard/intel_ops_console.html | 重构：native `<details><summary>` 替换所有 onclick toggle |
| tools/check_intel_ops_console_ab_collapsible_unified_card_layout.py | 重写：34 项检查，含原生 details/summary + JS 移除验证 |
| tools/check_intel_ops_console_mobile_candidate_layout.py | 重写：25 项检查，原生 details 验证 + regex 修复 |
| tools/check_intel_ops_console_candidate_folding_ux.py | 重写：23 项检查，原生 details 验证 + regex 修复 |
| tools/check_intel_ops_console_readability_ux.py | 更新：A 卡 regex + B 卡 regex + C 组检查适配 native details |
| tools/check_intel_ops_console_validation_detail_restore.py | 更新：B 卡 regex + C 组检查适配 native details |
| tools/check_intel_ops_console_post_night_state.py | 更新：B 组/C 组检查适配 native details |
