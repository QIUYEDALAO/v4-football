# V3V4_TEAM_CN_PERSISTENT_PIPELINE_FIX_20260525

## 结果总览
- 已完成上游 pipeline 持久化修复：alias + resolver + marker enrich + renderer + runner + pipeline checker。
- 本地与内网 8765 页面验证通过，重建后中文不回流。
- Git commit/push 已完成。
- Cloud hotfix deploy 阶段 BLOCKER：远端 SSH 不可达，且 cloud bundle secret scan 拦截。

## 必答
1. 为什么之前每天会回英文？
- 因为之前主要是 served HTML 临时 patch，未把 team_cn 解析稳定接入 marker 与 runner 重建链路。

2. 现在是否修到上游 pipeline？
- 是。

3. alias 文件在哪里？
- `data/config/team_cn_aliases.json`。

4. resolver 是否被 runner 调用？
- 是。`run_v3v4_dashboard_daily_update.py` 已接入 `enrich_team_cn()`。

5. marker 是否写入 home_team_cn / away_team_cn？
- 是。candidate_view 与 outside_57 pool 均写入 `home_team_cn/away_team_cn/home_team_en/away_team_en/team_cn_source/team_cn_missing`。

6. renderer 是否禁止英文 fallback？
- 是。主标题使用中文；中文缺失显示 `中文名缺失：<English>`；英文仅审计小字。

7. checker 是否能防止明天回流？
- 是。新增 `tools/check_v3v4_team_cn_pipeline_persistent.py` 检查 alias/resolver/marker/runner/served HTML 全链路。

8. 是否改策略？
- 否。

9. 是否改验证数字？
- 否。

10. 是否 cloud deploy？
- 未完成，BLOCKER。

11. 是否还需要每天手工翻译？
- 不需要（在 cloud deploy 完成前，本地链路已持久化）。
