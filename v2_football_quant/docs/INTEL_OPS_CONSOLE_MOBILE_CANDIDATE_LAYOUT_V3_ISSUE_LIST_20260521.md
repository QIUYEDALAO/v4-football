# Intel Ops Console Mobile Candidate Layout V3 — 问题清单

**日期**: 2026-05-21
**阶段**: INTEL-OPS-CONSOLE-MOBILE-CANDIDATE-LAYOUT-V3-20260521
**来源**: BOSS iPhone 截图确认

---

## 问题总览

| # | 问题 | 严重级别 | 影响 |
|---|------|---------|------|
| 1 | B级候选横向挤压 | CRITICAL | 手机端 B 卡各元素横向争抢空间 |
| 2 | 队名被迫换行 | CRITICAL | "浙江队 vs 山东泰山"等队名折成两行 |
| 3 | 剧本和展开按钮占用队名空间 | HIGH | 剧本文字 + 展开按钮与队名同一行，挤占队名横向空间 |
| 4 | time_bins 需要保留 | HIGH | 现有 time_bins 位置可能被隐藏或不可见 |
| 5 | 展开按钮位置不合理 | MEDIUM | 展开按钮放在队名行导致可点击区域混乱 |
| 6 | 右下角眼睛按钮遮挡内容 | CRITICAL | position:fixed 悬浮按钮遮挡 B候选/V2验证/系统安全/下一动作 |
| 7 | 手机端候选卡需要三行摘要+一行 time_bins 结构 | HIGH | 当前四行结构 CSS 未强制防止换行/挤压 |
