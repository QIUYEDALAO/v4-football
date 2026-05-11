from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _date_key(value: str | None = None) -> str:
    if value:
        return value.replace("-", "")
    return datetime.now().strftime("%Y%m%d")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def universe_path(date_key: str | None = None) -> Path:
    return DATA_DIR / "universe" / f"fixtures_universe_{_date_key(date_key)}.jsonl"


def decision_log_path(date_key: str | None = None) -> Path:
    return DATA_DIR / "decision_logs" / f"v4_decision_log_{_date_key(date_key)}.jsonl"


def shadow_backtest_path(date_key: str | None = None) -> Path:
    return DATA_DIR / "shadow_backtest" / f"shadow_entry_{_date_key(date_key)}.jsonl"


def execution_sim_path(date_key: str | None = None) -> Path:
    return DATA_DIR / "execution" / f"live_execution_sim_{_date_key(date_key)}.jsonl"
