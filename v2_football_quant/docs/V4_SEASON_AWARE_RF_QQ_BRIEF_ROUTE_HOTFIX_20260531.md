# V4 Season-Aware RF QQ Brief Route Hotfix (2026-05-31)

## 问题原因
- `season_aware_rf` 生产扫描已产出 official A/B 与 pending candidates。
- 但原 `build_brief` 是 legacy 口径（基于 scout + explain_match），未按 `candidate_view` 的 official A/B 构建 season-aware 正式推荐简报。
- QQ 路由守卫虽然 PASS，但缺少可追踪的 season-aware brief 元数据（`brief_path` / `brief_sha256` / `sent_marker` / duplicate guard）。
- `tools/notify_cron_task_complete_qq.py` 是任务完成通知脚本，不是正式推荐发送器。

## 本次修复范围
1. 新增 mode-aware brief builder：
   - `engine/v4_openclaw_brief.py`
   - `build_brief(..., production_grade_mode, candidate_view_path)`
   - `season_aware_rf` 模式下从 `candidate_view` 读取 official A/B 渲染。
2. 保留 legacy brief 与回滚路径：
   - `_build_brief_legacy` 不变，`official_legacy` 仍可用。
3. `engine/v4_scan_and_brief.py` 写入 season-aware brief 路由元数据：
   - `brief_sha256`
   - `sent_marker_path`
   - `duplicate_sent_exists`
   - `allowed_to_send` 包含 duplicate guard。
4. 新增推荐路由 dry-run 工具：
   - `tools/run_v4_season_aware_qq_recommendation_dryrun.py`
   - 只读 candidate_view，生成 brief，输出 route decision。
5. 新增 checker：
   - `tools/check_v4_season_aware_qq_brief_route.py`

## 内容守卫
- 主推荐只允许 official A/B。
- C观察 / SKIP / shadow-only / dryrun-only 不进入主推荐列表。
- 文本包含：
  - `production_grade_mode=season_aware_rf`
  - `official_grade_source=market_adjusted_shadow_grade`
- 若 A/B=0，输出“无A/B上半场主推荐”，并保持不发送。

## 安全边界
- 不修改评分逻辑（不改 official grade 计算规则）。
- 不修改 pending 内容（仅渲染/路由）。
- 不重扫、不调用 API。
- 不重算 validation。
- 不修改 live bet。
- 不修改 cron。
- 不真实推 QQ（Codex 阶段 `real_send=false`）。

## Dry-run 结果口径
- 产物写入 `data/runtime/status/v4_scan_<window>_dryrun_<date>.json`。
- 仅写 dry-run marker，不写 sent marker。
- duplicate guard：若 sent marker 已存在，则 route 显式 BLOCK。

## 后续
- OpenClaw 只读验收通过后，才可按 BOSS 单独授权执行真实 push completion。
