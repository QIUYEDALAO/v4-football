# V4 API Credential Preflight / 403 Circuit Breaker Issue List

1. HTTP 403 subscription 错误：You are not subscribed to this API。
2. API 订阅有效但当前 key/host/listing 组合被拒，不能直接判定订阅过期。
3. RapidAPI 与 API-SPORTS official direct 存在混用风险。
4. V4 scanner 历史上缺少 API credential preflight。
5. urllib 失败后 curl fallback 历史逻辑可能继续 403。
6. 403 subscription 被当成可重试错误会扩大请求量。
7. 800 次无效请求造成扫描耗时异常。
8. 需要 subscription 403 fail-fast / circuit breaker。
9. 需要 provider routing 矩阵锁定 host/header/key 来源。
10. 需要 no-secret logging，只输出 key fingerprint。

结论：403 subscription 不得作为可重试错误；必须先 preflight，失败即阻断远程扫描。
