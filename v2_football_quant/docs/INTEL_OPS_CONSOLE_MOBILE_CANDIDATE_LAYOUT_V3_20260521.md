# Intel Ops Console Mobile Candidate Layout V3 — 最终报告

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-MOBILE-CANDIDATE-LAYOUT-V3-20260521

---

## 变更摘要

### B-card 四行移动端布局（强化版）

| 行 | CSS class | 内容 | 关键 CSS |
|----|-----------|------|----------|
| bs-r1 | `flex-wrap:nowrap` | time \| league | `gap:10px` |
| bs-r2 | `white-space:nowrap; overflow:hidden; text-overflow:ellipsis` | teams | `font-size:23px` |
| bs-r3 | `flex-wrap:nowrap; justify-content:space-between` | script \| expand | `min-height:44px` |
| bs-r4 | `border-top:1px` | time_bins | `font-size:19px` |

### A-card 保护
- `card-r1`: `flex-wrap:wrap` → `flex-wrap:nowrap`
- `card-r2`: 新增 `white-space:nowrap; overflow:hidden; text-overflow:ellipsis`
- detail-btn: `min-height:40px` → `44px`

### 眼睛按钮处理
- 移除 `position:fixed` 悬浮按钮（原遮挡底部内容）
- 移除 `body{padding-bottom:80px}`
- 移除 `small-mode` CSS 规则
- 移至顶部 h1 工具栏：inline 36px 按钮，切换 `--font-base` / `--font-team` 变量
- 新函数 `toggleEyeComfortV2()` 替代旧 `toggleEyeComfort()`

---

## 问题回答

1. **B级队名是否独占一行？** 是。bs-r2 独占一行，`white-space:nowrap` 防换行。
2. **剧本和展开是否放到队名下方？** 是。bs-r3 在 bs-r2 下方，script 左对齐，expand 右对齐。
3. **B级 time_bins 是否仍默认可见？** 是。bs-r4 默认可见，border-top 分隔，0-15m/16-30m/31-45m。
4. **A级是否不被按钮挤压？** 是。card-r1 `flex-wrap:nowrap`，detail-btn 在行末。
5. **C级是否默认折叠？** 是。c-section-body 无 open 类。
6. **右下角眼睛按钮是否处理？** 已处理。移除 fixed 悬浮，移至顶部 h1 工具栏。
7. **candidate数字是否未变？** 未变。A=1 B=3 C=5 SKIP=0。
8. **validation数字是否未变？** 未变。130 settled, 57.7%。
9. **是否运行capture？** 否。
10. **是否真实推送？** 否。

---

## Checker 验证结果

| Checker | 结论 | Total | Pass | Fail |
|----------|------|-------|------|------|
| check_intel_ops_console_mobile_candidate_layout | PASS | 23 | 23 | 0 |
| check_intel_ops_console_validation_detail_restore | PASS | 28 | 28 | 0 |
| check_intel_ops_console_candidate_folding_ux | PASS | 13 | 13 | 0 |
| check_intel_ops_console_readability_ux | PASS | 11 | 11 | 0 |
| check_intel_ops_console_post_night_state | PASS | 16 | 16 | 0 |
| intel_ops_console | WARN_ONLY | 19 | 17 | 0 |
| intel_ops_console_chinese_ux | WARN_ONLY | 13 | 12 | 0 |

**总: 123 checks | 120 PASS | 3 WARN_ONLY | 0 FAIL | 0 BLOCKER**

---

## 修改文件

| 文件 | 动作 |
|------|------|
| data/runtime/dashboard/intel_ops_console.html | 修改：CSS强化 + eye button重定位 |
| tools/check_intel_ops_console_mobile_candidate_layout.py | 新建：23项检查 |
