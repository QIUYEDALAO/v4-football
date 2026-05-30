# V4-RF-CPL 分阶段实施任务清单

版本：v1
日期：2026-05-30
设计基线：V4_SYSTEM_SLIM_AND_WHITELIST_RESTORE_PASS

---

## Phase 0 — 系统精简与白名单恢复

**状态：** ✅ 已完成

**任务目标：**
- 恢复 V4 正式生产为 57 联赛白名单
- 清理废弃文件
- 归档实验报告
- 新增 canonical checker

**产出：**
- `docs/V4_LEAGUE_WHITELIST_OPERATING_GUIDE_20260530.md`
- `docs/V4_SYSTEM_CLEANUP_REMOVED_JUNK_20260530.md`
- `tools/check_v4_system_slim_and_whitelist_mode.py`

---

## Phase 1 — 新增 RF 字段计算（不改正式评级）

### 任务目标
在 `engine/v4_runner.py` 中新增 Recent Form Primary 字段计算。
只增加数据字段，不出现在正式评分中。

### 执行方
Codex

### 允许修改文件
- `engine/v4_runner.py`（仅新增字段计算逻辑）
- `engine/v4_scan_and_brief.py`（仅传递新字段到 candidate_view）

### 禁止事项
- 禁止修改 `DEFAULT_RULES`
- 禁止修改 `v4_match_intelligence.py` 评分逻辑
- 禁止修改 H2H 运行时逻辑
- 禁止修改 recent form 现有正式逻辑

### checker
```bash
python3 tools/check_v4_production_default_rules_guard.py
python3 tools/check_v4_system_slim_and_whitelist_mode.py
python3 tools/check_v4_rf_cpl_design_freeze.py
```

### PASS 条件
- 所有 checker PASS
- 新字段在 candidate_view JSON 中可见
- 正式评分无变化

### BLOCKER 条件
- DEFAULT_RULES 被改
- 正式评分结果变化
- scan 入口断裂

### 回滚方式
```bash
git checkout -- engine/v4_runner.py engine/v4_scan_and_brief.py
```

---

## Phase 2 — 新增 RF shadow grade（不改正式评级）

### 任务目标
在 `engine/v4_match_intelligence.py` 中新增 `rf_shadow_grade` 计算逻辑。
shadow grade 写入选候选数据但不出现在正式 `official_grade` 中。

### 执行方
Codex

### 允许修改文件
- `engine/v4_match_intelligence.py`（仅新增 shadow 计算，不触及正式评分函数）
- `engine/v4_scan_and_brief.py`（将 shadow 字段写入输出）

### 禁止事项
- 禁止修改正式评分函数 `compute_ht_score` / `grade_candidate` / `recommend_for_bet`
- 禁止修改 `DEFAULT_RULES`
- 禁止修改正式 A/B/SKIP 逻辑

### checker
```bash
python3 tools/check_v4_production_default_rules_guard.py
python3 tools/check_v4_rf_cpl_design_freeze.py
```

### PASS 条件
- shadow grade 存在于 candidate 输出中
- `official_grade` 与 shadow 前一致
- 所有 checker PASS

### BLOCKER 条件
- `official_grade` 发生变化
- DEFAULT_RULES 被改

### 回滚方式
```bash
git checkout -- engine/v4_match_intelligence.py
```

---

## Phase 3 — 新增 H2H Assist shadow（不改正式评级）

### 任务目标
新增 H2H Assist 辅助状态字段，标记 H2H 在新体系下的角色。

### 执行方
Codex

### 允许修改文件
- `engine/data_sources/h2h_engine.py`（新增 H2H Assist 辅助状态计算）
- `engine/v4_match_intelligence.py`（引入 H2H Assist 字段）
- `engine/v4_runner.py`（传递 H2H Assist 数据）

### 禁止事项
- 禁止修改 H2H 当前正式逻辑（`evaluate_h2h_edge` 等核心函数不变）
- 禁止修改 `DEFAULT_RULES` 中 H2H 阈值

### checker
```bash
python3 tools/check_v4_production_default_rules_guard.py
python3 tools/check_v4_rf_cpl_design_freeze.py
```

### PASS 条件
- H2H Assist 字段存在于 candidate 输出
- 正式评分中 H2H 权重未变
- 所有 checker PASS

### BLOCKER 条件
- `evaluate_h2h_edge` 返回值变化
- H2H 硬过滤行为变化

---

## Phase 4 — 新增 Dominant Favorite shadow route（不改正式评级）

### 任务目标
新增 DF 路线判断，输出 shadow route 和 shadow 评分。

### 执行方
Codex

### 允许修改文件
- `engine/v4_runner.py`（新增 handicap 参数捕获、DF 数据采集）
- `engine/v4_match_intelligence.py`（新增 DF shadow 评分逻辑）

### 禁止事项
- 禁止修改正式 market 盘口采集逻辑
- 禁止修改正式评分逻辑

### checker
```bash
python3 tools/check_v4_production_default_rules_guard.py
python3 tools/check_v4_rf_cpl_design_freeze.py
```

### PASS 条件
- DF 字段在 candidate 输出中可见
- 正式评分未变化

---

## Phase 5 — 新增 CPL shadow guard（不改正式评级）

### 任务目标
新增 Combat Power Loss shadow 检查，输出 CPL 状态字段但不熔断。

### 执行方
Codex

### 允许修改文件
- `engine/v4_runner.py`（新增伤病数据采集）
- `engine/v4_match_intelligence.py`（新增 CPL shadow 状态）

### 禁止事项
- 禁止修改正式评级熔断逻辑
- 禁止修改 NO_MARKET 逻辑

### checker
```bash
python3 tools/check_v4_production_default_rules_guard.py
python3 tools/check_v4_rf_cpl_design_freeze.py
python3 tools/check_v4_no_market_core_validation_skip.py
```

### PASS 条件
- CPL 字段在 candidate 输出中可见
- 正式评分未变化
- NO_MARKET checker 未受影响

---

## Phase 6 — 新增 COMBAT_POWER_LOSS 人工排除机制

### 任务目标
实现人工战力熔断 marker 的存储和展示。

### 执行方
Codex / OpenClaw

### 允许修改文件
- `tools/serve_live_bet_tracker.py`（新增 COMBAT_POWER_LOSS marker 路由）
- dashboard template（新增按钮）

### 禁止事项
- 禁止修改 NO_MARKET marker 逻辑
- 禁止物理删除 candidate/scout/brief

### checker
```bash
python3 tools/check_v4_no_market_core_validation_skip.py
python3 tools/check_v4_system_slim_and_whitelist_mode.py
```

### PASS 条件
- COMBAT_POWER_LOSS marker 可写入、可读取
- NO_MARKET checker 仍 PASS

---

## Phase 7 — Dashboard 展示 RF / DF / H2H Assist / CPL

### 任务目标
在 dashboard 候选列表和展开区展示新字段。

### 执行方
Codex

### 允许修改文件
- `data/runtime/dashboard/v4_control_center.html`（仅前端展示）
- `tools/build_v4_control_center_model.py`（传递新字段到前端）

### 禁止事项
- 禁止 dashboard 重算 `official_grade`
- 禁止修改 validation 显示逻辑

### checker
```bash
python3 tools/check_v4_control_center.py
python3 tools/check_v4_rf_cpl_design_freeze.py
```

### PASS 条件
- dashboard 展示新字段
- `official_grade` 未变
- dashboard checker PASS

---

## Phase 8 — BOSS 审核 shadow 输出

### 任务目标
BOSS 审核 Phase 1-7 的 shadow 输出，确定最终阈值。

### 执行方
BOSS

### 允许修改文件
无（仅审核）

### 动作
- 查看 shadow grade 与实际赛果对比
- 确认 RF 路线 A/B 阈值
- 确认 DF 路线 A/B 阈值
- 确认 CPL 熔断表
- 确认 H2H Assist 处理方式
- 决定是否进入 Phase 9

### PASS 条件
BOSS 签字确认阴影输出符合预期。

---

## Phase 9 — 正式切换 V4-RF-CPL

### 任务目标
将 shadow grade 切换为正式 `official_grade`。

### 执行方
Codex

### 允许修改文件
- `engine/v4_match_intelligence.py`（正式评分函数改用 RF 主评分逻辑）
- `DEFAULT_RULES`（更新阈值配置）

### 禁止事项
- 禁止修改 validation 历史
- 禁止修改 live bet 记录
- 禁止推 QQ

### checker
```bash
# 全量 checker 执行
python3 tools/check_v4_production_default_rules_guard.py
python3 tools/check_v4_system_slim_and_whitelist_mode.py
python3 tools/check_v4_control_center.py
python3 tools/check_v4_no_market_core_validation_skip.py
python3 tools/check_v4_true_goal_time_distribution.py
python3 tools/check_v4_playbook_script_and_time_distribution.py
python3 tools/check_v4_rf_cpl_design_freeze.py
```

### PASS 条件
- 全部 checker PASS
- dashboard 正常显示
- validation 正常跑
- BOSS 确认

### 回滚方式
```bash
git revert <phase9_commit>
```

---

## Phase 10 — 新版 rolling validation

### 任务目标
新增 V4-RF-CPL 命中的滚动验证看板。

### 执行方
Codex

### 允许修改文件
- `engine/v4_ht_result_validator.py`（新增 RF 验证统计）
- `tools/build_v4_control_center_model.py`（新增验证看板数据）

### 禁止事项
- 禁止修改旧版 validation 历史
- 禁止修改 live bet 记录

### checker
```bash
python3 tools/check_v4_control_center.py
python3 tools/check_v4_rf_cpl_design_freeze.py
```

### PASS 条件
- 新版验证数据在 dashboard 可见
- 旧版验证数据不受影响

---

*文档结束 — 设计冻结，未开始实施。*
