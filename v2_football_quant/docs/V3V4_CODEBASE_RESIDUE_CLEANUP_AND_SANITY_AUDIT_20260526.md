# V3V4_CODEBASE_RESIDUE_CLEANUP_AND_SANITY_AUDIT_20260526

## 审计结论
- 语法审计：已通过（0 个 SyntaxError）。
- import smoke：已通过（0 个 import 错误）。
- active path 审计：未发现 20260522 stale / 124/140 回流 / 18/18 错误 audit active 污染。
- Live Bet：test/VOID 已排除 summary，本金与 ROI 口径正常。
- V3 世界杯 PG stale：保持 STALE_GUARDED，不作为正式结论 active 输入。

## 关键修复
1. 语法污染隔离（forensic 保留）
- `tools/gen_v4_ops_console.py` -> quarantine
- `tools/v3_steps_789.py` -> quarantine
- 原路径新增 `.stale` marker，避免编译/运行链路继续读取坏脚本。

2. import 兼容修复
- `tools/serve_live_bet_tracker.py` 增加 package-style import fallback，修复 `import tools.serve_live_bet_tracker` 场景下的 `ModuleNotFoundError`。

3. 新增总守卫 checker
- `tools/check_v3v4_codebase_residue_and_sanity.py`
- 聚合语法、import、active path、decommission、live bet、cron/cloud 守卫结果。

## 输出文件
- `data/runtime/status/v3v4_codebase_audit_git_freeze_20260526.json`
- `data/runtime/status/v3v4_codebase_residue_inventory_20260526.json`
- `data/runtime/status/v3v4_python_syntax_audit_20260526.json`
- `data/runtime/status/v3v4_import_smoke_audit_20260526.json`
- `data/runtime/status/v3v4_active_source_path_audit_20260526.json`
- `data/runtime/status/v3v4_cleanup_manifest_20260526.json`
- `data/runtime/status/v3v4_codebase_audit_git_manifest_20260526.json`
- `data/runtime/status/check_v3v4_codebase_residue_and_sanity_20260526.json`
- `data/runtime/status/v3v4_codebase_residue_cleanup_and_sanity_audit_20260526.json`

## 问题回答
1. 是否发现语法错误？发现 2 处坏脚本，已隔离后语法 PASS。
2. 是否发现 import 错误？发现 1 处（live bet server），已修复为兼容导入。
3. 是否存在 RapidAPI 残留 active？无 active 残留（API route checker 为 direct）。
4. 是否存在 V2/V33 active 残留？无 active 残留（decommission checker PASS）。
5. 是否存在 20260522 stale active？无。
6. 是否存在 124/140 active 回流？无。
7. 是否存在 18/18 active 回流？无。
8. V3 世界杯 stale PG 是否已隔离？是（STALE_GUARDED）。
9. live bet tracker 是否存在 test/VOID 污染？summary 已排除。
10. 哪些文件被 quarantine/disable/delete？两处坏脚本 quarantine + `.stale` 标记。
11. 是否改了 V4 策略？否。
12. 是否改了 candidate？否。
13. 是否改了 validation 数字？否。
14. 是否运行 full scan？否。
15. 是否 cloud publish / QQ / cron？否。
16. 是否可以进入稳定运行观察期？可以。
