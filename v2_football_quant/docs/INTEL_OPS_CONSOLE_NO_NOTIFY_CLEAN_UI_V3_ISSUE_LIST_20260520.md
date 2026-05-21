# Intel Ops Console No-Notify Clean UI V3 — Screenshot Issue List

## Phase
INTEL-OPS-CONSOLE-NO-NOTIFY-CLEAN-UI-V3-20260520

## 10 Screenshot Problems

| # | Problem | Severity | Current State | Fix |
|---|---------|----------|---------------|-----|
| 1 | V4 QQ 残留 | HIGH | Top bar card "V4 QQ 关闭" visible | Remove from top bar, move to collapsed audit |
| 2 | QQ未发送 残留 | HIGH | A卡 card-status shows "QQ未发送" badge | Remove from card-status, clean detail panels |
| 3 | V4_QQ_ENABLED 残留 | HIGH | Zone 1 info-row "V4_QQ_ENABLED=false" visible | Remove from main view, keep only in audit |
| 4 | actual_send 残留 | HIGH | Zone 4 "actual_send=false" in main view | Move to collapsed audit details |
| 5 | 需BOSS批准 残留 | HIGH | Title subtitle + Zone 1 "等待BOSS批准" + A卡 card-status | Remove all from main page |
| 6 | 当前窗口重复 | MEDIUM | Top card "当前窗口:晚间" + decision-flag "窗口状态：晚间" + Zone 1 "当前窗口 evening" | Keep only top card + Zone 5 context |
| 7 | 阻断项占整行 | MEDIUM | Top grid 5th card uses grid-column:1/-1 spanning full width | 4-card 2x2 grid, blocker as normal card |
| 8 | 标题裁切 | MEDIUM | h1 has letter-spacing:-0.3px, subtitle has margin:-4px | Fix margins, ensure no negative values |
| 9 | 系统安全raw字段外露 | HIGH | Zone 4 shows V2 QQ/V4 QQ/D13/V33/HOURLY all in main view | Show only summary status, raw fields in collapsed audit |
| 10 | 决策感不足 | MEDIUM | Page reads like backend status page, not intelligence decision console | Remove backend raw fields, focus on match data |

## Prohibitions
All standard prohibitions apply: no capture, no QQ push, no V4_QQ_ENABLED, no D13/V33/HOURLY, no strategy changes, no number fabrication.
