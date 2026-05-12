# V4 仪表盘优化验收清单

> 更新日期：2026-05-12  
> 状态：执行中（已完成核心项）

## 1) 前台极简、后台复杂
- [x] 前台改为动作优先（非参数优先）
- 证据：
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_dashboard.py`
  - `actionCode / evLabel / executionLabel / riskLevel` 渲染路径

## 2) 三模式分层（作战/复盘/研究）
- [x] 临场作战模式（默认）
- [x] 复盘模式独立面板
- [x] 研究模式独立面板
- 证据：
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_dashboard.py`
  - `mode=ops/review/research` 分支

## 3) 临场首页只看关键数字与四分区
- [x] 监控/A+/A/等待/跳过 5 指标
- [x] 四分区：可进场/等待触发/风险观察/已跳过
- 证据：
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_dashboard.py`
  - `opsSummary`, `cardsBuy`, `cardsWait`, `cardsRisk`, `cardsSkip`

## 4) 单场卡片限制核心信息
- [x] 动作、等级、盘口、EV标签、执行标签、窗口、主因Top3、风险Top2
- [x] 复杂参数全部折叠进“查看完整数据”
- 证据：
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_dashboard.py`
  - `card(row)` 模板

## 5) 后端统一动作码（前端零推断）
- [x] `PAPER_BUY_NOW`
- [x] `WAIT_LINE`
- [x] `WAIT_TEMPO`
- [x] `WAIT_CONFIDENCE`
- [x] `PAPER_ONLY`
- [x] `SKIP`
- [x] `RISK_BLOCKED`（保留位）
- 证据：
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_match_intelligence.py`
  - `action_code` 字段及判定逻辑

## 6) 人话标签统一输出
- [x] `ev_label`（EV强/EV合格/EV观察）
- [x] `execution_label`（可成交/等待条件/仅观察/风控拦截）
- [x] `risk_level`（LOW/MID/HIGH）
- 证据：
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_match_intelligence.py`

## 7) 复盘模式关键信息
- [x] 动作分布 + EV标签分布
- [x] `legacy vs EV` 区块（接入复盘数据）
- [x] 跳过后影子表现区块（接入 shadow_summary）
- [x] EV-Legacy delta 颜色提示
- 证据：
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_dashboard.py`
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_review_report.py`

## 8) 复盘数据层补齐
- [x] `legacy_summary`
- [x] `shadow_summary`
- [x] markdown 同步输出
- 证据：
  - `/Users/liudehua/Desktop/v2_football_quant/engine/v4_review_report.py`
  - `/Users/liudehua/Desktop/v2_football_quant/data/daily_reports/v4_review_20260511.json`
  - `/Users/liudehua/Desktop/v2_football_quant/data/daily_reports/v4_review_20260511.md`

## 9) 当前生成物
- [x] 仪表盘已生成：
  - `/Users/liudehua/Desktop/v2_football_quant/docs/v4_dashboards/v4_dashboard_20260511.html`

## 10) 收尾建议（下一步）
- [x] 将 `RISK_BLOCKED` 接入真实 `risk_guard` 拦截结果（live动作 `SKIP_RISK_GUARD` -> 前台 `RISK_BLOCKED`）
- [x] 在复盘页加入 EV 分桶校准表（读取 `v4_calibration_report.json`）
- [x] 在研究模式增加 walk-forward 摘要卡（读取 `review.walk_forward` 输出）
