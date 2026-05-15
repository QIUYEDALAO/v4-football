# OpenClaw Secrets Policy

> 建立时间：2026-05-15
> 原则：任何凭证不得写入文档、消息或代码

---

## 禁止写入以下位置

- MEMORY.md
- STATE_CURRENT.md
- QQ消息
- GitHub
- 日报 / 周报 / 月报
- OpenClaw 总结
- docs 文件
- 任何非脱敏文件

---

## 敏感内容列表

- API Key
- Bot Token
- AppSecret
- Gateway Token
- provider key
- webhook token
- QQ Bot secret
- auth profile secret

---

## 存储规则

- 所有凭证通过环境变量或 OpenClaw auth profile 读取
- 在任何文件/消息中只允许显示 `KEY=present`
- 不允许在 QQ、日报、周报中展示真实值

---

## 如果发现明文

1. 立即标记 BLOCKER
2. 不在 QQ 展示
3. 报告 BOSS
4. 等待是否 rotate key
