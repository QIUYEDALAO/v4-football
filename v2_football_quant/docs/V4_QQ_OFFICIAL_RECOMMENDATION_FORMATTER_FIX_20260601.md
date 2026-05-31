# V4 QQ Official Recommendation Formatter Fix (2026-06-01)

## 背景
Phase 3N-RETRY 已验证 QQ push gate 路径可达，但发现 `engine/v4_qq_formatter.py` 仍使用测试模板文案，导致正式候选可能被包装为“模板验收TEST/非正式推荐”。

## 问题
原 `format_qq()` 输出包含：
- `【V4模板验收TEST｜非正式推荐】`
- `说明：模板实机验收，不代表今日正式推荐，请勿下注。`
- `—— V4模板验收TEST结束 ——`

这与 Phase 3N 的“正式推荐口径”冲突，属于正式推送 blocker。

## 本轮修复
1. 将 QQ formatter 分离为两种模式：
- `official_recommendation`：正式推荐模板（默认）
- `template_test`：模板验收测试模板

2. 正式推荐模板输出不再包含以下测试污染文案：
- 模板验收TEST
- 非正式推荐
- 不代表今日正式推荐
- 请勿下注
- 模板验收TEST结束

3. 生产调用路径切换到正式模式：
- `engine/v4_scan_and_brief.py` 生成 QQ brief 时显式传入
  `mode="official_recommendation"`

4. 保留测试模板能力：
- test/template-acceptance 场景仍可显式 `mode="template_test"`

5. 新增检查器：
- `tools/check_v4_qq_official_formatter.py`
- 检查 official 模式无 TEST 污染、含 A/B 正式字段与 B=2 比赛项、test 模式仍可输出 TEST 文案

## 本轮未做事项（安全边界）
- 未真实推 QQ
- 未写 sent marker
- 未写 pending
- 未重扫
- 未调用外部 API
- 未改 73.5 阈值
- 未改 DEFAULT_RULES
- 未改官方 A/B thresholds
- 未改 official 判级逻辑

## 下一步
由 OpenClaw 在 QQ-routed session 做只读验收后，再进入 Phase 3N-RETRY-2 的真实推送闭环执行。
