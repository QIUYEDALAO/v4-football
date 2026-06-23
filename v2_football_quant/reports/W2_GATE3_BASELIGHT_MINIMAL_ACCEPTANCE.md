# W2 Gate 3 — Baselight 最小验收报告

**日期**: 2026-06-23 19:40 UTC

**BASELIGHT_STATUS**: `LICENSE_UNVERIFIED`

**状态说明**: License 未确认（非数据集本身问题，需后续对接方提供 metadata）

---

## 数据源说明

当前项目数据源为 **API-Sports** (v3.football.api-sports.io)，非 Baselight 原始数据集。
所有检查基于现有本地数据（312 个 odds JSON 文件 + SQLite DB）进行对标。

---

## 1. 经济报价键跨日期检查

报价键定义: fixture_id + bookmaker + market + selection + line

| 指标 | 数值 |
|---|---|
| 总报价条目 | 652,841 |
| 总报价键数 | 652,841 |
| 跨2+日期报价键 | 0 |
| 单日期报价键 | 652,841 |
| Exact duplicate 行 | 0 |
| distinct 收集日期 | ['2026-04-27', '2026-04-28', '2026-04-29', '2026-04-30', '2026-05-01', '2026-05-02', '2026-05-03', '2026-05-04'] |

**分析**: 基础数据为单次快照布局，跨日期报价键=0 是数据布局特征，非异常。

| 判定维度 | 结果 |
|---|---|
| 报价键可交叉引用 | ⚠️ 基础数据为单次快照布局 — 需 Baselight 时序数据方可验证变动 |
| 无重复键 | ✅ 零 exact duplicate |

---

## 2. Settlement 核对

使用 W2 现有 settlement 逻辑 (`asian_over_settlement.py` 的镜像实现) 与纯手工公式核对。
Settlement 自测试已通过。

| 分类 | 检查数 | 匹配 | 不匹配 |
|---|---|---|---|
| 整盘(整数盘) | 10 | 10 | 0 |
| 半盘(±0.5) | 10 | 10 | 0 |
| ±0.25 | 10 | 10 | 0 |
| ±0.75 | 10 | 10 | 0 |
| ±1.25 | 5 | 5 | 0 |

**结果**: ✅ ALL_MATCH | Settlement PASS

---

## 3. License / Provenance

**状态**: `LICENSE_UNVERIFIED`

**检查笔记**:
- DB schema (init_schema.sql): license_in_schema=False, provenance_in_schema=False
- Release manifest: settlement_version=V4_SETTLEMENT_AH_v1
- Release manifest has 'license' field: False
- Odds data annotation: [1531637, 1533674, 1540308, 1533675, 1533673, 1391603, 1403823, 1492615, 1492614, 1396507, 1391138, 1392162, 1387973, 1378199, 1530579, 1531636, 1540280, 1380354, 1536973, 1396513, 1396511, 1537093, 1
- Baselight metadata files: ['tools/run_w2_baselight_minimal_acceptance.py', 'reports/W2_GATE3_BASELIGHT_MINIMAL_ACCEPTANCE.json', 'reports/W2_GATE3_BASELIGHT_MINIMAL_ACCEPTANCE.md']

**建议**:

当前项目数据源为 API-Sports (api-sports.io)，非 Baselight 数据集。无明确的 dataset license / provenance / download_permission 元数据。
如需接入 Baselight 数据集，必须在 Baselight 官方页面或数据说明中确认：
  - 数据集使用许可（如 CC BY 4.0 / 商业许可）
  - 是否允许本地下载和长期保存
  - 是否允许内部回测用途
在取得上述确认之前，标记为 LICENSE_UNVERIFIED。

---

## 4. 最终判定

| 检查项 | 状态 | 说明 |
|---|---|---|
| 报价键跨日期 | ⚠️ N/A | 单次快照布局，需 Baselight 时序数据验证 |
| Settlement 一致 | ✅ PASS | 全部匹配 |
| License 确认 | ⚠️ LICENSE_UNVERIFIED | 未找到数据集 license metadata |

**BASELIGHT_STATUS**: `LICENSE_UNVERIFIED`

## 约束确认

- ✅ 未下载全量 5.22 亿行
- ✅ 未构建 adapter
- ✅ 未构建 walk-forward
- ✅ 未修改 Gate3 为 CLOSED
- ✅ 未修改 master roadmap
- ✅ 未修改 W1 或 Stage7I runtime

---
_报告由 W2_GATE3_BASELIGHT_MINIMAL_ACCEPTANCE 自动生成于 2026-06-23 19:40 UTC_
