# V4 Postmatch Review API Direct Header Fix Issue List 20260523

1. engine/v4_review_result_refresh.py 曾存在 RapidAPI header 残留，和 Direct endpoint 组合会导致鉴权失败。
2. x-rapidapi-key 不应请求 v3.football.api-sports.io。
3. V4 postmatch / attribution / review / validation 必须统一 API-SPORTS Direct。
4. review refresh active header 必须为 x-apisports-key。
5. review refresh 必须先执行 API preflight，safe_to_scan=false 时不得进入逐场 API。
6. subscription 403 必须 fail-fast，不能 retry。
7. curl fallback 不得处理 subscription 403。
8. postmatch validation 必须使用 match_date，禁止 scan_date。
9. brief 不得用于命中率。
10. 本轮只允许 route audit / dry-run，不运行完整扫描、不推送、不发布、不提交。

PASS: 问题清单完整；不再允许 x-rapidapi-key 作为 postmatch active header。
