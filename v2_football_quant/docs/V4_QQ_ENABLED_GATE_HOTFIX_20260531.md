# V4_QQ_ENABLED_GATE_HOTFIX (2026-05-31)

## 原因

`engine/v4_scan_and_brief.py` 中 `V4_QQ_ENABLED = False` 写死为硬编码 false，
导致即便所有 preflight / route dry-run 都 PASS，真实 QQ 推送仍被无条件阻断。

## 修复

将 `V4_QQ_ENABLED` 改为环境变量控制，新增 `_parse_bool_env()` 辅助函数。

## 默认值

未设置环境变量时，`V4_QQ_ENABLED` 仍为 `False`。

## 开闸方式

```bash
# 方式：一次性开闸，允许真实 QQ 推送
V4_QQ_ENABLED=1 python3 -u engine/v4_scan_and_brief.py --date 20260531 ... ...

# 支持的值（大小写不敏感）
V4_QQ_ENABLED=1
V4_QQ_ENABLED=true
V4_QQ_ENABLED=yes
V4_QQ_ENABLED=on
```

任何其他值（包括空、0、false、no、off、随机字符串）均视为 `False`。

## 最高优先级阻断

以下条件**无条件阻断**真实推 QQ，即使 `V4_QQ_ENABLED=1`：

1. `--no-push` 命令行参数
2. `OPENCLAW_NO_PUSH=1` 环境变量
3. duplicate sent marker 已存在（`v4_scan_{window}_sent_{date}.json` 已存在）

阻断链路优先级：`--no-push` ≈ `OPENCLAW_NO_PUSH` > duplicate marker > `V4_QQ_ENABLED`

## route decision 输出

push marker 中的 `qq_route_guard` 包含以下字段：

- `V4_QQ_ENABLED` — 解析后的环境变量值
- `effective_no_push` — `--no-push` 或 `OPENCLAW_NO_PUSH=1` 解析结果
- `args_push_effective` — 最终的 push 模式（never / conditional / always）
- `real_send_allowed` — 是否允许真实推送（所有门都开才为 true）
- `block_reason` — 阻断原因（`duplicate_sent_marker_exists` / `blocked_by_no_push_or_env_gate` / `no_ab` / `eligible`）

## 本轮不改动内容

- 不改评分
- 不改候选
- 不重扫
- 不调用 API
- 不改 cron
- 不改 validation
- 不改 live bet
- 不改 pending_bet_candidates

## 本轮 Codex 阶段

不真实推 QQ，不写 sent marker。

## OpenClaw 验收后

OpenClaw 验收通过后，可以在既有 brief / QQ route dry-run PASS 的基础上，
使用 `V4_QQ_ENABLED=1` 执行最终 QQ push completion。
