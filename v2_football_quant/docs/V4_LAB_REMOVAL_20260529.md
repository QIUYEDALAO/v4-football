# V4 Lab 系统退役

## 退役原因

V4 Lab 已不再需要。正式 V4 已迁移至 all_eligible 候选发现模式并带 WHITELIST_57 / OUTSIDE_57 分层统计。

## 删除的文件

- `engine/v4_lab_fullscan.py`
- `engine/v4_lab_fullscan_new.py`（未跟踪）
- `engine/v4_lab/profile_loader.py`
- `config/v4_lab_profiles/`（6个profile + 2个未跟踪）
- `tools/check_v4_lab_fullscan_isolation.py`
- `tools/check_v4_lab_h2h_gate_before_full_scoring.py`
- `tools/check_v4_lab_production_clone_h2h_last3.py`
- `tools/analyze_lab_b_recent_form.py`
- `docs/lab/README.md`
- `data/runtime/lab/v4/`（本地 runtime 产物）

## 新增的文件

- `tools/check_v4_lab_removed.py`（Lab 删除验收 checker）

## 保留的文件

- `engine/v4_outside57_scanner.py`（正式 parallel scan 使用）
- `config/leagues_whitelist.json`（57白名单）

## 禁止项确认

| 项目 | 状态 |
|------|------|
| DEFAULT_RULES 修改 | ❌ 未改 |
| A/B 阈值修改 | ❌ 未改 |
| Candidate 评级修改 | ❌ 未改 |
| Cron 修改 | ❌ 未改 |
| Validation 重算 | ❌ 未触发 |
| Live bet 修改 | ❌ 未改 |
| QQ 推送 | ❌ 未推送 |
| Secret 泄露 | ❌ 无 |
| all_eligible 正式扫描 | ✅ 保留 |
| WHITELIST_57 / OUTSIDE_57 分层 | ✅ 保留 |
