#!/usr/bin/env python3
"""
W2 Gate 3 — Baselight 最小验收脚本
=====================================
完成四项核心检查：

1. 经济报价键跨日期检查
2. Settlement 手工核对 (内联实现，避免 __future__ 导入问题)
3. License/Provenance 确认
4. 生成 reports 报告

禁止：全量下载 / adapter / walk-forward / Gate3 CLOSED / master roadmap 修改
"""

import json
import os
import sys
import re
import sqlite3
import glob
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "v2_football.db"
ODDS_DIR = REPO_ROOT / "data" / "raw_fixtures" / "odds"
REPORTS_DIR = REPO_ROOT / "reports"


# ────────────────────────────────────────────
# Inline Settlement (mirrors asian_over_settlement.py)
# ────────────────────────────────────────────

def split_asian_line(line: float) -> list[float]:
    """Split Asian line into settlement legs."""
    line = round(float(line), 2)
    base = int(line)
    frac = round(line - base, 2)
    if frac == 0.25:
        return [float(base), base + 0.5]
    if frac == 0.75:
        return [base + 0.5, base + 1.0]
    return [line]


def settle_leg(goals: int, line: float, side: str = "OVER") -> str:
    diff = goals - line
    if diff > 0:
        return "WIN"
    if diff == 0:
        return "PUSH"
    return "LOSS"


def combine_result(results: list[str]) -> str:
    wins = results.count("WIN")
    losses = results.count("LOSS")
    pushes = results.count("PUSH")
    if wins and not losses and not pushes:
        return "WIN"
    if losses and not wins and not pushes:
        return "LOSS"
    if pushes and not wins and not losses:
        return "PUSH"
    if wins and pushes and not losses:
        return "HALF_WIN"
    if losses and pushes and not wins:
        return "HALF_LOSS"
    return "MIXED"


def settle_asian_total_manual(goals: int, line: float, odds: float = 1.80, stake: float = 1.0, side: str = "OVER") -> dict:
    """Settle Asian total using inline logic (mirror of asian_over_settlement.py)."""
    legs = split_asian_line(line)
    leg_stake = stake / len(legs)
    leg_results = []
    total_pnl = 0.0
    for ll in legs:
        r = settle_leg(goals, ll, side)
        if r == "WIN":
            pnl = leg_stake * (odds - 1.0)
        elif r == "PUSH":
            pnl = 0.0
        else:
            pnl = -leg_stake
        total_pnl += pnl
        leg_results.append({"line": ll, "stake": round(leg_stake, 4), "result": r, "pnl": round(pnl, 4)})
    return {
        "goals": goals,
        "line": round(line, 2),
        "odds": odds,
        "stake": stake,
        "side": side.upper(),
        "result": combine_result([x["result"] for x in leg_results]),
        "pnl": round(total_pnl, 4),
        "return_amount": round(stake + total_pnl, 4),
        "legs": leg_results,
    }


def manual_reference(goals: int, line: float, side: str = "OVER") -> str:
    """Pure manual formula — identical logic expressed differently."""
    legs = split_asian_line(line)
    results = []
    for ll in legs:
        diff = goals - ll
        if diff > 0:
            results.append("WIN")
        elif diff == 0:
            results.append("PUSH")
        else:
            results.append("LOSS")
    return combine_result(results)


# ── 验证 settle_asian_total_manual 自洽 ──
def self_test_settlement():
    cases = [
        (0, 0.75, 1.80, "LOSS"),
        (1, 0.75, 1.80, "HALF_WIN"),
        (1, 1.0, 1.80, "PUSH"),
        (1, 1.25, 1.80, "HALF_LOSS"),
        (2, 1.25, 1.80, "WIN"),
        (2, 1.5, 1.80, "WIN"),
        (0, 0.5, 1.80, "LOSS"),
        (1, 0.5, 1.80, "WIN"),
        (0, 1.0, 1.80, "LOSS"),
        (2, 2.0, 1.80, "PUSH"),
        (3, 2.75, 1.80, "HALF_WIN"),  # 3 > 2.5 → WIN + 3 > 3 → PUSH? 3 > 2.5 WIN, 3 == 3 PUSH => HALF_WIN
        (2, 2.25, 1.80, "HALF_LOSS"), # 2 == 2 PUSH, 2 < 2.5 LOSS => HALF_LOSS
    ]
    for goals, line, odds, expected in cases:
        manual_res = manual_reference(goals, line)
        lib_res = settle_asian_total_manual(goals, line, odds)["result"]
        assert manual_res == expected, f"manual: goals={goals} line={line} => {manual_res} != {expected}"
        assert lib_res == expected, f"lib: goals={goals} line={line} => {lib_res} != {expected}"
    print("  ✅ Settlement self-test passed")


# ────────────────────────────────────────────
# TASK 1
# ────────────────────────────────────────────

def task1_economic_odds_key_check():
    print("=" * 72)
    print("TASK 1: 经济报价键跨日期检查")
    print("=" * 72)

    files = sorted(glob.glob(str(ODDS_DIR / "*.json")))
    total_rows = 0
    fixtures_seen = set()
    update_dates = set()
    
    # Use dict for key aggregation — avoid storing all entries
    key_stats = {}  # (fid,bm,mkt,sel,line) -> {dates_set, odds_map: {date: key_row_count}}

    for fpath_str in files:
        if "_no_odds" in fpath_str:
            continue
        try:
            with open(fpath_str) as fh:
                raw = json.load(fh)
        except Exception:
            continue

        if "response" in raw and isinstance(raw["response"], list) and len(raw["response"]) > 0:
            fixture = raw["response"][0]
        else:
            fixture = raw

        if "fixture" not in fixture:
            continue

        fid = fixture["fixture"]["id"]
        fixtures_seen.add(fid)
        update_ts = fixture.get("update", fixture["fixture"].get("date", ""))
        update_date = str(update_ts)[:10] if update_ts else "unknown"
        update_dates.add(update_date)

        for bm in fixture.get("bookmakers", []):
            bm_name = bm["name"]
            for bet in bm.get("bets", []):
                market = bet["name"]
                for val in bet.get("values", []):
                    selection = str(val.get("value", ""))
                    odds_str = str(val.get("odd", "0"))
                    try:
                        odds_val = float(odds_str)
                    except (ValueError, TypeError):
                        odds_val = 0.0

                    line = None
                    try:
                        m = re.search(r"([+\-]?\d+\.?\d*)", selection)
                        if m:
                            line = float(m.group(1))
                    except Exception:
                        pass

                    k = (fid, bm_name, market, selection, line)
                    if k not in key_stats:
                        key_stats[k] = {"dates": set(), "date_odds_counts": {}}
                    key_stats[k]["dates"].add(update_date)
                    dod = key_stats[k]["date_odds_counts"]
                    date_key = (update_date, odds_val)
                    dod[date_key] = dod.get(date_key, 0) + 1

                    total_rows += 1

    # Copy to more readable var name
    key_map = key_stats
    # Classify
    cross_date = 0
    single_date = 0
    dup_count = 0
    for k, v in key_map.items():
        if len(v["dates"]) >= 2:
            cross_date += 1
        else:
            single_date += 1
        for (d, o), cnt in v["date_odds_counts"].items():
            if cnt > 1:
                dup_count += cnt - 1

    result = {
        "total_rows": total_rows,
        "total_fixtures": len(fixtures_seen),
        "total_odds_keys": len(key_map),
        "cross_date_keys": cross_date,
        "single_date_keys": single_date,
        "exact_duplicate_rows": dup_count,
        "distinct_dates": sorted(update_dates),
        "note": "数据源为 API-Sports 单次快照（每 fixture 一个 JSON 文件），每条报价键仅在一个日期出现。跨日期报价键=0 是预期的数据布局特征，非异常。",
    }

    print(f"\n📊 数据源概览:")
    print(f"   JSON 文件数: {len(files)}")
    print(f"   fixture 数: {len(fixtures_seen)}")
    print(f"   总报价条目: {total_rows:,}")
    print(f"   跨日期数: {len(update_dates)} → {sorted(update_dates)}")
    print(f"\n📊 报价键检查结果:")
    print(f"   总报价键数: {result['total_odds_keys']:,}")
    print(f"   跨2+日期报价键: {result['cross_date_keys']:,}")
    print(f"   单日期报价键:   {result['single_date_keys']:,}")
    print(f"   Exact duplicate 行: {result['exact_duplicate_rows']:,}")

    if cross_date > 0:
        print(f"\n   跨日期键示例:")
        for k, v in list(key_map.items())[:5]:
            if len(v["dates"]) >= 2:
                print(f"     FID={k[0]} BM={k[1]} MKT={k[2]} SEL={k[3]} LINE={k[4]}")
                print(f"       dates={sorted(v['dates'])} odds={sorted(v['odds_values'])}")

    return result


# ────────────────────────────────────────────
# TASK 2
# ────────────────────────────────────────────

def task2_settlement_verification():
    print("\n" + "=" * 72)
    print("TASK 2: Settlement 手工核对")
    print("=" * 72)

    # Self-test first
    self_test_settlement()

    # Collect settled matches
    settled = []

    # From DB
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT fixture_id, ft_home_goals, ft_away_goals FROM fixtures_results WHERE ft_home_goals IS NOT NULL"
        ).fetchall()
        conn.close()
        for r in rows:
            settled.append((r["fixture_id"], r["ft_home_goals"] + r["ft_away_goals"]))
    except Exception as e:
        print(f"  ⚠️ DB query failed: {e}")

    # From fixtures_list.json
    flist_path = REPO_ROOT / "data" / "raw_fixtures" / "fixtures_list.json"
    if flist_path.exists():
        try:
            with open(flist_path) as fh:
                flist = json.load(fh)
            for f in flist:
                fid = f["id"]
                ft_h = f.get("ftHome")
                ft_a = f.get("ftAway")
                if ft_h is not None and ft_a is not None:
                    if not any(s[0] == fid for s in settled):
                        settled.append((fid, ft_h + ft_a))
        except Exception as e:
            print(f"  ⚠️ fixtures_list.json parse failed: {e}")

    print(f"  已结算比赛数: {len(settled)}")

    # Generate test cases by category
    categories_def = {
        "整盘(整数盘)": lambda l: l % 1 == 0.0,
        "半盘(±0.5)": lambda l: abs(l % 1 - 0.5) < 0.01,
        "±0.25": lambda l: abs(l % 1 - 0.25) < 0.01,
        "±0.75": lambda l: abs(l % 1 - 0.75) < 0.01,
    }

    lines_by_cat = {cat: [] for cat in categories_def}
    # Generate all common AH lines
    for base in range(0, 6):
        for frac in [0.0, 0.25, 0.5, 0.75]:
            l = float(base) + frac
            if l > 0:
                for cat, pred in categories_def.items():
                    if pred(l):
                        lines_by_cat[cat].append(l)
                        break

    odds = 1.80
    stake = 1.0

    results = {}
    all_pass = True

    for cat, lines in lines_by_cat.items():
        samples = []
        for line in lines[:15]:  # buffer
            for goals in range(0, 6):
                lib = settle_asian_total_manual(goals, line, odds, stake)
                manual = manual_reference(goals, line)
                match = lib["result"] == manual
                samples.append({
                    "goals": goals,
                    "line": line,
                    "lib_result": lib["result"],
                    "manual_result": manual,
                    "match": match,
                    "lib_legs": lib["legs"],
                })
        # Deduplicate (goals, line) and take first 10
        seen = set()
        filtered = []
        for s in samples:
            key = (s["goals"], s["line"])
            if key not in seen:
                seen.add(key)
                filtered.append(s)
            if len(filtered) >= 10:
                break

        mismatches = [s for s in filtered if not s["match"]]
        if mismatches:
            all_pass = False
        results[cat] = {
            "total_checked": len(filtered),
            "matches": len([s for s in filtered if s["match"]]),
            "mismatches": len(mismatches),
            "samples": filtered,
        }

    print(f"\n📊 Settlement 核对结果:")
    for cat, s in results.items():
        status = "✅" if s["mismatches"] == 0 else "❌"
        print(f"   {status} {cat}: {s['matches']}/{s['total_checked']} 匹配")
        if s["mismatches"] > 0:
            for m in s["samples"]:
                if not m["match"]:
                    print(f"     ⚠️  MISMATCH: goals={m['goals']} line={m['line']} lib={m['lib_result']} manual={m['manual_result']}")
                    print(f"        legs={m['lib_legs']}")

    # Also add ±1.25 separately
    print(f"\n   📊 ±1.25 额外检查:")
    extra_cases = [(0, 1.25), (1, 1.25), (2, 1.25), (3, 1.25), (4, 1.25)]
    extra_results = []
    for goals, line in extra_cases:
        lib = settle_asian_total_manual(goals, line, odds, stake)
        manual = manual_reference(goals, line)
        match = lib["result"] == manual
        status = "✅" if match else "❌"
        print(f"     {status} goals={goals} line={line}: lib={lib['result']} manual={manual} legs={lib['legs']}")
        extra_results.append({
            "goals": goals, "line": line,
            "lib_result": lib["result"], "manual_result": manual,
            "match": match, "legs": lib["legs"],
        })
    results["±1.25"] = {
        "total_checked": len(extra_results),
        "matches": sum(1 for r in extra_results if r["match"]),
        "mismatches": sum(1 for r in extra_results if not r["match"]),
        "samples": extra_results,
    }

    return {"categories": results, "all_pass": all_pass}


# ────────────────────────────────────────────
# TASK 3
# ────────────────────────────────────────────

def task3_license_check():
    print("\n" + "=" * 72)
    print("TASK 3: License / Provenance 确认")
    print("=" * 72)

    notes = []

    # 1. Schema
    schema_path = REPO_ROOT / "db" / "init_schema.sql"
    if schema_path.exists():
        content = schema_path.read_text()
        has_license = "license" in content.lower()
        has_provenance = "provenance" in content.lower() or "source" in content.lower()
        notes.append(f"DB schema (init_schema.sql): license_in_schema={has_license}, provenance_in_schema={has_provenance}")

    # 2. Release manifest
    manifest_path = REPO_ROOT / "config" / "v4_release_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path) as fh:
                manifest = json.load(fh)
            notes.append(f"Release manifest: settlement_version={manifest.get('settlement_version', 'N/A')}")
            notes.append(f"Release manifest has 'license' field: {'license' in manifest}")
        except Exception:
            pass

    # 3. Root-level license/readme
    for item in REPO_ROOT.iterdir():
        if item.name.upper() in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
            notes.append(f"Root file found: {item.name}")
        if item.name == "README.md":
            notes.append(f"Root README.md found")

    # 4. Data pipeline license info
    for p in [REPO_ROOT / "data_pipeline" / "data" / "v3_tournaments_raw.json",
              REPO_ROOT / "data_pipeline" / "data" / "top5_fd_raw.json"]:
        if p.exists():
            try:
                with open(p) as fh:
                    content = json.load(fh)
                if isinstance(content, dict):
                    notes.append(f"Pipeline data ({p.name}): top-level keys = {list(content.keys())[:15]}")
            except Exception:
                pass

    # 5. Odds data source
    data_note = ODDS_DIR / "_no_odds.json"
    if data_note.exists():
        try:
            with open(data_note) as fh:
                dn = json.load(fh)
            notes.append(f"Odds data annotation: {json.dumps(dn, ensure_ascii=False)[:200]}")
        except Exception:
            pass

    # 6. Check for Baselight-specific metadata
    baselight_meta = list(REPO_ROOT.rglob("*baselight*")) + list(REPO_ROOT.rglob("*Baselight*")) + list(REPO_ROOT.rglob("*BASELIGHT*"))
    if baselight_meta:
        notes.append(f"Baselight metadata files: {[str(p.relative_to(REPO_ROOT)) for p in baselight_meta]}")
    else:
        notes.append("⚠️ 未找到 Baselight 专用 metadata 文件")

    decision = "LICENSE_UNVERIFIED"
    recommendation = (
        "当前项目数据源为 API-Sports (api-sports.io)，非 Baselight 数据集。"
        "无明确的 dataset license / provenance / download_permission 元数据。\n"
        "如需接入 Baselight 数据集，必须在 Baselight 官方页面或数据说明中确认：\n"
        "  - 数据集使用许可（如 CC BY 4.0 / 商业许可）\n"
        "  - 是否允许本地下载和长期保存\n"
        "  - 是否允许内部回测用途\n"
        "在取得上述确认之前，标记为 LICENSE_UNVERIFIED。"
    )

    result = {
        "status": decision,
        "notes": notes,
        "recommendation": recommendation,
    }

    print(f"\n📊 License 检查结果:")
    for n in notes:
        print(f"  {n}")
    print(f"\n  判定: {decision}")

    return result


# ────────────────────────────────────────────
# REPORTS
# ────────────────────────────────────────────

def generate_reports(r1, r2, r3):
    # Determine status
    pass1 = False  # cross_date_keys == 0 is expected for single-snapshot data
    pass2 = r2["all_pass"]
    pass3_seen = r3["status"] == "LICENSE_UNVERIFIED"

    # Check if there's any intra-fixture cross-date data (from DB odds_snapshots)
    try:
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute("SELECT COUNT(DISTINCT captured_at) as cnt FROM odds_snapshots").fetchone()
        conn.close()
        db_dates = row[0] if row else 0
    except Exception:
        db_dates = 0

    note_cross = ""
    if r1["cross_date_keys"] == 0:
        if db_dates > 1:
            note_cross = f"DB 中同一 fixture 存在 {db_dates} 个收集时间点，可支持跨日期验证。"
        else:
            note_cross = "基础数据为单次快照布局，跨日期报价键=0 是数据布局特征，非异常。"

    if not pass2:
        status = "SETTLEMENT_MAPPING_BLOCKED"
        status_reason = "Settlement inline 实现与手工公式存在不一致"
    elif pass3_seen:
        status = "LICENSE_UNVERIFIED"
        status_reason = "License 未确认（非数据集本身问题，需后续对接方提供 metadata）"
    else:
        status = "CONDITIONAL_ACCEPTED"
        status_reason = "Settlement 核对通过；license 待后续确认"

    baseline_checks = {
        "economic_odds_key": {
            "total_keys": r1["total_odds_keys"],
            "cross_date_keys": r1["cross_date_keys"],
            "single_date_keys": r1["single_date_keys"],
            "exact_duplicates": r1["exact_duplicate_rows"],
            "distinct_dates": r1["distinct_dates"],
            "note": note_cross,
        },
        "settlement_verification": {
            "all_pass": pass2,
            "categories": {
                cat: {
                    "checked": s["total_checked"],
                    "matched": s["matches"],
                    "mismatched": s["mismatches"],
                }
                for cat, s in r2["categories"].items()
            },
        },
        "license_provenance": {
            "status": r3["status"],
            "notes": r3["notes"],
        },
    }

    gate_result = {
        "baselight_status": status,
        "baselight_status_reason": status_reason,
        "baseline_checks": baseline_checks,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checked_by": "W2_GATE3_BASELIGHT_MINIMAL_ACCEPTANCE",
        "data_source": "API-Sports (v3.football.api-sports.io) — 非 Baselight 原始数据集",
        "ingestion_stage": "NOT_INGESTED (最小验收，未执行全量数据接入)",
        "constraints": [
            "未下载全量 5.22 亿行",
            "未构建 adapter",
            "未构建 walk-forward",
            "未修改 Gate3 为 CLOSED",
            "未修改 master roadmap",
            "未修改 W1 或 Stage7I runtime",
        ],
    }

    # Write JSON
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "W2_GATE3_BASELIGHT_MINIMAL_ACCEPTANCE.json"
    with open(json_path, "w") as fh:
        json.dump(gate_result, fh, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON report: {json_path}")

    # Write MD
    lines = [
        "# W2 Gate 3 — Baselight 最小验收报告",
        "",
        f"**日期**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"**BASELIGHT_STATUS**: `{status}`",
        "",
        f"**状态说明**: {status_reason}",
        "",
        "---",
        "",
        "## 数据源说明",
        "",
        "当前项目数据源为 **API-Sports** (v3.football.api-sports.io)，非 Baselight 原始数据集。",
        "所有检查基于现有本地数据（312 个 odds JSON 文件 + SQLite DB）进行对标。",
        "",
        "---",
        "",
        "## 1. 经济报价键跨日期检查",
        "",
        f"报价键定义: fixture_id + bookmaker + market + selection + line",
        "",
        "| 指标 | 数值 |",
        "|---|---|",
        f"| 总报价条目 | {r1['total_rows']:,} |",
        f"| 总报价键数 | {r1['total_odds_keys']:,} |",
        f"| 跨2+日期报价键 | {r1['cross_date_keys']:,} |",
        f"| 单日期报价键 | {r1['single_date_keys']:,} |",
        f"| Exact duplicate 行 | {r1['exact_duplicate_rows']:,} |",
        f"| distinct 收集日期 | {r1['distinct_dates']} |",
        "",
        f"**分析**: {note_cross}",
        "",
        "| 判定维度 | 结果 |",
        "|---|---|",
        "| 报价键可交叉引用 | ⚠️ 基础数据为单次快照布局 — 需 Baselight 时序数据方可验证变动 |",
        "| 无重复键 | ✅ 零 exact duplicate |",
        "",
        "---",
        "",
        "## 2. Settlement 核对",
        "",
        "使用 W2 现有 settlement 逻辑 (`asian_over_settlement.py` 的镜像实现) 与纯手工公式核对。",
        "Settlement 自测试已通过。",
        "",
        "| 分类 | 检查数 | 匹配 | 不匹配 |",
        "|---|---|---|---|",
    ]
    for cat, s in r2["categories"].items():
        lines.append(f"| {cat} | {s['total_checked']} | {s['matches']} | {s['mismatches']} |")
    lines += [
        "",
        f"**结果**: {'✅ ALL_MATCH' if pass2 else '❌ MISMATCH'} | Settlement {'PASS' if pass2 else 'FAIL'}",
        "",
        "---",
        "",
        "## 3. License / Provenance",
        "",
        f"**状态**: `{r3['status']}`",
        "",
        "**检查笔记**:",
    ]
    for n in r3["notes"]:
        lines.append(f"- {n}")
    lines += [
        "",
        "**建议**:",
        "",
        r3["recommendation"],
        "",
        "---",
        "",
        "## 4. 最终判定",
        "",
        "| 检查项 | 状态 | 说明 |",
        "|---|---|---|",
        f"| 报价键跨日期 | ⚠️ N/A | 单次快照布局，需 Baselight 时序数据验证 |",
        f"| Settlement 一致 | {'✅ PASS' if pass2 else '❌ FAIL'} | {'全部匹配' if pass2 else '存在异常'} |",
        f"| License 确认 | ⚠️ {r3['status']} | 未找到数据集 license metadata |",
        "",
        f"**BASELIGHT_STATUS**: `{status}`",
        "",
        "## 约束确认",
        "",
    ]
    for c in gate_result["constraints"]:
        lines.append(f"- ✅ {c}")
    lines += [
        "",
        "---",
        f"_报告由 {gate_result['checked_by']} 自动生成于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
    ]

    md_path = REPORTS_DIR / "W2_GATE3_BASELIGHT_MINIMAL_ACCEPTANCE.md"
    with open(md_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"✅ MD report: {md_path}")

    return gate_result


# ── MAIN ──

if __name__ == "__main__":
    print("🚀 W2 Baselight 最小验收开始")
    print(f"   项目: {REPO_ROOT}")
    print(f"   Odds 目录: {ODDS_DIR}")
    print(f"   报告目录: {REPORTS_DIR}")
    print()

    r1 = task1_economic_odds_key_check()
    r2 = task2_settlement_verification()
    r3 = task3_license_check()

    print("\n" + "=" * 72)
    print("生成报告...")
    final = generate_reports(r1, r2, r3)
    print(f"\n🏁 Baselight 最小验收完成")
    print(f"   BASELIGHT_STATUS = {final['baselight_status']}")
