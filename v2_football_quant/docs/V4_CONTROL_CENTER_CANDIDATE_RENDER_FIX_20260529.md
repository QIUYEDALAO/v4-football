# V4 作战台候选渲染修复

## 问题

bb1962e 引入的嵌套模板字面量导致 JS 语法错误，候选卡片不渲染、KPI 显示 A0/B0。

## 根因

`renderCandidate` 函数中的 `binText` 使用了三层嵌套模板字面量（template literal），Node.js/browser 解析器无法正确处理，抛出 `Unexpected token ';'` 语法错误。JavaScript 执行中断后，`loadModel()` 异常退出，DOM 保留初始占位值（A0/B0、正在读取候选数据…）。

## 修复

1. 将嵌套模板字面量替换为独立的 `buildScoreSummary(x)` 辅助函数
2. 辅助函数使用普通字符串拼接替代嵌套模板字面量
3. 保留所有显示逻辑（评分摘要、H2H样本、11-45压力、time_bins 等）
4. 保留安全 fallback：数据缺失显示"解释数据缺失，不影响 official grade"

## 禁止项确认

| 项目 | 状态 |
|------|------|
| DEFAULT_RULES 修改 | ❌ 未改 |
| A/B 阈值修改 | ❌ 未改 |
| Cron 修改 | ❌ 未改 |
| Validation 重算 | ❌ 未触发 |
| Live bet 修改 | ❌ 未改 |
| QQ 推送 | ❌ 未推送 |
| 重跑 scan | ❌ 未触发 |
| bb1962e 非 BLOCKER 改动回滚 | ❌ 未回滚 |
