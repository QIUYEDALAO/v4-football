# V4统一作战台 UI 黄金模板对齐报告

**阶段**: V4-CONTROL-CENTER-UI-TEMPLATE-ALIGNMENT-20260526
**生成时间**: 2026-05-26T02:30:00+08:00
**状态**: V4_CONTROL_CENTER_UI_TEMPLATE_ALIGNMENT_PASS

---

## 核心问题诊断

### 为什么当前 UI 和 BOSS 设计稿不一致？

前一轮 Phase 3 UI 重构使用了自定义 CSS 变量（`--bg: #060d18`, `--surface`, `--border` 等）和自定义 class 体系（`.top-kpi`, `.kpi-violet`, `.kpi-green`, `.top-bar` 等），与 BOSS 提供的黄金模板 `v4_control_center_final_design.html` 的 class 和变量体系完全不同。

| 项目 | 旧 UI | 黄金模板 |
|------|-------|----------|
| CSS 变量 | `--bg`, `--surface`, `--border` | `--bg`, `--card`, `--line`, `--text` |
| 主色调 | `--blue: #5eaefa` | `--blue: #5cc8ff` |
| KPI 容器 | `.top-bar` + `.top-kpi` | `.kpi-grid` + `.card.kpi` |
| 主布局 | `.main-grid` | `.primary-layout` |
| 模块区 | `.panel` + `<details>` | `.module-grid` + `.card.module` |
| 导航 | 无底部导航 | `.nav` 固定底部导航 |
| 抽屉 | 无 | `.drawer` + `.panel` |

### 修复方案

以 BOSS 提供的 `v4_control_center_final_design.html` 为黄金模板，1:1 替换 UI 骨架，同时完整保留所有数据绑定 JS 逻辑。

---

## 19 项核心验收问答

| # | 问题 | 答案 |
|---|------|------|
| 1 | 当前 UI 为什么和 BOSS 设计稿不一致？ | 前一轮使用了自定义 CSS 变量和 class，未以黄金模板为基线 |
| 2 | 是否已经用黄金模板作为基线？ | 是。CSS 变量、class 名、DOM 结构与黄金模板完全一致 |
| 3 | 是否移除了 OpenClaw Control 顶栏？ | 是。已替换为黄金模板 `.topbar` sticky header |
| 4 | 是否移除了 top-kpi 旧布局？ | 是。已替换为黄金模板 `.kpi-grid` + `.card.kpi` |
| 5 | 是否保留真实数据绑定？ | 是。loadModel()、renderAll()、renderTopBar() 等全部保留 |
| 6 | 是否顶部 KPI 正常显示？ | 是。6 个 KPI 通过 id 锚点与 JS 绑定 |
| 7 | 是否今日候选正常显示？ | 是。A/B 候选渲染为 `.candidate` article，SKIP 折叠为摘要行 |
| 8 | 是否 SKIP 已折叠？ | 是。SKIP 显示为紧凑单行，不再是大卡片铺满 |
| 9 | 是否投注操作区还原？ | 是。模块网格中保留投注操作按钮，模态层完整保留 |
| 10 | 是否系统控制按绿/黄/红分层？ | 是。在系统控制模块 rows 中按颜色分层描述 |
| 11 | 是否 checker 已能拦截 UI 走样？ | 是。新增 9 项黄金模板 class 必须存在 + 6 项旧 class 禁止存在 |
| 12 | 是否改 model？ | 否 |
| 13 | 是否改策略？ | 否 |
| 14 | 是否改 candidate？ | 否 |
| 15 | 是否重算 validation？ | 否 |
| 16 | 是否改实盘原始记录？ | 否 |
| 17 | 是否推 QQ？ | 否 |
| 18 | 是否 cloud / cron？ | 否 |
| 19 | BOSS 是否可以刷新页面做视觉验收？ | 是。刷新 http://127.0.0.1:8766/v4_control_center.html |

---

## 修改文件清单

| 文件 | 变更 | 内容 |
|------|------|------|
| data/runtime/dashboard/v4_control_center.html | 重写 | CSS/HTML 以黄金模板为基线，保留全部 JS 数据绑定 |
| tools/check_v4_control_center.py | 增强 | 新增 15 项 UI 模板硬检查 |

---

## Checker UI 模板检查结果

```
has_topbar: true
has_kpi-grid: true
has_primary-layout: true
has_module-grid: true
has_chart-layout: true
has_drawer: true
has_nav_bottom: true
has_candidate: true
has_summary-grid: true
no_OpenClaw_Control: true
no_top-kpi: true
no_kpi-violet: true
no_kpi-green: true
no_kpi-amber: true
no_top-bar: true
```

---

## 禁止项确认

```
model_schema_changed=false
data_binding_regressed=false
full_scan_ran=false
capture_ran=false
validation_recomputed=false
strategy_changed=false
candidate_changed=false
candidate_rating_changed=false
result_validation_history_changed=false
script_validation_history_changed=false
live_bet_raw_records_rewritten=false
validation_cumulative_mixed_with_live_bet=false
old_cumulative_source_reused=false
v3_module_added=false
v2_restored=false
v33_active=false
QQ_recommendation_pushed=false
cloud_publish=false
cron_schedule_modified=false
secrets_printed=false
secrets_committed=false
```

---

## Git 状态

- 本地 commit: `56134f4` — "dashboard: align V4 control center with confirmed UI template"
- 2 files changed, 628 insertions(+), 668 deletions(-)
- GitHub push: REMOTE_PUSH_BLOCKED（账号暂停）
- 本地 commit 保留，不重复提交

---

## 结论

**V4_CONTROL_CENTER_UI_TEMPLATE_ALIGNMENT_PASS**

BOSS 打开 http://127.0.0.1:8766/v4_control_center.html 即可验收黄金模板 UI + 真实数据渲染。
