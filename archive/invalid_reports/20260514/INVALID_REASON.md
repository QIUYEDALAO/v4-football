# INVALID REASON — 2026-05-14 V4复盘报告

生成日期：2026-05-15 22:38
作废日期：2026-05-15 22:44
作废人：BOSS 指令

## 错误原因

1. 原报告使用 v4_ht_recommend_validation_20260514.json 全量字段反推正式分级；
2. validation/attribution 文件包含所有扫描比赛（45场）的预测分级，非正式推荐样本；
3. 2026-05-14 正式 V4 brief 实际输出：
   - A：0
   - B：0
   - A+B 主推荐：0
   - HT_SKIP：7
   - 正式推荐：无
4. 原报告错误统计 A=7、B=5、A+B=12，与正式 brief 严重冲突；
5. validation/attribution 只能作为正式样本的赛果补充，不得决定样本范围。

## 后果

- 不得进入日报、周报、月报、滚动验证
- 不得用于任何命中率计算
- 已归档永久保留

## 修复

- 新增守卫：正式复盘须先读取正式 brief，若 A=0/B=0 则复盘不得生成 A/B>0
- validation/attribution 改为仅补充正式推荐样本的赛果
