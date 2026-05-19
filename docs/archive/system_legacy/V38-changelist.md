> **DEPRECATED** — NOT_PRODUCTION — DO_NOT_EXECUTE — HISTORICAL_REFERENCE_ONLY
> Archived by Phase SYSTEM-LEGACY-0.
> This file is kept for historical reference only and must not be used as
> formal V4 entrypoint, configuration, or production reference.

# V38 改造清单（一次性执行）

**日期：** 2026-05-04
**目标：** 将所有确认要改的优化一次性写入代码，不拖三周。

---

## 说明

以下清单结合了3位专家的意见和最终决策。所有改动一次性完成，不做分阶段。

## 六、不做的

| 原建议 | 理由 |
|--------|------|
| 天气/温度 | 零API约束，影响非线性 |
| FIFA排名/ELO | 改用「夺冠赔率倒数」替代 |
| 新闻发布会爬虫 | 规则化替代（小组赛第三轮直接降级） |
| 进球类型标记 | 捷报页面不直接显示，无法提取 |
| Kelly公式定注码 | 等200场数据后再决定，现在没有参数 |
| 联赛Modifier加权 | 改为联赛黑名单，跑200场后拉黑负收益联赛 |
| 半场盘口/全场盘口比值 | 不同维度（大小球 vs 让球），不可比 |

---

## 七、改动清单（文件级）

| 文件 | 改动 | 说明 |
|------|------|------|
| `batch-worker-v38.js` | 共振系数+全场让球绝对值+水位+裁判+AH数据 | 核心文件 |
| `extractCrownOdds()` | 重写：一次提取半场大小球+全场让球+胜平负+水位 | 不再只取大小球 |
| `extractH2H()` | 增加recentTwo字段（近2次交锋进球情况） | 10行 |
| `smartRecommend()` | 80-89%共振系数+全场让球绝对值判断+近2次利用 | 40行 |
| `buyTiming()` | 水位判断（真降盘/假降盘）+0.75陷阱 | 20行 |
| `extractRecent()` | 增加返回quantified form数据（积分、进球、失球） | 15行 |
| `extractReferee()` | 新增函数，找不到不报错 | 15行 |
| `verify-v38.js` | 增加回测逻辑（不新建文件）+ 让球盘验证记录 | 30行 |
| `v38-config.js` | 无需改 | 0行 |

**预计总增量：约+130行，从1213行→约1343行**
