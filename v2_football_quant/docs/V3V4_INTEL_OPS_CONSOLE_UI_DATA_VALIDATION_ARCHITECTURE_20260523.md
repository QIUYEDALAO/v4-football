# V3/V4 Intel Ops Console UI Data Validation Architecture — 20260523

status: PASS
phase: V3V4-INTEL-OPS-CONSOLE-UI-DATA-VALIDATION-REFIT-20260523

## 顶部四卡

1. 数据状态：今日已更新 / 最近数据 / 未就绪。
2. 候选结构：A / B / C / SKIP。
3. 复盘状态：REPORT_ONLY / 等待赛果 / 可复盘。
4. 阻断：0 / N。

## 主区域顺序

1. V3/V4 比赛验证。
2. V4 情报状态。
3. 候选列表。
4. V3 战备窗口。
5. 系统安全。
6. 下一动作。
7. 系统审计折叠区。

## 去重规则

- “今日决策”不再单独存在。
- 候选数量、采集日期、窗口、A/B/C/SKIP 并入 V4 情报状态。
- 如果 scan_date 小于 current_local_date，候选区使用“最近候选 / 数据日期 YYYYMMDD”，不得写“今日候选”。

## 验证模块规则

- 只读取正式 V4 attribution / validation / review 产物。
- C 显示为观察层，不进入 A+B 正式命中率。
- unknown 不显示为 0%，样本不足显示 N/A。
- V3 无结算样本时显示战备预留。
