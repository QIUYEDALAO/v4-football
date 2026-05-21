# Intel Ops Console Mobile Validation Restore Closeout — 最终报告

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-MOBILE-VALIDATION-RESTORE-CLOSEOUT-20260521

---

## Checker 最终汇总

| Checker | 结论 | Total | Pass | Fail |
|----------|------|-------|------|------|
| check_intel_ops_console_validation_detail_restore | PASS | 28 | 28 | 0 |
| check_intel_ops_console_candidate_folding_ux | PASS | 13 | 13 | 0 |
| check_intel_ops_console_readability_ux | PASS | 11 | 11 | 0 |
| check_intel_ops_console_post_night_state | PASS | 16 | 16 | 0 |
| check_intel_ops_console_no_notify_clean_ui | PASS | 19 | 19 | 0 |
| intel_ops_console | WARN_ONLY | 19 | 17 | 0 |
| intel_ops_console_chinese_ux | WARN_ONLY | 13 | 12 | 0 |

**总: 119 checks | 116 PASS | 3 WARN_ONLY | 0 FAIL | 0 BLOCKER**

---

## 10 项问题逐一回答

### 1. 上一轮为什么 PASS 与 todo 未完成矛盾？
两套任务序列并存：旧序列 #120-#127（早期合并阶段命名）与新序列 #128-#134（实际执行）描述同一批工作。旧序列在完成任务后未同步关闭，导致 #121 in_progress + #122-#127 pending 残留。实际所有工作通过新序列 #129-#134 完成。纯 todo 同步遗漏，非实际工作缺失。

### 2. B-card 四行布局是否完成？
**完成。** 3 张 B 卡全部采用 bs-r1/bs-r2/bs-r3/bs-r4 四行块布局。time|league 在 bs-r1，teams 独占 bs-r2（23px 字体），script|expand 在 bs-r3，time_bins 在 bs-r4（默认可见，border-top 分隔）。队名不被 script/expand 挤压。

### 3. V2 多日验证是否恢复？
**恢复。** 页面包含 2026-05-05 至 2026-05-15 共 10 天验证数据回放表。数据来自 v2_validation_detail_model_20260521.json（185 settled, 45.9%, r7=47.2%）。BET_LOCKED 口径清晰标注。

### 4. V2 锁仓证明是否恢复？
**恢复。** HTML 中包含 "V2 锁仓证明" 卡片，Ried vs Wolfsberger AC 作为 BET_LOCKED 示例可见。锁仓卡在 \<details\> 内默认折叠。

### 5. V4 昨日 B 级未知明细是否恢复？
**恢复。** 3 场 B 级 unknown 匹配全部可见：Arsenal vs Burnley、浙江队 vs 山东泰山、Ilves vs Inter Turku。数据来自 v4_yesterday_b_anomaly_detail_20260521.json。

### 6. RESULT_UNKNOWN_API_DISABLED 是否解释？
**解释。** 页面明确说明 API 未启用、赛果未拉取，全部 24 场 result_known=False。"不计入命中率" 清晰标注。

### 7. Validation credibility zone 是否重构？
**重构。** 首页摘要：数据血缘 PASS、V2 多日验证摘要、V4 B unknown N/A、C 观察 N/A。详细内容（V2 多日表、V2 锁仓证明、V4 B unknown 明细、raw lineage、C/SKIP 统计）全部在 \<details\> 内默认折叠。

### 8. V2 module display 是否完成？
**完成。** 首页摘要显示 V2 状态、BET_LOCKED 口径、滚动验证摘要。折叠详情包含 V2 锁仓证明、多日回放、rolling 7/14/30、WATCH/CANDIDATE 审计说明。

### 9. Todos 是否清零？
**清零。** 15/15 completed，0 in_progress，0 open（pending）。

### 10. Candidate / Validation 数字是否未变？
**未变。** A=1 B=3 C=5 SKIP=0。Validation 130 settled, 57.7%。

---

## 禁止项确认

| 禁止项 | 状态 |
|--------|------|
| capture_ran | false |
| push_enabled | false |
| D13 | false |
| V33 | false |
| HOURLY | false |
| strategy_changed | false |
| candidate_numbers_changed | false |
| validation_numbers_changed | false |

---

## 修改文件

| 文件 | 动作 |
|------|------|
| data/runtime/dashboard/intel_ops_console.html | 修改：B-card 4-row CSS+HTML，Zone 3/4 恢复，eye button padding |
| data/runtime/status/v2_validation_detail_model_20260521.json | 新建：V2 10 天聚合模型 |
| data/runtime/status/v4_yesterday_b_anomaly_detail_20260521.json | 新建：V4 B 异常明细 |
| tools/check_intel_ops_console_validation_detail_restore.py | 新建：28 项检查 |
| tools/check_intel_ops_console_candidate_folding_ux.py | 修改：bs-teams→bs-r2，time_bins 检查位置修正 |
| tools/check_intel_ops_console_readability_ux.py | 修改：bs-teams→bs-r2，time_bins 检查位置修正 |
