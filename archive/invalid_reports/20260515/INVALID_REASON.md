# 20260515 V4复盘 — 无效报告说明

- 生成时间：2026-05-16 15:57
- 原因：37/76 partial validation 当作正式 final review 生成
- 样本范围污染：A6/B8 与 BOSS 正式口径不一致
- readiness=REVIEW_NOT_READY
- guard=BLOCKER（MATCH_COUNT_MISMATCH）
- 不得进入滚动统计 / 周报 / 月报 / QQ推送
- partial validation 不得计算正式命中率
- 已从 data/daily_reports/ 和 data/runtime/status/ 移动到本目录
