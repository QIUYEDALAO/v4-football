# V4_OFFICIAL_FIXTURE_ID_VALIDATION_PIPELINE_PERSISTENT_FIX_20260526

## 当前结论
- 结论：`V4_OFFICIAL_FIXTURE_ID_VALIDATION_PIPELINE_PERSISTENT_FIX_BLOCKED`
- 阻塞点：当前运行环境无可用 API key（`API_PROVIDER_OR_HEADER_BLOCKED`，`config.secrets.API_KEY` 不存在），无法完成 Step 3 的 live bounded API 复现。

## 已完成
1. 已冻结并记录手动 bounded 成功产物（A 3/5、B 2/4、A+B 5/9，Bodo timeout excluded）。
2. 已审计自动链路旧根因（match_date-only + final no-api-only）。
3. 已新增工具：`tools/run_v4_official_fixture_id_validation.py`。
4. 已接入 13:00 after-validation runner 调用 fixture_id bounded validation。
5. 已接入 14:00 final runner 的“必要时 fixture_id rerun，否则 NOOP”逻辑。

## 阻塞原因
- 本地 API 凭据不可用，导致 bounded validation 仅能产出 safe N/A，无法现场复现 3/5、2/4、5/9。
- 按 BOSS 规则：无 API key 不得伪造昨日验证数字，因此必须在 Step 3 停止。

## 回答（已确认）
1. 为什么之前自动 validation 一直 N/A：旧链路主要依赖 match_date attribution，且 final runner `--no-api` 不会主动按 fixture_id 拉 yesterday official A/B。
2. 手动 bounded rerun 为什么成功：直接对 official fixture_id 调 `fixtures?id` + `fixtures/events`，并把 timeout/未结算排除分母。
3. 13:00 runner 是否已接入 fixture_id validation：代码已接入（待 API 凭据实测）。
4. 14:00 final 是否已接入必要时 bounded rerun：代码已接入（待 API 凭据实测）。
5. 明天 cron 是否会走新链路：代码入口已就位，但当前环境无法完成 live 预检证明。
6. 昨日验证当前显示什么：在无 API 凭据下为 safe N/A。
7. Bodo/Glimt timeout 如何处理：记为 excluded，不进入分母。
8. 是否用了 scout full pool：否，仅 official candidate_view A/B。
9. 是否用了 brief 反推：否。
10. 是否用了 scan_date：否（match_date / fixture_id）。
11. 是否改策略：否。
12. 是否改 candidate：否。
13. 是否改 cron 时间表：否。
14. 是否需要 BOSS 明天观察：是，需先注入可用 API key 后再做 bounded live verify。
15. 如果 API timeout，dashboard 会如何显示：排除该 fixture 并给出 safe_na_reason / excluded reason，不伪造命中率。
