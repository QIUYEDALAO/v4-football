# V4_LAZY_SHADOW_PRODUCTION_SWITCH_GUARD_20260530

## 目标
本轮不是正式切换。本轮只新增“正式切换前硬守卫（switch guard）”，确保未来若讨论切换 `rf_lazy_shadow`，必须先通过完整安全门。

## 当前结论
- `official_legacy` 仍是默认。
- `rf_lazy_shadow` 仍需显式 `--collection-mode rf_lazy_shadow` 才会启用。
- 12:00 任务未切到 lazy（cron payload 中未出现 `--collection-mode rf_lazy_shadow`，也未出现 `--max-fixtures`）。
- 当前状态只能是 `SWITCH_GUARD_PASS`，不是 `PRODUCTION_SWITCH_PASS`。

## 正式切换前必须满足的 guard（缺一不可）
1. `official_legacy` fallback 仍可用。
2. 默认模式不能是 `rf_lazy_shadow`。
3. 12:00 cron 不得包含 `--collection-mode rf_lazy_shadow`。
4. 12:00 cron 不得包含 `--max-fixtures`。
5. `DEFAULT_RULES` 未改。
6. A/B 阈值未改。
7. H2H runtime 正式判级语义未改。
8. 最近 daily shadow canary 为 PASS。
9. 最近 expanded canary 为 PASS。
10. 最近 rolling canary 为 PASS。
11. 最近 cache audit 为 PASS。
12. lazy 不得出现无法解释的 `scout=0`。
13. common fixtures 的 official grade mismatch 必须为 0。
14. official fixtures 必须全部被 lazy 覆盖。
15. official A/B fixtures 必须全部被 lazy 覆盖。
16. shadow-only rows 不得进入 `pending_bet_candidates`。
17. validation 不得使用 shadow grade。
18. live bet 不得使用 shadow grade。
19. QQ 不得使用 shadow grade。
20. runtime artifact 不得被 stage，secrets 不得被 stage。

## 执行边界确认
- 本轮未修改 cron、未切换生产默认、未启用正式切换。
- 本轮未修改 `DEFAULT_RULES` / A/B 阈值 / official grade。
- 本轮未触发 validation 重算，未改 live bet，未推 QQ。
- CPL 正式熔断仍未启用。

## 后续规则
即使未来继续观察结果良好，也不能自动切换生产。  
如要进入正式切换评审，必须由 BOSS 单独授权并再次通过 switch guard。
