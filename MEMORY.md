# MEMORY.md — 长期记忆

## 💎 核心价值观

> **赔率涨跌不改变已成交的 PnL，只影响 CLV 的符号，而 CLV 的符号才是 Alpha 存在的证据。**

## ⚽ V2 量化系统（当前主力）

### 项目定位
- 数据源：API-Football Pro (Key: e5e315b1f9ba1ba51dc2124b35f07a01)
- 56个联赛白名单 | 14引擎模块 | 3026行 Python
- 核心KPI：ROI > 3% | CLV > 0 | 命中率 > 58%
- GitHub: git@github.com:whoerixxz/v2-football-quant.git

### 当前阶段：纸盘验证（5/6 - 5/12）
- 8:00 Cron `V2每日扫描` 自动扫描 → QQ Bot 推送
- 次日 paper_trading.py 自动结算
- 纸盘验收：7天 ≥25场 | CLV>0 | ROI≥3% | MDD≤12%
- 5/5 首场结算：Al Khaleej vs Al Hilal HT 1-1 ✅ | PnL +86.1u | CLV -8.43%
- 5/6 推荐2场：拜仁vs巴黎(HT Draw Edge+11.2%) + 阿联酋超(Edge+5%)

### 架构红线（信号与执行分离）
- 纸盘期：8:00 快照 → 假设瞬间成交 → 次日 CLV 结算
- 实盘期：daily_runner 降级为观察池 → odds_monitor 赛前30min轮询 → T-15min临场决策
- **绝不把 8:00 快照直接接下单 API**

### 代码冻结（2026-05-06 17:40）
- 6个致命 Bug 已修（Stake丢失/NoneType/Kelly摧毁/平局误杀/旧纸盘/收盘真空）
- 关键文件：bankroll.py（纯Kelly）、daily_runner.py（防崩溃）、paper_trading.py（V2 CLV）
- 银行：2000本金 | Kelly 1/6 | 单注上限300 | 低价值<10不投

### P0 剩余
- ❌ 评分引擎权重校准（H2H 20%→60%）
- ❌ 14联赛数据补拉

## 🔧 工程纪律
- 临近开赛/周末 → 代码静止
- 样本外积累优先 → 几十场后才 --summary
- 所有规则以代码为准，MEMORY 仅作记录

## 🏗️ 系统配置
- 模型：deepseek-v4-flash（默认）/ v4-pro（重型）
- 通道：QQ Bot (ON) | 微信 (已弃)
- 记忆：memory-core + memory-wiki（后台编译）
- 投注资金表：workspace/投注资金日报表.html
