# V3V4 Dashboard Yesterday Validation Visibility Hotfix Issue List (20260524)

Phase: `V3V4-DASHBOARD-YESTERDAY-VALIDATION-VISIBILITY-HOTFIX-20260524`

## 固定问题清单

1. `after-scan` 已恢复（非 `SCAN_NOT_READY`），但“昨日验证”仍未显示。
2. `after-scan` 可能在整页重建时清空 `validation section`。
3. `yesterday validation target` 应固定为 `20260523`（相对 dashboard_date=20260524）。
4. `dashboard display date` 应固定为 `20260524`。
5. “今日候选”与“昨日验证”必须采用不同日期口径（今日=20260524，昨日验证=20260523）。
6. validation 统计必须基于 `match_date`，不得基于 `scan_date`。
7. `brief` 不得用于命中率计算。
8. `script validation` 必须与 `result validation` 分离展示和分母计算。
9. `C` 不得恢复进候选/验证/剧本验证展示。
10. checker 必须拦截“候选已更新但昨日验证消失”的回归。

## Step 1 判定

- PASS 条件：问题清单完整（10/10）。
- BLOCKER 条件：流程仍允许 `after-scan` 清空 `validation section`。

当前判定：`PASS`（问题清单完整，进入 Step 2 数据源审计）。
