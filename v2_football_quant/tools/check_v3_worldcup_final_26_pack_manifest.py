#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
MANIFEST = BASE / "v3_wc2026_final_26_pack_manifest.json"
DOC = ROOT / "docs/V3_WC_FINAL_26_SQUAD_PACK_PHASE_7_PACK_MANIFEST_AND_REGISTRY_20260604.md"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_final_26_pack_manifest_20260604.json"

EXPECTED_COUNTS = {
    "team_count": 48,
    "total_players": 1248,
    "coach_count": 48,
    "teams_with_26_players": 48,
    "position_distribution": {"GK": 145, "DF": 421, "MF": 371, "FW": 311},
}
SAFETY_EXPECTED = {
    "observation_only": True,
    "no_starting_xi": True,
    "no_injury_judgment": True,
    "no_prediction": True,
    "betting_recommendation": False,
    "affects_v4": False,
}
DISALLOWED_TEXT = [
    "starting lineup",
    "starting_lineup",
    "starting_players",
    "injury_status",
    "suspension_status",
    "strength ranking",
    "strength_ranking",
    "prediction ranking",
    "prediction_ranking",
    "betting signal",
    "betting_signal",
    "recommended_pick",
    "recommendation_ranking",
    "fund_flow",
    "steam",
    "drift",
]
SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}",
    r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
    r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def git_ls_files(path: Path) -> list[str]:
    rel = str(path.relative_to(ROOT))
    result = subprocess.run(["git", "ls-files", rel], cwd=ROOT, text=True, capture_output=True, check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(re.search(pattern, text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def check_safety(failures: list[str], node: dict[str, Any], prefix: str) -> None:
    for key, expected in SAFETY_EXPECTED.items():
        add(failures, node.get(key) is expected, f"{prefix}_{key}_unexpected", node.get(key))


def main() -> int:
    failures: list[str] = []
    add(failures, MANIFEST.exists(), "manifest_missing", MANIFEST.relative_to(ROOT))
    if failures:
        print(json.dumps({"conclusion": "BLOCKER", "failures": failures}, ensure_ascii=False, indent=2))
        return 2

    manifest = load_json(MANIFEST)
    add(failures, manifest.get("pack_name") == "V3_WC_FINAL_26_SQUAD_PACK", "pack_name_unexpected", manifest.get("pack_name"))
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    add(failures, len(artifacts) == 10, "artifact_count_unexpected", len(artifacts))
    for artifact in artifacts:
        rel = artifact.get("path")
        path = ROOT / str(rel)
        add(failures, artifact.get("exists") is True and path.exists(), "artifact_missing", rel)
        add(failures, int(artifact.get("file_size") or 0) > 0, "artifact_file_size_empty", rel)
        add(failures, isinstance(artifact.get("sha256"), str) and len(artifact.get("sha256")) == 64, "artifact_sha256_invalid", rel)

    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    for key in ["team_count", "total_players", "coach_count", "teams_with_26_players"]:
        add(failures, counts.get(key) == EXPECTED_COUNTS[key], f"{key}_unexpected", counts.get(key))
    add(failures, counts.get("position_distribution") == EXPECTED_COUNTS["position_distribution"], "position_distribution_unexpected", counts.get("position_distribution"))
    nodes = manifest.get("war_room_nodes") if isinstance(manifest.get("war_room_nodes"), dict) else {}
    final_node = nodes.get("final_26_squad_observation") if isinstance(nodes.get("final_26_squad_observation"), dict) else {}
    profile_node = nodes.get("final_26_squad_profile_observation") if isinstance(nodes.get("final_26_squad_profile_observation"), dict) else {}
    add(failures, final_node.get("exists") is True, "final_26_squad_observation_node_missing", final_node)
    add(failures, profile_node.get("exists") is True, "final_26_squad_profile_observation_node_missing", profile_node)
    add(failures, final_node.get("module") == "final_26_squad_observation", "final_node_module_unexpected", final_node.get("module"))
    add(failures, profile_node.get("module") == "final_26_squad_profile_observation", "profile_node_module_unexpected", profile_node.get("module"))
    add(failures, profile_node.get("ranking_type") == "roster_observation_ranking", "profile_ranking_type_unexpected", profile_node.get("ranking_type"))
    add(failures, int(profile_node.get("team_profile_refs_count") or 0) == 48, "profile_refs_count_unexpected", profile_node.get("team_profile_refs_count"))
    check_safety(failures, manifest.get("safety") if isinstance(manifest.get("safety"), dict) else {}, "manifest_safety")
    check_safety(failures, profile_node.get("safety") if isinstance(profile_node.get("safety"), dict) else {}, "profile_node_safety")
    final_safety = final_node.get("safety") if isinstance(final_node.get("safety"), dict) else {}
    for key, expected in {
        "observation_only": True,
        "no_starting_xi": True,
        "no_injury_judgment": True,
        "betting_recommendation": False,
        "affects_v4": False,
    }.items():
        add(failures, final_safety.get(key) is expected, f"final_node_safety_{key}_unexpected", final_safety.get(key))
    add(failures, manifest.get("raw_docx_policy") == "ACCEPT_RAW_UNTRACKED", "raw_docx_policy_unexpected", manifest.get("raw_docx_policy"))
    add(failures, manifest.get("final_pack_acceptance_ready") is True, "final_pack_acceptance_not_ready", manifest.get("final_pack_acceptance_ready"))

    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for path in [MANIFEST, DOC]
        if path.exists()
    )
    for token in DISALLOWED_TEXT:
        add(failures, token not in text, "disallowed_text", token)
    relevant_runtime = [item for item in git_ls_files(ROOT / "data/runtime") if "final_26" in item or "squad" in item]
    add(failures, not relevant_runtime, "runtime_squad_output_tracked", relevant_runtime[:5])
    secrets = secret_hits([MANIFEST, DOC, ROOT / "tools/build_v3_worldcup_final_26_pack_manifest.py", Path(__file__).resolve()])
    add(failures, not secrets, "secret_literal_hits", secrets)
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "artifact_count": len(artifacts),
        "counts": counts,
        "raw_docx_policy": manifest.get("raw_docx_policy"),
        "final_pack_acceptance_ready": manifest.get("final_pack_acceptance_ready"),
        "runtime_relevant_tracked": relevant_runtime,
        "secret_hits": secrets,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
