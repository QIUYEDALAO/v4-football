# V4 Postmatch Script Validation Addon 20260523

## Conclusion

V4_POSTMATCH_SCRIPT_VALIDATION_ADDON_WARN_ONLY

## What Was Missing

赛后验证原来只覆盖 A/B 结果命中率，缺少对赛前候选卡片 `script_type` / 剧本字段的赛后走势验证。

## Added

- New schema: `data/runtime/status/v4_script_validation_schema_20260523.json`.
- New resolver: `tools/rebuild_v4_script_validation_from_match_date.py`.
- New summary: `data/runtime/status/v4_script_validation_summary_20260523.json`.
- Validation summary now contains separate `result_validation` and `script_validation` fields.
- Dashboard validation card now shows a compact `剧本验证` strip plus a `剧本验证审计` foldout.
- New checker: `tools/check_v4_postmatch_script_validation.py`.

## Script Validation Rules

- Supported frozen script families include: 中段发力型, 中后段发力型, 慢热绝杀型, 前压快开型, 开局冲击型, 后段冲击型.
- `SCRIPT_UNKNOWN` is excluded from the denominator.
- `SCRIPT_PARTIAL` is tracked separately and is not counted as HIT.
- C and SKIP are excluded.
- A+B equals A+B only, never C.
- Brief text is not used for script judgement.
- match_date is used; scan_date is not used.

## Current Script Validation

- yesterday A+B: `N/A`
- cumulative A: `22/39 · 56.4%`
- cumulative B: `47/85 · 55.3%`
- cumulative A+B: `69/124 · 55.6%`
- SCRIPT_UNKNOWN cumulative A+B: `19`
- denominator cumulative A+B: `124`

## Result Validation Preservation

- A result validation remains `39/46 · 84.8%`.
- B result validation remains `85/94 · 90.4%`.
- A+B result validation remains `124/140 · 88.6%`.
- Script validation did not change A/B hit rates.

## Safety

- full_scan_ran=false
- capture_ran=false
- QQ_push=false
- cloud_publish=false
- cron_enabled=false
- git_commit=false
- git_push=false
- V2 restored=false
- V33 active=false
- C validation visible=false
- C script validation visible=false
- last_7d_visible=false
- brief_used_for_script_validation=false
- scan_date_used_for_validation=false

## Verification

- script validation checker: `PASS`
- postmatch API route checker: `PASS`
- API preflight: `WARN_ONLY` / `API_KEY_MISSING`
- scout date integrity: `WARN_ONLY`
- match-date validation history recovery: `None`
- dashboard HTTP 127: `200`
- dashboard HTTP 192: `200`

## Answers

1. 原来缺少剧本验证。
2. 现在已新增剧本验证。
3. 数据源是正式 local attribution JSONL + repaired scout match_date，不使用 brief。
4. 使用 match_date=true。
5. 使用 brief=false。
6. 包含 C=false。
7. 包含 SKIP=false。
8. SCRIPT_UNKNOWN 进入分母=false。
9. 昨日剧本验证=N/A，无可信 match_date 事件样本。
10. 累计剧本验证 A+B=`69/124 · 55.6%`。
11. dashboard 已显示剧本验证=true。
12. 结果命中率被改=false。
13. 完整扫描运行=false。
14. capture=false。
15. QQ push=false。
16. cloud publish=false。
17. 可以回到 OpenClaw 总体验收=true。
