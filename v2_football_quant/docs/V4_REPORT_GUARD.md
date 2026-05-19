# V4 Report Guard

Phase: V4-G
Date: 2026-05-19
Status: FINAL

## 1. Full Report Guard

- Must use V4 reporting schema
- Must display guard_summary (schema_guard, qq_guard, renderer_guard)
- Must retain A/B/C/SKIP grading
- C must be observation-only, NOT primary
- SKIP must be NOT recommendation
- UNKNOWN/API_DISABLED must be excluded from hit/miss
- Must NOT write verified
- Must NOT change rules

## 2. QQ Brief Guard (iPhone Mobile)

- Must be iPhone-readable (no long tables)
- Each section under mobile reading burden
- Only core conclusions, counts, risks, guard status
- No full detailed table
- C must NOT be written as primary recommendation
- SKIP must NOT be written as recommendation
- Must NOT write "已发送" unless sent_marker exists
- Current templates (25-26 lines) already meet mobile readership

## 3. Weekly/Monthly Report Guard

- May show trends over time
- Must NOT auto-change rules based on single week/month
- Insufficient samples must be marked INSUFFICIENT
- Rule changes require separate BOSS approval

## 4. Prohibited Actions

| Action | Reason |
|--------|--------|
| C counted as primary recommendation | Misrepresentation |
| SKIP counted as recommendation | Scope breach |
| UNKNOWN counted as MISS | Data contamination |
| API_DISABLED counted as MISS | False negative |
| Report writes PRODUCTION_VERIFIED | Scope breach |
| Report triggers QQ push | Delivery breach |
| Report calls API | Security breach |
| Report modifies strategy | Algorithmic safety |
| Long table in QQ brief | Mobile unfriendly |
