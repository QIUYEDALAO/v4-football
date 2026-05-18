# V2 Window Worker Sandbox Observe (Phase D.8.10)

## 1. 定位

- D.8.10 仅执行 `sandbox worker observe`。
- 不是 supervisor live。
- 不是真实 window worker live。
- 不是生产恢复。

## 2. 固定边界

- 不执行 `engine/v2_window_checker_with_watchdog.py`
- 不写正式 `data/state/selected_fixtures_YYYYMMDD.json`
- 不推 QQ
- 不写 verified
- 不写 `PRODUCTION_VERIFIED`
- 不启用 cron
- 不调用 API / 不读取 key

## 3. 执行方法

- 只读读取正式 selected_fixtures。
- 复制到 `data/runtime/sandbox/v2_window_worker/YYYYMMDD_midday/`。
- monkeypatch worker 读写路径到 sandbox 副本。
- 在 sandbox 中执行 worker 核心逻辑并输出窗口结构化结果。

## 4. 审计字段

- `observe_scope=sandbox_worker_logic_only`
- `formal_state_written=false`
- `formal_state_unchanged=true`
- `live_window_worker_executed=false`
- `supervisor_executed=false`
- `qq_sent=false`
- `verified_written=false`
- `cron_modified=false`
- `api_called=false`
- `key_read=false`

## 5. 后续门禁

- D.8.10 通过后仅进入评审门禁，不自动进入 live。
- D.8.11 已建立 live worker safety wrapper（plan-only）。
- 若要真实 live worker observe，必须由 BOSS 单独下发 D.8.12 审批指令。
- Phase E 仍不得自动进入。
