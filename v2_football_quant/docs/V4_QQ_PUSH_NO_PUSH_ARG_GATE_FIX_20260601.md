# V4_QQ_PUSH_NO_PUSH_ARG_GATE_FIX_20260601

## 背景
Phase 3N 验收发现 QQ push 路由存在参数门控缺陷：
`engine/v4_scan_and_brief.py` 使用 `--no-push` 的 `store_true + default=True`，导致 CLI 无法显式关闭 no-push，`effective_no_push` 在常规用法下恒为 `True`。

## 本轮修复范围（最小变更）
仅修复参数门控，不改业务规则：
1. `engine/v4_scan_and_brief.py`
   - `--no-push` 改为 `argparse.BooleanOptionalAction`
   - 保持 `default=True`（默认仍是安全 no-push）
   - 支持显式关闭：`--no-no-push`
2. `tools/check_v4_qq_enabled_gate.py`
   - 新增检查：
     - `--no-push` 使用 `BooleanOptionalAction`
     - legacy `store_true + default=True` 旧写法已移除
     - `effective_no_push = args.no_push or env_no_push` 仍存在

## 验证
- `python3 -m py_compile engine/v4_scan_and_brief.py tools/check_v4_qq_enabled_gate.py` PASS
- `python3 tools/check_v4_qq_enabled_gate.py` PASS
- `python3 engine/v4_scan_and_brief.py --help` 已显示：
  - `--no-push | --no-no-push`

## 安全边界确认
本轮未执行/未改动：
- 未重扫
- 未调用 API
- 未推 QQ
- 未写 pending
- 未改 official 判级
- 未改 73.5 rescue 阈值
- 未改 DEFAULT_RULES
- 未改 A/B thresholds
- 未改 cron / validation / live bet

## 使用说明（Phase 3N 后续）
- 默认：`--no-push` 为 True（安全）
- 需要走 QQ push gate 检查时：显式加 `--no-no-push`
- 仍需满足：`V4_QQ_ENABLED=true` 且 `OPENCLAW_NO_PUSH!=1` 且 route 条件通过
