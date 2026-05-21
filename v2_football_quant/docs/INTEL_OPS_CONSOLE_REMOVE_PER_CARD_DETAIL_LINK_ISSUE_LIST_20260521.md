# Intel Ops Console Remove Per-Card Detail Link — 问题清单

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-REMOVE-PER-CARD-DETAIL-LINK-20260521

---

## 问题列表

### RMD-001: 每场卡片技术详情入口仍占空间
- **严重度**: HIGH
- **描述**: card-r5 虽然在上一轮弱化为小字链接，但仍单独占一行，浪费卡片垂直空间。BOSS明确要求不要每场卡片单独放技术详情。

### RMD-002: 弱化按钮仍不符合 BOSS要求
- **严重度**: HIGH
- **描述**: 上一轮将按钮样式弱化为 `color:#6b7d8e; opacity:0.75` 小字链接，但入口仍存在，BOSS要求彻底删除。

### RMD-003: 技术信息不是主决策信息
- **严重度**: MEDIUM
- **描述**: 英文队名/source/hash/model tag 属于低频审计信息，不应在每场卡片中独立占位。

### RMD-004: 技术信息应统一折叠，不应逐场占位
- **严重度**: MEDIUM
- **描述**: 技术血缘信息应统一移动到 A/B候选组底部一个折叠区，默认关闭。

### RMD-005: 上轮 3 tasks 中仍有 1 in_progress，不能收 PASS
- **严重度**: CRITICAL
- **描述**: Task #153 (false pass issue list) 仍为 in_progress，在 todo 未清零前不得输出 PASS。
