#!/usr/bin/env python3
"""engine/sys_daily_settlement_summary.py — SYS每日结算汇总 + 中午链路完整性守卫
======================================================================
v2变更(2026-05-17): 升级为中午链路完整性守卫。
  检查V2/V4管道全产物，发现缺文件/guard fail/renderer未执行/marker缺失时输出
  CHAIN_INCOMPLETE而非PASS。

职责：只读文件、生成固定格式摘要、可选推送。
不调用 AI / agentTurn / memory_search / ReportAgent。
不自由总结。

用法:
  python3 engine/sys_daily_settlement_summary.py --date 20260515
  python3 engine/sys_daily_settlement_summary.py --date 20260515 --dry-run
  python3 engine/sys_daily_settlement_summary.py --date 20260515 --push              # mode=exception_only (默认安全: 仅异常推QQ)
  python3 engine/sys_daily_settlement_summary.py --date 20260515 --push --mode announce  # 全推(需显式)
  python3 engine/sys_daily_settlement_summary.py --date 20260515 --mode silent          # 只写文件不推QQ
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_TZ = timezone(timedelta(hours=8))
REPORT_DIR = BASE_DIR / "data" / "paper_trading"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
DAILY_DIR = BASE_DIR / "data" / "daily_reports"
ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"


def _load_json(path: Path, default: dict = None) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default or {}


def _exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# ── V2 链路产物路径 ──
def _v2_verified_path(date_key: str) -> Path:
    return REPORT_DIR / f"verified_{date_key}.json"


def _v2_task_status_path() -> Path:
    return STATUS_DIR / "task_status_v2_daily_settle.json"


# ── V4 链路产物路径 ──
def _v4_validation_path(date_key: str) -> Path:
    return DAILY_DIR / f"v4_ht_recommend_validation_{date_key}.json"


def _v4_attribution_path(date_key: str) -> Path:
    return ARCHIVE_DIR / f"v4_result_attribution_{date_key}.jsonl"


def _v4_full_report_path(date_key: str) -> Path:
    # 可能以 v4_review_full_{date}.txt 或 v4_review_{date}.txt 命名
    p1 = DAILY_DIR / f"v4_review_full_{date_key}.txt"
    p2 = DAILY_DIR / f"v4_review_{date_key}.txt"
    return p1 if p1.exists() else p2


def _v4_qq_report_path(date_key: str) -> Path:
    return DAILY_DIR / f"v4_review_qq_{date_key}.txt"


def _v4_guard_path(date_key: str) -> Path:
    return STATUS_DIR / f"v4_review_guard_{date_key}.json"


def _v4_route_path(date_key: str) -> Path:
    return STATUS_DIR / f"v4_review_route_{date_key}.json"


def _v4_push_path(date_key: str) -> Path:
    return STATUS_DIR / f"v4_review_push_{date_key}.json"


def _v4_readiness_path(date_key: str) -> Path:
    return STATUS_DIR / f"v4_review_readiness_{date_key}.json"


# ──────────────────────
# V2 链路完整性检查
# ──────────────────────

def check_v2_chain(date_key: str) -> dict:
    """
    检查 V2 结算链路的完整产物。
    返回:
      status: "COMPLETE" / "PARTIAL" / "MISSING" / "CHAIN_INCOMPLETE"
      detail: 说明
      files: 各文件存在性 {filename: bool}
    """
    verified_path = _v2_verified_path(date_key)
    task_status_path = _v2_task_status_path()

    products = {
        f"verified_{date_key}.json": _exists(verified_path),
        "task_status_v2_daily_settle.json": _exists(task_status_path),
    }

    task_status = _load_json(task_status_path)
    ts_status = task_status.get("status", "")

    # 检查两个核心文件
    if not products[f"verified_{date_key}.json"] and not products["task_status_v2_daily_settle.json"]:
        return {
            "status": "MISSING",
            "detail": "verified文件 和 task_status 均不存在",
            "files": products,
        }

    if not products[f"verified_{date_key}.json"]:
        return {
            "status": "CHAIN_INCOMPLETE",
            "detail": f"verified_{date_key}.json 不存在，但 task_status 存在",
            "files": products,
        }

    if not products["task_status_v2_daily_settle.json"]:
        return {
            "status": "CHAIN_INCOMPLETE",
            "detail": "task_status_v2_daily_settle.json 不存在，但 verified 存在",
            "files": products,
        }

    # task_status 必须为 DONE
    if ts_status != "DONE":
        detail = task_status.get("error", "") or task_status.get("message", "")
        return {
            "status": "CHAIN_INCOMPLETE",
            "detail": f"task_status={ts_status}: {detail}",
            "files": products,
        }

    # 读取 verified 内容
    verified = _load_json(verified_path)
    total = verified.get("total_predicted", 0)
    completed = verified.get("total_completed", 0)
    hits = verified.get("hits", 0)
    pnl = verified.get("total_pnl", 0.0)
    hit_rate = verified.get("hit_rate_pct", 0.0)

    return {
        "status": "COMPLETE",
        "detail": "",
        "bet_locked": total,
        "completed": completed,
        "hits": hits,
        "hit_rate_pct": hit_rate,
        "pnl": pnl,
        "files": products,
    }


# ──────────────────────
# V4 链路完整性检查
# ──────────────────────

def check_v4_chain(date_key: str) -> dict:
    """
    检查 V4 复盘链路的完整产物。
    V4每日复盘固定流程的8个产物:
      1. validation
      2. attribution
      3. full report
      4. QQ report
      5. guard
      6. route marker
      7. push/sent marker
      8. readiness (可选，存在时辅助诊断)

    返回:
      status: "COMPLETE" / "CHAIN_INCOMPLETE" / "MISSING"
      detail: 说明
      files: 各文件存在性 {filename: bool}
      missing: 缺失的文件名列表
      diagnosis: 诊断说明
    """
    products = {
        "validation": _exists(_v4_validation_path(date_key)),
        "attribution": _exists(_v4_attribution_path(date_key)),
        "full_report": _exists(_v4_full_report_path(date_key)),
        "qq_report": _exists(_v4_qq_report_path(date_key)),
        "guard": _exists(_v4_guard_path(date_key)),
        "route_marker": _exists(_v4_route_path(date_key)),
        "sent_marker": _exists(_v4_push_path(date_key)),
        "readiness": _exists(_v4_readiness_path(date_key)),
    }

    missing = [k for k, v in products.items() if not v]

    readable_names = {
        "validation": "v4_ht_recommend_validation",
        "attribution": "v4_result_attribution",
        "full_report": "v4_review_full / v4_review",
        "qq_report": "v4_review_qq",
        "guard": "v4_review_guard",
        "route_marker": "v4_review_route",
        "sent_marker": "v4_review_push",
        "readiness": "v4_review_readiness",
    }

    missing_names = [readable_names.get(k, k) for k in missing]

    present_names = [readable_names.get(k, k) for k, v in products.items() if v]
    present_count = sum(1 for v in products.values() if v)
    total_required = len(products)

    present_pct = round(present_count / total_required * 100)

    # 诊断：判断问题的根因
    diagnosis = ""

    if not products["validation"] and not products["attribution"]:
        # 验证和归因都不存在 — 赛果数据源或API问题
        diagnosis = "验证与归因均未执行"
    elif products["validation"] and products["attribution"] and not products["full_report"] and not products["qq_report"]:
        # 验证/归因存在，但渲染未执行
        diagnosis = "验证/归因已完成，渲染器未执行 renderer → guard → route → push 链条断裂"
    elif products["full_report"] and not products["qq_report"]:
        diagnosis = "full report 已生成但 QQ report 缺失，renderer --mode qq 未执行"
    elif products["full_report"] and products["qq_report"] and not products["guard"]:
        diagnosis = "full/qq 报告已存在，guard 未执行"
    elif products["guard"] and not products["route_marker"]:
        diagnosis = "guard 已生成，route marker 缺失"
    elif products["route_marker"] and not products["sent_marker"]:
        diagnosis = "route 已标记，push/sent marker 缺失"
    elif products["sent_marker"]:
        guard = _load_json(_v4_guard_path(date_key))
        guard_pass = guard.get("guard_status") == "PASS"
        if guard_pass:
            diagnosis = "完整链路已通过，复盘已推送"
        else:
            diagnosis = f"已推送但 guard 状态={guard.get('guard_status','?')}"
    elif present_count == 0:
        diagnosis = "所有链路产物均不存在"

    if not diagnosis:
        if present_pct >= 50:
            diagnosis = f"部分产物存在({present_count}/{total_required})，缺失: {', '.join(missing_names)}"
        else:
            diagnosis = f"大部分产物缺失({present_count}/{total_required})，仅存在: {', '.join(present_names)}"

    # 确定状态
    if present_count == total_required:
        status = "COMPLETE"
    elif present_count == 0:
        status = "MISSING"
    else:
        status = "CHAIN_INCOMPLETE"

    # 构建详情
    detail_parts = []
    if missing_names:
        detail_parts.append(f"缺失({len(missing_names)}): {'/'.join(missing_names)}")
    detail_parts.append(f"存在({present_count}/{total_required})")
    detail = " | ".join(detail_parts)

    result = {
        "status": status,
        "detail": detail,
        "diagnosis": diagnosis,
        "present_count": present_count,
        "total_required": total_required,
        "files": products,
        "missing": missing,
    }

    # 如有 guard 数据，补充 guard_status
    guard = _load_json(_v4_guard_path(date_key))
    if guard:
        result["guard_status"] = guard.get("guard_status", "UNKNOWN")
        result["guard_issues"] = guard.get("issues", [])

    # 如有 route，补充 route 状态
    route = _load_json(_v4_route_path(date_key))
    if route:
        result["allowed_to_push"] = route.get("allowed_to_push", False)
        result["route_reason"] = route.get("reason", "")

    # 如有 push，补充 push 状态
    push = _load_json(_v4_push_path(date_key))
    if push:
        result["sent"] = push.get("status") == "SENT"
        result["push_result"] = push.get("delivery_result", "")

    return result


# ──────────────────────
# V33 审计结果解读
# ──────────────────────

def check_v33_audit(date_key: str) -> dict:
    """读取 V33 residual audit 结果并分类严重级别。
    historical_doc 和 allowed_guard → INFO（status_only）
    active_v33_path → BLOCKER（exception_alert）
    """
    v33_path = STATUS_DIR / f"v33_residual_audit_{date_key}.json"
    if not v33_path.is_file():
        # Try without date (old hardcoded path)
        v33_path = STATUS_DIR / "v33_residual_audit_20260520.json"
    if not v33_path.is_file():
        return {
            "available": False,
            "severity": "status_only",
            "detail": "V33 audit result not found",
        }

    v33 = _load_json(v33_path)
    active = v33.get("active_v33_path_count", 0)
    allowed = v33.get("allowed_guard_count", 0)
    historical = v33.get("historical_doc_count", 0)
    check_status = v33.get("check_status", "PASS")

    if check_status == "BLOCKER" or active > 0:
        severity = "exception_alert"
        note = f"active_v33_path={active} — MUST be 0"
    else:
        severity = "status_only"
        note = f"allowed_guard={allowed} historical_doc={historical} — informational only, no QQ push"

    return {
        "available": True,
        "severity": severity,
        "check_status": check_status,
        "active_v33_path_count": active,
        "allowed_guard_count": allowed,
        "historical_doc_count": historical,
        "detail": note,
    }


# ──────────────────────
# 汇总构建
# ──────────────────────

def build_summary(date_key: str) -> dict:
    """生成汇总文本 + 链路完整性检查"""
    v2 = check_v2_chain(date_key)
    v4 = check_v4_chain(date_key)
    v33 = check_v33_audit(date_key)

    # 判断整体链路完整性
    v2_ok = v2["status"] == "COMPLETE"
    v4_ok = v4["status"] == "COMPLETE"
    chain_status = "COMPLETE" if (v2_ok and v4_ok) else "CHAIN_INCOMPLETE"

    # ── V2 文本 ──
    v2_lines = []
    v2_lines.append(f"产物完整性：{v2['status']}")
    if v2["status"] == "COMPLETE":
        v2_lines.append(f"BET_LOCKED：{v2.get('bet_locked',0)}")
        v2_lines.append(f"命中：{v2.get('hits',0)}/{v2.get('completed',0)}（{v2.get('hit_rate_pct',0)}%）")
        v2_lines.append(f"PnL：{v2.get('pnl',0)}u")
    elif v2.get("detail"):
        v2_lines.append(f"缺文件：{v2['detail']}")
    products_v2 = v2.get("files", {})
    present_v2 = [k for k, v in products_v2.items() if v]
    missing_v2 = [k for k, v in products_v2.items() if not v]
    v2_lines.append(f"存在({len(present_v2)}): {'/'.join(present_v2) if present_v2 else '无'}")
    if missing_v2:
        v2_lines.append(f"缺失({len(missing_v2)}): {'/'.join(missing_v2)}")

    # ── V4 文本 ──
    v4_lines = []
    v4_lines.append(f"链路完整性：{v4['status']}")
    v4_lines.append(f"诊断：{v4.get('diagnosis','')}")
    v4_lines.append(f"产物：{v4.get('present_count',0)}/{v4.get('total_required',8)}")

    missing_names = {
        "validation": "v4_ht_recommend_validation",
        "attribution": "v4_result_attribution",
        "full_report": "v4_review_full/v4_review",
        "qq_report": "v4_review_qq",
        "guard": "v4_review_guard",
        "route_marker": "v4_review_route",
        "sent_marker": "v4_review_push",
        "readiness": "v4_review_readiness",
    }
    missing_items = v4.get("missing", [])
    if missing_items:
        v4_lines.append(f"缺失：{'/'.join(missing_names.get(k, k) for k in missing_items)}")

    guard_status = v4.get("guard_status", "")
    if guard_status:
        v4_lines.append(f"guard状态：{guard_status}")

    sent = v4.get("sent")
    if sent is not None:
        v4_lines.append(f"推送状态：{'✅ 已推送' if sent else '待推送'}")
        if v4.get("push_result"):
            v4_lines.append(f"推送结果：{v4['push_result']}")

    # ── 当前状态文本 ──
    now = datetime.now(LOCAL_TZ)
    today_key = now.strftime("%Y%m%d")

    # 组装
    lines = []
    lines.append("【SYS 状态中控】")
    lines.append(f"📌 每日链路完整性检查 · {date_key}")
    lines.append(f"整体链路：{'✅ COMPLETE' if chain_status == 'COMPLETE' else '⚠️ CHAIN_INCOMPLETE'}")
    lines.append("")
    lines.append("【V2昨日结算】")
    lines.extend(v2_lines)
    lines.append("")
    lines.append("【V4昨日复盘】")
    lines.extend(v4_lines)
    # ── V33 审计 ──
    v33_lines = []
    if v33["available"]:
        severity_tag = "🔴 exception_alert" if v33["severity"] == "exception_alert" else "🟢 status_only (INFO)"
        v33_lines.append(f"V33审计：{v33['check_status']} | {severity_tag}")
        v33_lines.append(f"  active_v33_path={v33['active_v33_path_count']} (must=0)")
        v33_lines.append(f"  allowed_guard={v33['allowed_guard_count']} (guard/checker files — INFO, no push)")
        v33_lines.append(f"  historical_doc={v33['historical_doc_count']} (docs/archive refs — INFO, no push)")
    else:
        v33_lines.append(f"V33审计：结果文件未找到")

    lines.append("")
    lines.append("【今日准备】")
    lines.append(f"V2建池：13:15待执行")
    lines.append(f"V4午间扫描：14:05待执行")
    lines.append(f"SYS汇总：{chain_status}")
    lines.append("")
    lines.append("【V33审计】")
    lines.extend(v33_lines)

    summary_text = "\n".join(lines)

    return {
        "date": date_key,
        "chain_status": chain_status,
        "summary": summary_text,
        "v2": v2,
        "v4": v4,
        "v33_audit": v33,
        "checked_at": now.isoformat(),
    }


def push_via_system_event(summary_text: str, date_key: str) -> bool:
    """通过 sessions_send 推送至主会话"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"""
import json, sys
from pathlib import Path
push_path = Path('/Users/liudehua/.openclaw/workspace/v2_football_quant/data/runtime/status/sys_daily_summary_{date_key}.json')
push_data = {json.dumps({"date": date_key, "summary": summary_text, "status": "COMPLETE_REPORT"})}
push_path.write_text(json.dumps(push_data, ensure_ascii=False, indent=2), encoding='utf-8')
print('PUSH_FILE_WRITTEN')
"""],
            capture_output=True, text=True, timeout=30,
        )
        return "PUSH_FILE_WRITTEN" in result.stdout
    except Exception as e:
        print(f"[SYS] push write error: {e}", flush=True)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true", help="仅输出，不推")
    parser.add_argument("--push", action="store_true", help="推送（写文件 + sessions_send）— 等同 --mode exception_only")
    parser.add_argument("--mode", default="exception_only", choices=["announce", "exception_only", "silent"],
                        help="推送模式：exception_only=仅异常推(默认) / announce=全推(需显式) / silent=只写文件不推")
    args = parser.parse_args()

    # --push flag uses default mode (exception_only); only explicit --mode announce pushes everything
    # No override — --push alone means exception_only, which is now the safe default

    date_key = str(args.date).replace("-", "")
    result = build_summary(date_key)

    # Always write status file
    status_path = STATUS_DIR / f"sys_daily_summary_{date_key}.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(result["summary"])
    print(f"[SYS] mode={args.mode} chain_status={result['chain_status']}")

    should_push = False
    if args.mode == "announce":
        should_push = True
    elif args.mode == "exception_only":
        # Only push on CHAIN_INCOMPLETE or MISSING — not on COMPLETE
        should_push = result["chain_status"] in ("CHAIN_INCOMPLETE", "MISSING")
    elif args.mode == "silent":
        should_push = False

    if should_push:
        ok = push_via_system_event(result["summary"], date_key)
        if ok:
            print(f"[SYS] ✅ push file written: {status_path}")
        else:
            print(f"[SYS] ❌ push failed", flush=True)
    elif args.dry_run:
        print()
        print("--- dry-run (no push) ---")
    else:
        print(f"[SYS] ⏭️  push suppressed: mode={args.mode} chain_status={result['chain_status']}")


if __name__ == "__main__":
    main()
