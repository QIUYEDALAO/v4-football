# V4 Control Center Candidate Render Binding Fix — 2026-05-29

## 问题

f55da9c 恢复作战台 UI 后，候选卡片不渲染。KPI 正确显示 A1/B1/SKIP240，但候选行动区卡在 "正在读取今日候选..."。

## 断点

`renderCandidate()` 函数中使用了 `${script}` 模板变量，但该变量未定义。JavaScript ReferenceError 导致 `.map(renderCandidate)` 中断，`renderCandidates()` 无法替换 loading 占位符。

**根因**：`const script = safe(...)` 行在上轮修复中被移除，但模板字面量中的 `${script}` 引用未同步删除。

## 修复

`data/runtime/dashboard/v4_control_center.html`：

```javascript
// 在 renderCandidate 中添加：
const script = safe(first(x.script, x.script_type, x.playbook), "正式候选");
```

## 验证

- 全部 checker PASS
- HTML template vars 全部绑定
- A=1 B=1 候选正确存在
- Rosenborg A / TransINVEST B 均可渲染
- 未投注金额/分钟/水位为空
- DEFAULT_RULES 未改
- validation 未重算
- live bet 未改
- QQ 未推送
