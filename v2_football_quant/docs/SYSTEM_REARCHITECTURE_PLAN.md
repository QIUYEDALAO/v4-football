# SYSTEM_REARCHITECTURE_PLAN

## 定位
当前核心问题不是策略问题，而是**生产工程问题**：
- 事实源分散；
- 展示、证据、推送口径不一致；
- 缺少可回放与可审计闭环。

本方案仅做工程层重构，不改 V2/V3/V4 策略，不改 BET_LOCKED，不改 V4 A/B/C/SKIP。

---

## 总体分层
1. API Ingest Layer  
2. Raw Snapshot / Cache Layer  
3. Strategy Compute Layer  
4. Structured Result Layer  
5. Evidence / Guard / Marker Layer  
6. Daily Run Ledger  
7. Report Render Layer  
8. Dashboard Layer  
9. Notification Layer  
10. Replay / Backfill Layer

---

## 关键原则
1. `reading_status=PASS` 不等于 `production_verified=true`。  
2. `render_status=PASS` 不等于 `data_guard_status=PASS`。  
3. `WAITING_DUE_TIME` 不等于 `MISSING`。  
4. fallback/latest/qq_brief 只用于阅读，不得作为生产证据。  
5. `PRODUCTION_VERIFIED` 必须 guard + route + sent 三证齐全。  

---

## Phase A/B（本轮）
- Unified State Machine v1  
- Daily Run Ledger v1  
- Ledger Checker v1  
- Replay Day v1  
- Dashboard 首页最小接入 Ledger（优先读 ledger，缺失再回退）

---

## Phase C（建议，不在本轮执行）
API Snapshot / Cache 规范化：
- 把慢 API 影响从 cron 关键路径隔离到可重用快照层；
- 限制“实时链路直接依赖外部接口”比例。

---

## Phase D
Marker Schema 统一化：
- 统一 status/guard/review/scan marker 字段名；
- 统一 PASS/WARN/FAIL + WAITING_DUE_TIME 语义。

---

## Phase E
Replay/Backfill 扩展：
- 支持多日期、模块组合回放；
- 明确只读回放与生产链路隔离。

---

## Phase F
自然验证闭环：
- 以自然触发结果做证据收敛；
- 不用补跑替代生产证据。

---

## Dashboard产品化方向（修正版）
> 近期不做 internal/public 双看板拆分。  
> 主线改为“单套 Dashboard 产品化阅读层 + 单场比赛卡片”。

### 近期目标（Phase I）
1. 当前只保留一套 Dashboard。  
2. 默认展示产品化阅读内容。  
3. 证据/guard/marker/source_path 默认折叠。  
4. 不把证据字段平铺给用户。  
5. 不把 `reading_status=PASS` 当 `production_verified=true`。  
6. 未来收费方向以“单场比赛卡片/单场详情页”为核心。  
7. 单场卡片需支持：
   - 比赛双方；
   - 联赛；
   - 开赛时间；
   - V4评级；
   - HT评分；
   - HT率；
   - 上半场均球；
   - 剧本；
   - 时段分布；
   - 风险提示；
   - 赛后复盘入口。  
8. 当前不做支付、不做权限、不做公网发布。  
9. 当前只做架构预留和页面设计方向说明。  

---

## 本阶段边界
- 不改 V2/V3/V4 策略；
- 不改 A/B/C/SKIP；
- 不做收费功能；
- 不接入支付；
- 不开放公网；
- 不写 PRODUCTION_VERIFIED。

