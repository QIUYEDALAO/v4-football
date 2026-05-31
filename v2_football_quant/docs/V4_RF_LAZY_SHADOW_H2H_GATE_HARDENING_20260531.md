# V4_RF_LAZY_SHADOW_H2H_GATE_HARDENING_20260531

## 背景
本轮修复的是 **代码设计问题**，不是单纯网络问题。
此前 `rf_lazy_shadow` 在大样本场景中出现 `H2H 27/106` 这类进度表现，说明链路虽有 `h2h_required` 字段，但仍接近对原始 fixtures 做大范围串行查询，Lazy gate 失败。

## 根因
1. H2H gate 没有形成“统一前置预判 + 预算截断”。
2. H2H 进度日志分母使用 raw fixtures，容易误导为全量进入。
3. 缺少明确的 budget/timeout 保护和可视化 skip reason。

## 本轮修复
### 1) H2H 改为 RF + Market 后执行
仅在 `--collection-mode rf_lazy_shadow` 下：
- 先做 Recent Form 与 Opening Market。
- 先做 shadow prefilter 与 hard gate。
- 再进入 H2H。

### 2) H2H 前硬拦截
新增/强化前置跳过原因：
- `MARKET_HARD_VETO_BEFORE_H2H`
- `NO_MARKET_BEFORE_H2H`
- `MARKET_NO_DATA_RF_NOT_STRONG`
- `RF_SHADOW_SKIP`
- `MARKET_ADJUSTED_SKIP`
- `FRIENDLY_SKIP_H2H`
- `YOUTH_SKIP_H2H`
- `NON_FORMAL_SKIP_H2H`
- `RECENT10_BELOW_GATE`
- `RECENT5_COLD`
- `DATA_MISSING_SKIP_H2H`
- `H2H_BUDGET_EXCEEDED`
- `H2H_TIMEOUT_SKIP`

### 3) H2H budget + timeout
- `h2h_max_required_ratio = 35%`
- 超预算按优先级截断并标记 `H2H_BUDGET_EXCEEDED`
- `h2h_per_fixture_timeout_seconds = 20`
- 超时标记 `H2H_TIMEOUT_SKIP`，且保留 scout row

### 4) 行保留与官方隔离
- `h2h_required=false` 不调用 H2H API。
- `h2h_required=false` 仍保留 scout row。
- `official_legacy` 默认链路不受影响。
- 不改 official grade，不改 cron，不改 validation/live bet/QQ。

### 5) 可观测性
新增/透传字段用于 dashboard：
- `h2h_budget_exceeded_reason`
- `h2h_timeout_seconds`
- `h2h_timed_out`
- `h2h_required_total`
- `h2h_required_ratio_cap`

并在 dashboard 展示 H2H 跳过原因、预算状态与超时阈值。

## 小样本验证（no-push）
命令：
```bash
python3 -u engine/v4_scan_and_brief.py --date 20260531 --window midday --no-push --scan-engine serial --fixture-universe whitelist --collection-mode rf_lazy_shadow --max-fixtures 20
```
结果要点：
- raw=20, scout=20
- h2h_required=true 2 / false 18（10%，低于 35%）
- 未出现 scout=0
- official grade mismatch=0
- QQ 未推

## 结论
本轮为 H2H gate hardening 修复，不是正式切换：
- `official_legacy` 仍为默认
- 12:00 cron 未改
- 若需全量重跑或推进正式切换，仍需 BOSS 单独授权
