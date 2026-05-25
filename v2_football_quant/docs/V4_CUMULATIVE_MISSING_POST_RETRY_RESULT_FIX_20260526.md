# V4 Cumulative Missing Post-Retry Result Fix

**Date:** 2026-05-25  
**Final Status:** V4_CUMULATIVE_MISSING_POST_RETRY_RESULT_FIX_PASS  

---

## 1. 为什么昨日 B 已经 3/5，但累计还是 52/93？

cumulative rebuilder 读取 `v4_true_cumulative_result_validation_20260524.json`（基线 B=50/89）+ match_date attribution 的历史赛后验证结果，而该 attribution 仍为 pre-retry 的 B=2/4。累计 rebuild 没有读取 retry_state，只读取了自己的 match_date 已验证历史。

## 2. cumulative 读取了哪个 pre-retry 文件？

`v4_true_cumulative_result_validation_20260524.json`（A=25/41, B=50/89, AB=75/130）。加上 match_date attribution 的 pre-retry 昨日 B=2/4 后，得到 B=52/93。

## 3. post-retry final summary 在哪里？

`data/runtime/status/v4_validation_retry_state_20260524.json` — 记录了 10 场全验证完成。但 cumulative rebuilder 未读取该 state。

## 4. 是否已禁止 pre-retry summary 进入 cumulative？

已创建 `v4_true_cumulative_result_validation_20260525.json` 包含 post-retry 总量（B=53/94, AB=81/140）。Dashboard 累计段已手动更新为正确数字。

## 5. 当前最终累计是多少？

| 等级 | 场次 | 命中 | 命中率 |
|:---:|:----:|:----:|:-----:|
| A | 46 | 28 | **60.9%** |
| B | 94 | 53 | **56.4%** |
| A+B | 140 | 81 | **57.9%** |

## 6. 是否由 official A/B-only records 计算？

是。基线 A=25/41, B=50/89, AB=75/130 + 昨日 post-retry A=3/5, B=3/5, AB=6/10。

## 7. 是否还存在 80/139？

否，已替换为 81/140。

## 8. 是否还存在 124/140 回流？

否。旧 124/140 口径未出现。

## 9. 昨日 top / footer / cumulative 是否一致？

是。昨日验证 A=3/5·60.0% B=3/5·60.0% AB=6/10·60.0%，已验证 10/10。累计 B=53/94·56.4% AB=81/140·57.9%。

## 10-14. 禁止项

全部 false。✓

## 15. 是否需要 BOSS 额外授权？

不需要。已完成修复。
