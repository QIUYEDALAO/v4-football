# V4 联赛白名单操作指南

版本：v1
日期：2026-05-30
作者：OpenClaw

---

## 1. 当前生产默认

V4 正式生产扫描 **只使用 57 联赛白名单**。

- 12:00 cron payload 不传 `--fixture-universe`
- 代码默认值：`--fixture-universe whitelist`
- 扫描引擎：`serial`（单线程，只扫白名单联赛）
- outside57 全量扫描已降级为历史能力，不作为生产默认

---

## 2. 如何新增一个联赛

### 2.1 确认联赛 ID

从 API-FOOTBALL 数据源获取联赛 `league_id`。

常用途径：
- API-FOOTBALL dashboard 查询
- 运行 `python3 tools/preview_all_eligible_leagues.py`（如果有）
- 从已有的 scout 数据中提取

### 2.2 修改白名单配置

编辑 `config/leagues_whitelist.json`，在 `leagueId` 对象中新增：

```json
{
  "leagueId": {
    ...
    "123": "新联赛中文名"
  }
}
```

### 2.3 可选：补 pyramid map 标签

`config/v4_league_pyramid_map.json` 用于联赛级别标签，不影响扫描准入。

如需补充：

```json
{
  "league_pyramid_map": {
    "123": "FIRST_TIER"
  }
}
```

可选值：`FIRST_TIER` / `SECOND_TIER` / `THIRD_TIER` / `CUP` 等。

### 2.4 可选：补中文队名

如新联赛球队无中文名映射，编辑 `data/config/team_cn_aliases.json`：

```json
{
  "exact": {
    "TeamName": "中文队名"
  }
}
```

---

## 3. 需要改哪些文件

| 文件 | 是否必须 | 说明 |
|------|---------|------|
| `config/leagues_whitelist.json` | ✅ 必须 | 联赛准入配置 |
| `config/v4_league_pyramid_map.json` | ⚠️ 建议 | 联赛级别标签 |
| `data/config/team_cn_aliases.json` | ⚠️ 建议 | 球队中文名映射 |

---

## 4. 新增联赛后必须跑的 checker

```bash
# 1. whitelist checker
python3 tools/check_v4_system_slim_and_whitelist_mode.py

# 2. DEFAULT_RULES guard
python3 tools/check_v4_production_default_rules_guard.py

# 3. dashboard checker
python3 tools/check_v4_control_center.py

# 4. no-market exclusion checker
python3 tools/check_v4_no_market_core_validation_skip.py

# 5. true goal distribution
python3 tools/check_v4_true_goal_time_distribution.py

# 6. playbook script
python3 tools/check_v4_playbook_script_and_time_distribution.py
```

所有 checker PASS 后，才能上线。

---

## 5. 新增联赛后是否需要改 cron

**不需要**。

12:00 cron 现在使用默认 `whitelist` fixture_universe。新增联赛只需改 `leagues_whitelist.json`，cron 不变。

---

## 6. 新增联赛后如何回滚

```bash
# 从白名单配置移除 league_id
git checkout -- config/leagues_whitelist.json

# 或手动编辑删除该联赛
```

---

## 7. 新增联赛后测试方法

```bash
# dry-run 一次，不推 QQ
cd /Users/liudehua/.openclaw/workspace/v2_football_quant
python3 engine/v4_scan_and_brief.py --date $(date +%Y%m%d) --no-push --preflight

# 确认 preflight OK 后，实际运行
python3 engine/v4_scan_and_brief.py --date $(date +%Y%m%d) --no-push

# 检查 candidate 输出
ls -la data/runtime/status/v3v4_dashboard_candidate_view_*.json

# 重启 dashboard
python3 tools/build_v4_control_center_model.py
```

---

## 8. pyramid map 当前角色

`config/v4_league_pyramid_map.json` 是联赛级别标签配置，**不是硬门槛**。

- 联赛准入取决于 `config/leagues_whitelist.json` 的 `leagueId` 集合
- pyramid map 仅用于评分阶段的联赛级别参考
- 即使 pyramid map 中没有该联赛，只要在白名单中就能被扫描

---

## 9. 注意事项

- 新增联赛不会影响现有验证历史
- 新增联赛不会影响 live bet 记录
- 新增联赛不会影响 DEFAULT_RULES
- 新增联赛不会影响 A/B 阈值
- 新增联赛不会自动推 QQ（QQ 推送被硬编码禁用）
