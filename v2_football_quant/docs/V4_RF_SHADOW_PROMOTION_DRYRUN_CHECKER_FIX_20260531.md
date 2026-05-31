# V4 RF Shadow Promotion Dry-Run Checker Fix (20260531)

## 目标
本轮仅修复 `tools/check_v4_rf_shadow_to_official_promotion_dryrun.py` 的误判口径，解决旧 43 场假设无法适配当前 97 场全量产物的问题。

## 本轮范围
- 仅修 checker 与 dryrun artifact 元信息口径。
- 不重新扫描。
- 不调用 API。
- 不修改 official grade。
- 不写 `pending_bet_candidates`。
- 不进入 validation。
- 不推 QQ。
- 不修改 cron。

## False Positive 根因
旧 checker 把官方口径硬编码为 `A=0, B=0, SKIP=43`，并以此判断是否“official grade changed”。

当前 20260531 已是 97 场全量产物，继续使用 43 场常量会产生 43->97 的误报（false positive）。

## 修复内容
1. checker 移除 43 场硬编码。
2. checker 改为读取当前 artifact 的动态总量字段：
   - `source_row_count`
   - `official_total`
   - `dryrun_total`
3. checker 对 official 口径改为动态判定：
   - `expected_skip = source_row_count - official_A - official_B - official_C`
   - 允许 candidate_view 顶层 `SKIP_count` 为 0（兼容旧/简化结构），并使用动态推导值核验总量。
4. build 工具补充元信息字段，避免 checker 再依赖固定常量。
5. 保留全部安全检查：
   - dryrun A/B 来源
   - MARKET_HARD_VETO 保护
   - MARKET_NO_DATA/NO_MARKET 保护
   - official 未改
   - pending_bet/validation/live_bet/QQ/cron/DEFAULT_RULES 未触碰

## 结果
- dryrun 结果未变：`A=0, B=5, C=13, SKIP=79`。
- checker 不再因 43->97 误报。
- official grade 未改。
- 本轮未重新 scan、未调用 API、未推 QQ、未改 cron。

## 安全声明
本报告与 dryrun 产物均为观察用途，不构成正式推荐，不进入正式候选与投放链路。
