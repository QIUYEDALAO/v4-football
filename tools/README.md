# 捷报比分数据采集器

## 功能

自动采集捷报比分网站的比赛分析数据，包括：
- 历史交锋记录
- 半场比分
- 上半场进球率计算

## 安装依赖

```bash
cd /Users/chenguoqing/.openclaw/workspace/tools
npm install playwright
```

## 使用方法

### 方法1：直接运行

```bash
node jiebao-scraper.js
```

### 方法2：快捷命令

```bash
# 添加到 ~/.zshrc
alias jiebao='node /Users/chenguoqing/.openclaw/workspace/tools/jiebao-scraper.js'

# 然后直接运行
jiebao
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `/tmp/jiebao-analysis.json` | JSON格式，完整数据 |
| `/tmp/jiebao-analysis.txt` | 文本格式，用于发送给AI |

## 工作流程

1. 打开捷报比分网站
2. 提取未开赛比赛列表
3. 筛选主流联赛比赛
4. 逐个点击比赛，打开分析页面
5. 提取历史交锋数据
6. 计算上半场进球率
7. 保存结果

## 发送给AI分析

运行完成后，将 `/tmp/jiebao-analysis.txt` 的内容发送给AI：

```
请分析以下比赛数据：

[粘贴 /tmp/jiebao-analysis.txt 内容]
```

## 配置

编辑 `jiebao-scraper.js` 中的 `CONFIG` 对象：

```javascript
const CONFIG = {
  baseUrl: 'https://live.nowscore.com/2in1.aspx',
  outputFile: '/tmp/jiebao-analysis.txt',
  headless: false,  // true = 无界面模式
  timeout: 30000
};
```

## 注意事项

- 首次运行需要安装 playwright
- 浏览器会显示窗口，可以观察采集过程
- 采集速度约每场1-2秒
- 按回车键关闭浏览器
