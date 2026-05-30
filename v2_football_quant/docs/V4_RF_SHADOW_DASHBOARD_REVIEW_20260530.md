# V4 RF Shadow Dashboard Review（2026-05-30）

## 目标与边界

本轮是 **Phase 4A 展示层评审**，目标是把 RF shadow 结果在 dashboard 中清晰展示，便于人工复盘 official 与 shadow 差异。

本轮明确不是正式策略切换：

1. 不修改 official grade。
2. 不修改 DEFAULT_RULES。
3. 不修改 A/B 阈值。
4. 不进入 CPL。
5. 不进入 Phase 4B/5/6。
6. 不调用 API。
7. 不执行正式 scan。

## 展示内容

在候选列表展开区新增 **RF影子观察**，重点展示：

1. 官方等级（official grade）
2. RF影子等级（rf_shadow_grade）
3. 盘口调整后影子等级（market_adjusted_shadow_grade）
4. 影子路线（rf_shadow_route）
5. 近期状态说明（rf_shadow_reason）
6. 双方平衡说明（rf_balance_reason）
7. H2H近5加分说明（h2h_recent5_bonus_reason）
8. 初盘判断说明（opening_market_reason）
9. 盘口调整说明（market_adjustment_reason）
10. 差异说明（official_vs_shadow_diff / official_vs_shadow_reason）

并固定提示：

- **影子观察，不作为投注推荐。**

## 展示口径

1. 页面保持列表布局，不恢复大卡片。
2. 主行显示官方 / RF影子 / 盘口后影子，展开区显示详细解释。
3. 内部枚举做中文映射，避免直接给 BOSS 看原始 enum。
4. 处理缺失值，不展示 `undefined/null/NaN`。

## 不变项（强约束）

1. shadow 不进入 todo_count 计算。
2. shadow 不进入 pending_bet_candidates。
3. shadow 不进入 validation 统计口径。
4. shadow 不进入 QQ 推送口径。
5. live bet 流程仍只服务 official A/B 候选。

## 自检与验收方式

本轮采用轻量自检：

1. `python3 tools/build_v4_control_center_model.py`
2. `python3 tools/check_v4_rf_shadow_dashboard_review.py`
3. 复用 guard/checker 验证 no-regrade、no-validation-change、no-livebet-change、no-QQ-change。

说明：本轮验证的是 dashboard 展示闭环，不等同于正式生产 dry-run 验收结论。
