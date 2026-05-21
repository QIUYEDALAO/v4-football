# Intel Ops Console Validation Detail Restore — 问题清单

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-VALIDATION-DETAIL-RESTORE-20260521

---

## 问题总览

| # | 问题 | 严重级别 | 影响 | 数据依据 |
|---|------|---------|------|---------|
| 1 | V2多日验证缺失 | HIGH | 页面只显示 N/A/样本不足，实际有 20260505-20260515 共10天 verified 数据 | verified_*.json ×10 |
| 2 | V2 DAILY_POOL 历史缺失 | HIGH | v2_window_notify 20260516-20260519 存在但未展示 | v2_window_notify_*.json ×4 |
| 3 | V2 BET_LOCKED历史未完整展示 | HIGH | 20260519 new_bet_locked=1, 历史累计130场已结算 | production_verified + verified files |
| 4 | V2只认BET_LOCKED口径需可见 | MEDIUM | 页面未标注"仅BET_LOCKED进入正式命中率" | — |
| 5 | V4昨日B级只显示N/A，无场次明细 | CRITICAL | v4_result_attribution_20260519.jsonl 含3场B级(Arsenal/Burnley, 浙江/山东, Ilves/Inter Turku) | pre_grade=B ×3 |
| 6 | RESULT_UNKNOWN_API_DISABLED未解释 | HIGH | 全部24场 result_known=False，应说明API未启用/赛果未拉取 | result_known=False ×24 |
| 7 | B级异常/未知未分类型 | MEDIUM | 3场B级全部 result_known=False，原因相同但未分类型展示 | — |
| 8 | C观察只摘要，无展开统计 | MEDIUM | 13场C级全部 result_known=False 但只显示"仅观察" | pre_grade=C ×13 |
| 9 | raw lineage不适合首页但必须可展开 | LOW | validation lineage proof 数据存在，当前完全隐藏 | — |
| 10 | checker未验证明细存在 | MEDIUM | 现有 checker 只验数字不变，不验明细 | — |

## 数据事实

### V2 验证数据
- verified_*.json: 20260505～20260515 共10天
- v2_window_notify_*.json: 20260516～20260519 共4天
- 累计已结算: 130场 (from validation AB133 audit)
- 历史命中率: 57.7% (from production recommendation)
- BET_LOCKED最新: 1场 (20260519, Ried vs Wolfsberger AC)

### V4 昨日 B 级数据 (20260519)
- 总计 24 场: B=3, C=13, SKIP=8
- 全部 result_known=False
- B 级明细:
  1. Arsenal vs Burnley (英超)
  2. Hangzhou Greentown vs Shandong Luneng (中超)
  3. Ilves vs Inter Turku (芬超)

## 执行计划

| Step | 动作 | 输出 |
|------|------|------|
| 1 | 建立问题清单 | 本文档 + JSON |
| 2 | 恢复 V2 多日验证模型 | v2_validation_detail_model_20260521.json |
| 3 | 恢复 V4 昨日 B 级异常明细 | v4_yesterday_b_anomaly_detail_20260521.json |
| 4 | 重构验证可信度区 | intel_ops_console.html 验证区 |
| 5 | 恢复 V2 模块 | intel_ops_console.html V2 区 |
| 6 | 新增 checker | check_intel_ops_console_validation_detail_restore.py |
| 7 | 运行验证 | 全部 8+1 checker |
| 8 | 生成报告 | docs + status JSON |
