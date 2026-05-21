# Intel Ops Console AB Collapsible Unified Card Layout — 问题清单

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-AB-COLLAPSIBLE-UNIFIED-CARD-LAYOUT-20260521
**来源**: BOSS iPhone 截图确认

---

## 问题总览

| # | 问题 | 严重级别 | 影响 |
|---|------|---------|------|
| 1 | B级剧本被右侧单列展示 | CRITICAL | bs-r3 使用 space-between，script在左 expand在右，视觉上剧本和展开形成双列 |
| 2 | B级展开按钮占右侧列 | CRITICAL | bs-expand 在 bs-r3 右侧，形成独立右列视觉效果 |
| 3 | B级卡片和A级卡片不一致 | HIGH | B用 b-summary-row 4-row结构，A用 candidate-card 结构，样式不统一 |
| 4 | B级队名容易被挤压 | MEDIUM | 虽然 bs-r2 独占一行，但 nowrap+ellipsis 可能在极小屏裁剪队名 |
| 5 | A/B组不能像C级一样整组折叠 | CRITICAL | A卡始终展开，B卡逐个折叠，没有整组折叠能力 |
| 6 | 首页候选区展开过多 | HIGH | A+B全部展开时占屏过多，周末赛事多时会爆屏 |
| 7 | 周末赛事多时会爆屏 | HIGH | 候选数增多时无整组折叠机制 |
| 8 | time_bins必须保留 | HIGH | 重构后必须确保 time_bins 不丢失 |
| 9 | C级必须继续仅观察 | HIGH | C级标注和内容不得改为推荐 |
| 10 | candidate数字不得变化 | HIGH | A=1 B=3 C=5 SKIP=0 必须保持不变 |
