# Intel Ops Console Detail Button De-emphasize — 问题清单

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-DETAIL-BUTTON-DEEMPHASIZE-20260521

---

## 问题列表

### DEEM-001: 单场"展开详情"按钮视觉权重过高
- **严重度**: HIGH
- **描述**: card-r5 中的 `<details><summary>展开详情 ▾</summary>` 使用了 `border:1px solid var(--border-subtle)` + `border-radius:5px` + `padding:4px 12px`，外观类似操作按钮，视觉权重高于技术信息应有的层级。
- **影响**: 干扰核心情报阅读（时间、联赛、等级、球队、HT、强度、预计球、剧本、time_bins）。

### DEEM-002: 详情按钮占用卡片底部整行空间
- **严重度**: MEDIUM
- **描述**: card-r5 单独占一行（`display:flex; justify-content:flex-end` from old CSS, now native details but still a separate visual row），浪费卡片垂直空间。

### DEEM-003: 技术详情不是主决策信息
- **严重度**: HIGH
- **描述**: 英文队名、source file、source hash、模型标签、血缘字段属于低频技术审计信息，不需要在每张卡片中以按钮形式突出展示。

### DEEM-004: A/B/C 组折叠已足够
- **严重度**: MEDIUM
- **描述**: 分组折叠（native details/summary）已经工作正常，单场卡片内部不需要额外的突出详情入口。技术详情入口应弱化为底部小字链接。

### DEEM-005: source/hash/英文队名应弱化展示
- **严重度**: MEDIUM
- **描述**: 当前 card-detail-inner 中的英文队名、source、hash 等信息虽然字体小（15px），但入口按钮（border + padding）过于显眼。

### DEEM-006: 不得影响 time_bins
- **严重度**: CRITICAL
- **描述**: time_bins（card-r4: 0-15m / 16-30m / 31-45m）是核心决策数据，任何改动不得影响其可见性。

### DEEM-007: 不得影响 A/B/C 分组折叠
- **严重度**: CRITICAL
- **描述**: 上一轮 CLICK-FIX 刚刚通过 native details/summary 修复了分组折叠，本轮改动不得破坏该功能。
