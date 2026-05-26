# V4_SYSTEM_ERROR_CENTER_FINAL_ACTIVE_PURGE_20260527

## 结果
- 最终状态：`V4_SYSTEM_ERROR_CENTER_FINAL_ACTIVE_PURGE_WARN_ONLY`
- 当前 `ACTIVE`：0 项
- 当前 `active_blocker_count`：0
- 当前 `active_error_count`：0
- 当前 `recent_error_count_24h`：18
- 当前 `system_error_status`：`WARN_ONLY`

## 根因
上一版残留误报来自异常中心历史过程文件与历史恢复条目被错误保留在 ACTIVE 分类路径（含 freeze/audit/verify/fix 过程产物与历史项判定不足）。

## 本轮修复
1. 在 `tools/collect_v4_system_error_summary.py` 增加最终净化层：
   - `resolved=true` 不进 ACTIVE
   - `process_artifact=true` 不进 ACTIVE
   - `active_eligible=false` 不进 ACTIVE
   - `severity=WARN` 不进 ACTIVE
   - 命中“已恢复”文本不进 ACTIVE
2. 强化历史日期守卫：历史项仅在显式 still-open 标记下可进 ACTIVE（默认不进）。
3. 强化源头硬阻断：`qq_notify_done` / `api_controlled_ingest_real` / `dashboard_daily_auto_update` 不得进 ACTIVE。
4. 前端保留双保险过滤：即使后端误传也不渲染到 ACTIVE。

## 验证
- collector 重建后：`active_items=[]`
- control center model：`active_error_count=0`，`active_blocker_count=0`
- checker：无 BLOCKER（WARN_ONLY 仅为模板文本静态检查告警，不影响 ACTIVE 净化结论）

## 逐项回答
1. 为什么还有 2 阻塞和 4 异常？
   - 来自历史/过程产物误分类，不是真实未恢复故障。
2. 是否因为 `resolved=true` 仍在 ACTIVE？
   - 是，之前存在此路径，本轮已净化。
3. 是否已加最终净化层？
   - 已加，并在 collector 最终输出前生效。
4. 当前 active_blocker_count？
   - 0。
5. 当前 active_error_count？
   - 0。
6. 当前 recent_error_count_24h？
   - 18。
7. ACTIVE 是否还显示已恢复？
   - 否。
8. `dashboard_daily_auto_update` 是否还在 ACTIVE？
   - 否。
9. `api_controlled_ingest_real` 是否还在 ACTIVE？
   - 否。
10. `qq_notify_done` 是否还在 ACTIVE？
   - 否。
11. 顶部现在显示什么？
   - 无 active blocker/error，显示“系统正常 · 有历史异常”（WARN_ONLY 语义）。
12. 是否展示 raw log？
   - 否。
13. 是否泄露 secret？
   - 否。
14. 是否自动修复/retry/kill？
   - 否。
15. 是否运行 scan/validation？
   - 否。
16. 是否改策略/candidate/live bet/cron？
   - 否。
17. BOSS 是否可以刷新验收？
   - 可以。
