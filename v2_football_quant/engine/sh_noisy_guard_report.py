from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
OUT_DIR = BASE_DIR / "data" / "capture_audit"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_report(date_key: str) -> dict:
    entries = _read_json(PAPER_DIR / f"v4_second_half_entries_{date_key}.json", [])
    if not isinstance(entries, list):
        entries = []

    def _norm_action(a: str) -> str:
        a = str(a or "UNKNOWN")
        if a == "SH_BUY_NOW":
            return "SH_PAPER_ONLY"
        if a == "SH_WATCH":
            return "SH_EV_CANDIDATE"
        return a

    action_counter = Counter(_norm_action(x.get("action")) for x in entries)
    noisy_reason_counter = Counter()
    odds = []
    ev_net_vals = []
    cons_vals = []
    ev_bucket = defaultdict(lambda: {"n": 0, "ev_net_sum": 0.0})
    for row in entries:
        for r in row.get("sh_noisy_reasons") or []:
            noisy_reason_counter[str(r)] += 1
        try:
            o = float(row.get("entry_over_odds"))
            odds.append(o)
        except Exception:
            pass
        try:
            ev = float(row.get("ev_net"))
            ev_net_vals.append(ev)
            if ev < 0:
                b = "<0"
            elif ev < 0.01:
                b = "0-0.01"
            elif ev < 0.03:
                b = "0.01-0.03"
            else:
                b = ">=0.03"
            ev_bucket[b]["n"] += 1
            ev_bucket[b]["ev_net_sum"] += ev
        except Exception:
            pass
        try:
            cons_vals.append(float(row.get("conservative_ev")))
        except Exception:
            pass

    n = len(entries)
    avg_odds = round(sum(odds) / len(odds), 4) if odds else None
    avg_ev = round(sum(ev_net_vals) / len(ev_net_vals), 6) if ev_net_vals else None
    avg_cons = round(sum(cons_vals) / len(cons_vals), 6) if cons_vals else None

    out = {
        "date": date_key,
        "generated_at": datetime.now().isoformat(),
        "sh_observe_total": n,
        "action_counts": dict(action_counter),
        "sh_noisy": int(action_counter.get("SH_NOISY", 0)),
        "sh_ev_candidate": int(action_counter.get("SH_EV_CANDIDATE", 0)),
        "sh_paper_only": int(action_counter.get("SH_PAPER_ONLY", 0)),
        "sh_blocked": int(action_counter.get("SH_BLOCKED", 0)),
        "avg_odds": avg_odds,
        "avg_ev_net": avg_ev,
        "avg_conservative_ev": avg_cons,
        "noisy_reason_top": noisy_reason_counter.most_common(20),
        "ev_bucket": {
            k: {
                "n": v["n"],
                "avg_ev_net": round(v["ev_net_sum"] / v["n"], 6) if v["n"] else 0.0,
            }
            for k, v in sorted(ev_bucket.items())
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"sh_noisy_guard_report_{date_key}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["output_path"] = str(path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()
    key = args.date.replace("-", "")
    print(json.dumps(build_report(key), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
