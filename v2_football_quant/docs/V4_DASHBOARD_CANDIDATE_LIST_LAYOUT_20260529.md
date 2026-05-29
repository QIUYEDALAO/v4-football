# V4 Dashboard Candidate List Layout

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_CANDIDATE_LIST_LAYOUT_PASS

## Summary

Converted V4 dashboard candidate area from large card layout to a compact, time-sorted list layout optimized for all_eligible workflows with multiple candidates.

## Changes

### Layout
- Replaced `.candidate-card` with `.candidate-table` compact list
- Each row shows: time, grade dot, league, teams, playbook, goal distribution, status, expand button
- Sorted by kickoff time ascending (A before B at same time)

### Interaction
- Single-expand: only one candidate's bet form open at a time
- Click row to expand/collapse bet panel
- Bet panel contains: line, odds, stake, entry minute, save bet, skip (早进球未投), notes

### Mobile
- Responsive table with playbook/dist columns hidden on narrow screens
- Teams column width capped, essential fields always visible

## Current Candidates (5)
Sorted by kickoff time:
1. 05-30 00:00 [B] 法赫-多瑙费尔德 vs TWL 埃莱克特拉 · Regionalliga - Ost
2. 05-30 00:00 [B] 特兰斯因维斯特 vs 赫格尔曼 · 立陶甲
3. 05-30 01:00 [A] 罗森博格 vs 博德闪耀 · 挪超
4. 05-30 01:00 [B] 梅尔布施 vs 乌丁根05 · Oberliga - Niederrhein
5. 05-30 02:00 [B] 圣加仑二队 vs YF 尤文图斯 · 1. Liga Classic - Group 3
