# Intel Ops Console Readability Row Layout V2 — UI 问题清单

## Phase
INTEL-OPS-CONSOLE-READABILITY-ROW-LAYOUT-V2-20260520

## 10 UI 问题

| # | 问题 | 严重度 | 现象 |
|---|------|--------|------|
| 1 | body 字体过小 | HIGH | 15px 在 iPhone 上长时间阅读导致眼疲劳 |
| 2 | 队名字体过小 | HIGH | .cn 18px，在密集赛程中不够醒目 |
| 3 | 指标行过密 | MEDIUM | info-row padding 3px，行高不足，视觉拥挤 |
| 4 | B级候选标签单独占行 | HIGH | "B级候选" badge 在 ct 行独立显示，浪费纵向空间 |
| 5 | 详情按钮单独占行 | HIGH | `<details>` 在卡片底部独占一行，拉长页面 |
| 6 | B卡视觉间距不合理 | MEDIUM | margin 8px，gap 不足导致卡片粘连 |
| 7 | 手机端阅读疲劳 | HIGH | 整体字号偏小，行距不足，无护眼适配 |
| 8 | 折叠区点击区域偏小 | HIGH | summary 高度 ~20px，远低于 Apple HIG 44px 建议 |
| 9 | validation 区块文字偏密 | MEDIUM | 三窗口数据重复感强，raw details 默认展开 |
| 10 | 顶部状态卡不够醒目 | MEDIUM | topbar value 16px，label 9px，信息层级弱 |

## 修复方案概要

- 全局字体提升至 19px base，队名 23px
- B/A 卡重构为 4 行横向布局，时间|联赛|等级|详情 同在第一行
- tap target 最低 48px
- C 默认折叠，validation raw 默认折叠
- 顶部状态栏 2x5 网格，每卡 72px+
- 大字护眼模式默认开启
