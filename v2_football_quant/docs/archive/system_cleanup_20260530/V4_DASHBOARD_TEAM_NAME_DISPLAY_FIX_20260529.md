# V4 Dashboard Chinese Team Name Display Fix

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_TEAM_NAME_DISPLAY_FIX_PASS

## Root Cause

1. `team_cn_aliases.json` missing key team entries (Rosenborg, TransINVEST Vilnius, Hegelmann Litauen)
2. Model builder using raw English names from brief/scout without Chinese resolution
3. Dashboard CSS lacking proper word-wrap for Chinese text

## Fixes

### 1. Chinese Alias Configuration
Added 11 missing Chinese aliases to `data/config/team_cn_aliases.json`:
- Rosenborg → 罗森博格
- TransINVEST Vilnius → 特兰斯因维斯特
- Hegelmann Litauen → 赫格尔曼
- Plus 8 additional team aliases

### 2. Model Builder Name Resolution
Imported `TeamCnResolver` into `tools/build_v4_control_center_model.py`.
Added `_resolve_cn_name()` helper that resolves Chinese names during model building.

### 3. Dashboard CSS
- `.match-line`: added `white-space:normal`, `overflow-wrap:anywhere`, `word-break:break-word`
- `.candidate-card`: added `display:flex; flex-direction:column`

## Current Candidates

| Grade | Home | Away | League | Playbook |
|-------|------|------|--------|----------|
| A | 罗森博格 | 博德闪耀 | 挪超 | 尾段压迫 |
| B | 特兰斯因维斯特 | 赫格尔曼 | 立陶甲 | 中段发力 |
| B | 法赫-多瑙费尔德 | TWL 埃莱克特拉 | Regionalliga - Ost | 中段发力 |
| B | 梅尔布施 | 乌丁根05 | Oberliga - Niederrhein | 尾段压迫 |
| B | 圣加仑二队 | YF 尤文图斯 | 1. Liga Classic - Group 3 | 中段发力 |
