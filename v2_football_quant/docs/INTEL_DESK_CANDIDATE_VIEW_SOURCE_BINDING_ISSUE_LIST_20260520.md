# Intel Desk Candidate View Source Binding — Issue List 20260520

**Phase:** INTEL-DESK-CANDIDATE-VIEW-SOURCE-BINDING-AND-MARKER-NORMALIZE-20260520

| # | Issue | Status |
|:--|:---|:---|
| 1 | 标准 status path 是否已补齐？ | PASS (already exists from MARKER-NORMALIZE phase) |
| 2 | legacy status path 是否存在？ | PASS |
| 3 | B/C 卡片是否硬编码在 HTML 而非从 JSON 生成？ | WARN — HTML cards manually written, not generated from candidate JSON |
| 4 | candidate view JSON 是否存在？ | PASS |
| 5 | dashboard 生成逻辑是否绑定 candidate model？ | FAIL — no generation script, no source_hash in HTML |
| 6 | checker 是否只检查 HTML 而未检查 source binding？ | WARN — existing checkers validate HTML content but not source provenance |
| 7 | midday/evening 更新后是否可能 stale？ | WARN — HTML is static, new window data won't auto-update |
| 8 | V4_QQ_ENABLED 是否仍 false？ | PASS |
| 9 | actual_send/qq_sent 是否仍 false？ | PASS |
| 10 | D13/V33/HOURLY 是否仍 false？ | PASS |

**Summary:** 5 PASS, 3 WARN, 1 FAIL, 0 BLOCKER
