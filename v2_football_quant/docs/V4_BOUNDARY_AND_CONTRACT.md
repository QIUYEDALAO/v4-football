# V4 Boundary And Contract

## 1) V4 System Definition

- V4 = 上半场进球情报系统。
- 正式输出评级只允许：`A` / `B` / `C` / `SKIP`。
- `SKIP is not recommendation`.
- `C is not main recommendation`.
- 不允许出现 V33 口径进入正式结论。
- `no AI recalculation`：禁止 AI 自由重算评级。

## 2) V4 Input Boundary

允许输入：
- 情报输入（结构化 match intelligence）
- fixture 输入（赛程/开赛状态）
- odds / market 输入（盘口与赔率）
- manual note 输入（人工备注，需可追溯）

禁止输入：
- 来源不明、不可追溯的临时文本
- 未经 guard 的外部结论
- 任何 V33 口径污染

## 3) V4 Output Boundary

V4 正式输出形态：
- formal conclusion
- QQ brief
- full report
- daily report
- attribution report
- rolling validation

所有输出必须遵守：
- 仅 A/B/C/SKIP 正式评级
- SKIP 不得包装成推荐
- C 不得包装成主推

## 4) V4 Execution Boundary

V4 执行链路必须可审计并具备 marker：
- worker
- renderer
- guard
- watchdog
- route marker
- sent marker
- state marker

硬约束：
- `guard required before QQ`
- `watchdog required`
- `route/sent marker required`

## 5) V4 Prohibitions

- 不得把 WATCH / CANDIDATE 写成正式推荐。
- 不得把 SKIP 推成投注建议。
- 不得使用 V33 结论或口径。
- 不得跳过 guard 直接推 QQ。
- 不得无 marker 写日报。
- 不得无归因证据改规则。

## 6) Isolation Boundary

- V4 口径不得被 V2 / D8 / D9 / D10 污染。
- 本阶段仅做边界与合同锁定，不执行生产。
