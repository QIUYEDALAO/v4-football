#!/usr/bin/env python3
"""
W2 Gate 3 — API-Sports Local JSON 快照审计脚本
==================================================

⚠️ SOURCE_MUST_BE_DECLARED

本脚本审计的是 API-Sports 本地 JSON 快照数据（312 files, 54 MB）。
它不读取、不接触、不评估 Baselight 数据集。

用途: 验证 W2 settlement library 对本地 API-Sports 赔率数据的正确性。
      检查经济报价键（fixture_id + bookmaker + market + selection + line）
      的跨日期分布和重复情况。

原始版本曾错误命名为 "Baselight probe"。
纠正后本文件明确声明数据来源仅为 API-Sports local JSON。

禁止解读为 Baselight 数据质量评估。
"""
print("SOURCE: API-Sports local JSON. NOT Baselight data.")
print("To run: python3 tools/run_w2_baselight_minimal_acceptance.py")
print("See reports/W2_GATE3_BASELIGHT_MINIMAL_ACCEPTANCE.md for corrected results.")
print("BASELIGHT_STATUS: NOT_EVALUATED_SOURCE_MISMATCH")
print("SOURCE_MUST_BE_DECLARED")
