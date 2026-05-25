# V4_CUMULATIVE_VALIDATION_SOURCE_POLLUTION_ROOTCAUSE_CLEANUP_20260526

## 结论
本轮完成了累计验证污染源定位、active path 去污染、A/B-only 可信口径重建、渲染一致性修复与守卫 checker 加固。主指标已不再从旧 `124/140` 分支读取。

## 根因定位
1. `124/140` 来源：`data/runtime/status/v3v4_validation_summary_20260525.json` 的 `result_validation.cumulative` 旧恢复口径字段，被 `tools/generate_intel_desk_html.py::_validation_section` 读取。
2. `39/46`、`85/94` 来源：同一旧 summary 的 cumulative A/B 字段。
3. 污染回流原因：renderer fallback + allowlist/last-good 路径混读，导致“顶部卡片读取新字段、底部文案保留旧手写片段”的混源渲染。
4. 昨日 B `3/5` vs 文案 B `2/4` 冲突来源：顶部与底部读取不同源（顶部 summary，底部 stale 文案行）。

## 处置动作
1. 建立唯一 source-of-truth 合约：A/B-only 仅来自 official settled records；C/SKIP/UNKNOWN/outside_57/scout full pool/brief 全部禁止。
2. 重建累计口径（按 records 计算，非硬编码）：
   - Baseline: A 25/41, B 50/89, AB 75/130
   - Yesterday verified: A 3/5, B 2/4, AB 5/9
   - Pending: 1
   - Final cumulative: **A 28/46 · 60.9%, B 52/93 · 55.9%, AB 80/139 · 57.6%**
3. 隔离污染证据到 quarantine（保留取证，不再 active 读取）。
4. 修复 resolver/renderer：
   - 累计只读 official A/B-only SoT；缺失时显示 reason，不再 fallback 到旧高命中率。
   - 昨日 top 与 footer 强制同源。
   - 推荐/已验证/待补验分开展示。
5. 新增并加固 checker：`tools/check_v4_cumulative_validation_source_integrity.py`。

## 当前显示状态
1. 主累计区域已移除 `39/46`、`85/94`、`124/140`、`88.6%`。
2. 昨日验证顶部与底部文案已同源，不再出现 B `3/5` vs `2/4` 冲突。
3. 推荐/已验证/待补验已分开。
4. `127/192` 页面 HTTP 200。

## 文件处置
- quarantine 保留：
  - `data/runtime/quarantine/v4_cumulative_pollution_20260526/intel_ops_console.html.pre_cleanup`
  - `data/runtime/quarantine/v4_cumulative_pollution_20260526/v3v4_validation_summary_20260525.json.pre_cleanup`
- 其余污染源通过 active path 移除与 resolver/renderer 约束处理。

## 必答
1. 124/140 来自哪个文件：`v3v4_validation_summary_20260525.json`（旧 cumulative 字段）。
2. 39/46 和 85/94 来自哪个文件：同上。
3. 为什么旧数据又污染 dashboard：fallback 混源 + stale 文案残留。
4. 是 renderer fallback、allowlist、last_good、旧 summary，还是 stale HTML：主要是 renderer fallback + 旧 summary + stale HTML 文案混入；allowlist 路径参与放大。
5. 已删除/quarantine/disable 哪些文件：见 cleanup manifest；核心证据已 quarantine。
6. 哪些旧文件保留 forensic，为什么：pre-cleanup HTML 与旧 summary，为复盘取证与事故追溯。
7. 当前唯一可信 cumulative source：official A/B settled only SoT (`v4_official_ab_validation_source_of_truth_20260525.json`)。
8. 当前累计验证最终显示什么：A 28/46 · 60.9%，B 52/93 · 55.9%，A+B 80/139 · 57.6%。
9. 当前昨日验证最终显示什么：A 3/5 · 60.0%，B 2/4 · 50.0%，A+B 5/9 · 55.6%（待补验 1）。
10. 昨日 top card 和底部文案是否一致：是。
11. 推荐数/已验证数/待补验是否分开：是。
12. 是否还会回流 124/140：active path 已封堵；checker 已加固防回流。
13. 是否改策略：否。
14. 是否改 candidate：否。
15. 是否重写历史 validation：否（仅新建 SoT 汇总与渲染读取修复）。
16. 是否运行 full scan：否。
17. 是否 cloud/QQ/cron：均否。
18. 是否需要 BOSS 额外授权删除更多旧取证文件：如需物理删除历史 forensic 文件，需要额外授权；当前建议继续 quarantine 保留。
