from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
V3_DATA_DIR = BASE_DIR / "data" / "v3_wc2026"
GROUP_SCHEDULE_PATH = V3_DATA_DIR / "group_schedule.json"


def _to_iso_dt(v: Any):
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    if len(s) == 10 and s.count("-") == 2:
        s = s + "T00:00:00+00:00"
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _team(match: dict[str, Any], side: str) -> str:
    if side == "home":
        return (
            match.get("home_team")
            or ((match.get("teams") or {}).get("home") or {}).get("name")
            or match.get("home")
            or ""
        )
    return (
        match.get("away_team")
        or ((match.get("teams") or {}).get("away") or {}).get("name")
        or match.get("away")
        or ""
    )


def _match_id(match: dict[str, Any]) -> str:
    return str(
        match.get("fixture_id")
        or match.get("match_id")
        or ((match.get("fixture") or {}).get("id") or "")
    )


def _detect_stage_from_text(v: str) -> str | None:
    s = str(v or "").upper()
    if not s:
        return None
    if "MD1" in s or "ROUND_1" in s:
        return "MD1"
    if "MD2" in s or "ROUND_2" in s:
        return "MD2"
    if "MD3" in s or "ROUND_3" in s:
        return "MD3"
    if any(x in s for x in ["KO", "KNOCKOUT", "ROUND OF 16", "QUARTER", "SEMI", "FINAL"]):
        return "KO"
    if "GROUP" in s:
        return "GROUP"
    return None


def build_group_schedule_index(matches: list[dict[str, Any]]) -> dict[str, list[tuple[datetime, str]]]:
    idx: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    group_all: list[tuple[datetime, str]] = []
    for m in matches:
        dt = _to_iso_dt(
            m.get("kickoff_utc")
            or m.get("fixture_date")
            or m.get("date")
            or ((m.get("fixture") or {}).get("date"))
        )
        if not dt:
            continue
        mid = _match_id(m)
        h = _team(m, "home")
        a = _team(m, "away")
        if h:
            idx[h].append((dt, mid))
        if a:
            idx[a].append((dt, mid))
        stage_text = str(m.get("stage") or "").lower()
        if stage_text == "group":
            group_all.append((dt, mid))
    for team, rows in idx.items():
        idx[team] = sorted(rows, key=lambda x: x[0])
    if group_all:
        seen = set()
        ordered = []
        for dt, mid in sorted(group_all, key=lambda x: x[0]):
            if not mid or mid in seen:
                continue
            seen.add(mid)
            ordered.append((dt, mid))
        if ordered:
            idx["__GROUP_MATCH_ORDER__"] = ordered
    return idx


def resolve_wc_stage(match: dict[str, Any], group_schedule: dict[str, list[tuple[datetime, str]]] | None = None) -> str:
    wc_stage = _detect_stage_from_text(match.get("wc_stage"))
    if wc_stage in {"MD1", "MD2", "MD3", "KO"}:
        return wc_stage

    stage_text = (
        match.get("stage")
        or ((match.get("league") or {}).get("round"))
        or ((match.get("fixture") or {}).get("status") or {}).get("long")
    )
    detected = _detect_stage_from_text(stage_text)
    if detected == "KO":
        return "KO"
    if detected in {"MD1", "MD2", "MD3"}:
        return detected

    md = match.get("matchday") or match.get("group_matchday")
    if md is not None:
        try:
            m = int(md)
            if m == 1:
                return "MD1"
            if m == 2:
                return "MD2"
            if m == 3:
                return "MD3"
        except Exception:
            pass

    if detected == "GROUP" or str(stage_text).lower() == "group":
        dt = _to_iso_dt(
            match.get("kickoff_utc")
            or match.get("fixture_date")
            or match.get("date")
            or ((match.get("fixture") or {}).get("date"))
        )
        h = _team(match, "home")
        a = _team(match, "away")
        mid = _match_id(match)
        if dt and h and a and group_schedule:
            home_list = group_schedule.get(h) or []
            away_list = group_schedule.get(a) or []
            h_no = next((i + 1 for i, (_, xmid) in enumerate(home_list) if str(xmid) == str(mid)), None)
            a_no = next((i + 1 for i, (_, xmid) in enumerate(away_list) if str(xmid) == str(mid)), None)
            if h_no == 1 and a_no == 1:
                return "MD1"
            if h_no == 2 and a_no == 2:
                return "MD2"
            if h_no == 3 and a_no == 3:
                return "MD3"
            # Fallback: use global group sequence split when team-by-team round is ambiguous.
            seq = group_schedule.get("__GROUP_MATCH_ORDER__") or []
            idx_no = next((i for i, (_, xmid) in enumerate(seq) if str(xmid) == str(mid)), None)
            if idx_no is not None and seq:
                n = len(seq)
                one = max(1, n // 3)
                two = max(one + 1, one * 2)
                if idx_no < one:
                    return "MD1"
                if idx_no < two:
                    return "MD2"
                return "MD3"
        return "UNKNOWN_STAGE"

    return "UNKNOWN_STAGE"


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        out = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        rows = obj.get("matches")
        if isinstance(rows, list):
            return rows
    return []


def _save_stage_audit(rows: list[dict[str, Any]], output: Path) -> None:
    by_stage: dict[str, int] = defaultdict(int)
    for r in rows:
        by_stage[str(r.get("wc_stage") or "UNKNOWN")] += 1
    payload = {"rows": len(rows), "by_stage": dict(sorted(by_stage.items()))}
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    p = argparse.ArgumentParser(description="Resolve WC stages (MD1/MD2/MD3/KO).")
    p.add_argument("--input", required=True, help="Input json/jsonl file")
    p.add_argument("--output", default="", help="Optional output jsonl with wc_stage")
    p.add_argument("--audit-output", default=str(V3_DATA_DIR / "v3_stage_audit.json"))
    args = p.parse_args()

    rows = _load_json_or_jsonl(Path(args.input))
    idx = build_group_schedule_index(rows)
    out = []
    for r in rows:
        x = dict(r)
        x["wc_stage"] = resolve_wc_stage(x, idx)
        out.append(x)

    if args.output:
        op = Path(args.output)
        op.parent.mkdir(parents=True, exist_ok=True)
        with open(op, "w", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    _save_stage_audit(out, Path(args.audit_output))
    by_stage = defaultdict(int)
    for r in out:
        by_stage[r.get("wc_stage", "UNKNOWN")] += 1
    print(json.dumps({"rows": len(out), "by_stage": dict(sorted(by_stage.items()))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
