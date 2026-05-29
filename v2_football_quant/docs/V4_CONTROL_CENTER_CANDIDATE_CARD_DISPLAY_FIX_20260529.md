# V4 Control Center Candidate Card Display Fix — 2026-05-29

## 问题

V4 作战台候选卡片展示层存在 5 个脏字段问题：
1. 未投注候选默认预填金额 428、入场分钟 13、水位 0.86
2. 候选卡片显示 "候选剧本" 占位词
3. 缺失进球时间分布时显示假 0%
4. source_group 未在卡片上展示
5. 缺失字段渲染为 N/A

## 修复

### 1. Model Builder (`tools/build_v4_control_center_model.py`)
- `_get_default_bet_params`: 无实盘记录时返回 None（移除硬编码 428/13/0.86）
- candidate 构建：`default_stake`/`default_entry_minute`/`default_odds` 在未投注时为 None
- `script_type`/`script`: 缺失时设为 None 而非空字符串

### 2. Dashboard HTML (`data/runtime/dashboard/v4_control_center.html`)
- 候选卡片新增 `source_group` / `fixture_universe` 展示行
- `srcGroupDisplay()` 函数：WHITELIST_57 / OUTSIDE_57 / 来源未标记
- "候选剧本" → "正式候选"
- 时间分布：缺失时显示 "进球时间分布：暂无解释数据"，不显示假 0%
- 投注表单：未投注时金额/入场分钟/水位为空
- 开赛时间：缺失时显示 "开赛时间待定" 而非 N/A

### 3. Checker 更新
- `tools/check_v4_control_center.py`: 接受未投注候选 default 字段为 None
- `tools/check_v4_control_center_candidate_card_display.py`: 新增 226 行展示层检查

## 验证

- 全部 checker PASS（含 WARN_ONLY）
- A=1 / B=1 保持不变
- official grade 未重算
- DEFAULT_RULES 未改
- validation 未重算
- live bet 原始记录未修改
- QQ 未推送

## 变更文件

| 文件 | 操作 |
|------|------|
| `tools/build_v4_control_center_model.py` | 修改：去硬编码默认值 |
| `data/runtime/dashboard/v4_control_center.html` | 修改：修复 5 个展示问题 |
| `tools/check_v4_control_center.py` | 修改：接受 unbet 候选 null 字段 |
| `tools/check_v4_control_center_candidate_card_display.py` | 新增 |
| `docs/V4_CONTROL_CENTER_CANDIDATE_CARD_DISPLAY_FIX_20260529.md` | 新增 |
