# Dashboard PWA 本地访问说明（Phase 2A）

本说明仅用于 **本地局域网只读访问** Dashboard，不涉及公网发布，不涉及 cron，不涉及 QQ 推送。

## 1. 生成 Dashboard 静态页面

先在项目根目录执行：

```bash
python3 tools/generate_mobile_dashboard.py --date YYYYMMDD
```

示例：

```bash
python3 tools/generate_mobile_dashboard.py --date 20260517
```

生成目录：

```text
data/runtime/dashboard/
```

关键文件：

- `index.html`
- `v2_today.html`
- `v4_scan.html`
- `v4_review.html`
- `system.html`
- `manifest.json`
- `service-worker.js`
- `assets/style.css`

## 2. 启动本地只读静态服务

执行：

```bash
python3 tools/serve_dashboard.py --host 0.0.0.0 --port 8765
```

默认值：

- host: `0.0.0.0`
- port: `8765`
- dir: `data/runtime/dashboard`

可指定目录：

```bash
python3 tools/serve_dashboard.py --host 0.0.0.0 --port 8765 --dir data/runtime/dashboard
```

## 3. iPhone 访问方式

1. 电脑与 iPhone 在同一局域网；
2. 查询电脑局域网 IP（例如 `192.168.1.20`）；
3. iPhone Safari 打开：

```text
http://电脑局域网IP:8765/index.html
```

示例：

```text
http://192.168.1.20:8765/index.html
```

## 4. 添加到主屏幕（PWA）

1. 在 iPhone Safari 打开 Dashboard；
2. 点击分享按钮；
3. 选择“添加到主屏幕”；
4. 主屏幕图标名称可用默认名称。

## 5. 当前能力边界（只读）

当前 Dashboard 仅做状态展示：

- 只读查看；
- 不触发 V2/V4 任务；
- 不调用外部 API；
- 不推送 QQ；
- 不包含重跑按钮；
- 不包含推送按钮；
- 不包含 kill/retry 按钮。

## 6. 安全注意事项

- **不要开放公网**；
- 仅用于内网/本机访问；
- 如需公网访问，必须后续单独设计认证、权限控制和安全隧道方案；
- 本阶段禁止直接公网裸奔。
