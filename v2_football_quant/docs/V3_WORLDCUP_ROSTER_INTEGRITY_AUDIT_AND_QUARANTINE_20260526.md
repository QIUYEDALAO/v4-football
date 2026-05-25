# V3 World Cup Roster Integrity Audit & Quarantine

**Audit Date:** 2026-05-25  
**Final Status:** V3_WORLDCUP_ROSTER_INTEGRITY_AUDIT_BLOCKED  
**Auditor:** ClawOps  

---

## 1. 当前是 46 队还是 48 队？

**46 队，非 48 队。**  
缺 2 个洲际附加赛胜出队。原导入脚本只列了 46 个直通名额，未包含附加赛路径。

## 2. 缺哪几队？

**2 个 inter-confederation playoff winners**。候选人包括：
- CONMEBOL: Paraguay 或 Peru  
- CONCACAF: Honduras 或 Trinidad  
- AFC: UAE 或 China  
- OFC: Solomon Islands 或 Tahiti  

确切队名需查世界杯正式资格赛结果。

## 3. team_id 是否全部正确？

**是。** 46 个 team_id 均正确（含 Türkiye/Turkey 名称差异已确认）。

## 4. players/squads 是否等于世界杯最终名单？

**否。** 
- API 端点 `players/squads` 返回的是**当前国家队征召名单**（API_CURRENT_SQUAD）
- 世界杯最终名单为 23~26 人，当前名单多队超 26 人（如智利 37 人）
- 未区分"预选名单"和"最终名单"

## 5. 哪些队是 official final squad？

**0 队。** 全部 46 队均为 API_CURRENT_SQUAD。无一队可确认为 OFFICIAL_FINAL_SQUAD。

## 6. 球员数据缺失比例？

| 字段 | 缺失率 |
|:--|:--|
| club（俱乐部） | **100%** |
| caps（国家队出场） | **100%** |
| goals（国家队进球） | **100%** |
| season_minutes（赛季时间） | **100%** |
| age | 部分缺失 |
| position | 基本完整 |

**100% 球员字段为空白 — 所有基于此数据的 roster_delta 和 PG 结论均无意义。**

## 7. 上一轮 PG_MEDIUM / WATCHLIST 可用吗？

**不可用。** 
- PG_MEDIUM（15 队）基于空白数据计算
- WATCHLIST（4 队）基于空白数据计算
- 已全部标记为 STALE / QUARANTINE
- `valid_for_v3_pg = false`

## 8. 已 stale / quarantine？

**是。** 见：
- `data/runtime/status/v3_worldcup_roster_baseline_stale_marker_20260526.json`

受影响文件：
- `team_profiles/roster_delta` → STALE
- `team_profiles/team_profiles` → STALE
- `market_baseline/...watchlist` → STALE
- HTML 页已添加红色警告横幅

## 9. 下一步如何补官方名单？

1. **等待世界杯官方大名单公布**（6 月初）
2. **使用 `players?team=X&season=2026`** 端点逐队获取详细球员数据（caps/goals/minutes/club）
3. **确认 2 个附加赛胜出队**并加入名单
4. **筛选每队至 23~26 人**最终名单
5. **标记 source_type=OFFICIAL_FINAL_SQUAD** 后才可用于 V3 PG 计算

## 10. 禁止项确认

| 检查项 | 状态 |
|:--|:--|
| V4 未改 | ✅ |
| V2 未改 | ✅ |
| V33 未启用 | ✅ |
| 无投注建议 | ✅ |
| V3 PG 未正式化 | ✅ |
| 无 QQ 推送 | ✅ |
| 无 cloud publish | ✅ |
| Cron 未改 | ✅ |
| 无 secret 打印 | ✅ |

---

**V3_WORLDCUP_ROSTER_INTEGRITY_AUDIT_BLOCKED**

*Block reason: team count (46≠48), source type (ALL API_CURRENT_SQUAD), field completeness (0%).*  
*All PG conclusions from baseline 20260526 are quarantined.*  
*Next phase: wait for official squad announcements, then re-import with validated data.*
