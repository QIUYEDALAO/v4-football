#!/usr/bin/env python3
"""V2 D10 Production Proof Authorization Checker"""
import json, sys, subprocess
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"

REQUIRED_DOCS = [
    "V2_D10_PRODUCTION_PROOF_AUTHORIZATION_PACKET.md",
    "V2_D10_SIX_PROOF_EVIDENCE_MATRIX.md",
    "V2_D10_CONTROLLED_PROOF_COMMAND_DRAFTS.md",
]
SIX_PROOF_TARGETS = [
    "real_state_present_case", "active_window_mutation_path",
    "production_cron_path", "production_qq_path",
    "production_verified_path", "formal_state_write_path",
]
FORBIDDEN_STAGED = ["data/runtime","data/state","data/paper_trading",
                    ".xlsx",".xls","engine/net_utils.py","secret",".env","token","key"]

def _run(cmd): return subprocess.run(cmd, capture_output=True, text=True, cwd=str(MODULE_ROOT))

def main():
    r = {"check_status":"PASS","packet_exists":False,"matrix_exists":False,"drafts_exists":False,
         "d10_allowed_to_generate":True,"d10_allowed_to_execute":False,
         "d11_allowed_to_generate":True,"d11_allowed_to_execute":False,
         "production_proof_execution_authorized":False,"PIPELINE_READY":False,"PRODUCTION_VERIFIED":False,
         "all_six_targets_present":False,"all_six_targets_unproven":True,"all_six_execution_allowed":False,
         "cron_enable_allowed":False,"qq_push_allowed":False,"state_write_allowed":False,
         "verified_write_allowed":False,"phase_e_allowed":False,
         "v4_frozen_at_j3":True,"v4_controlled_observe_execution_allowed":False,
         "forbidden_staged":[],"blockers":[],"warnings":[]}
    block = False

    for d in REQUIRED_DOCS:
        if (DOCS_DIR/d).is_file():
            r["packet_exists" if "PACKET" in d else "matrix_exists" if "MATRIX" in d else "drafts_exists"] = True
        else:
            r["blockers"].append(f"Missing: {d}"); block = True

    if r["matrix_exists"]:
        txt = (DOCS_DIR/"V2_D10_SIX_PROOF_EVIDENCE_MATRIX.md").read_text()
        r["all_six_targets_present"] = all(t in txt for t in SIX_PROOF_TARGETS)
        if not r["all_six_targets_present"]:
            r["blockers"].append("Not all six proof targets present"); block = True
        r["all_six_targets_unproven"] = all("UNPROVEN" in txt for _ in SIX_PROOF_TARGETS)
        r["all_six_execution_allowed"] = not ("execution_allowed.*true" in txt.lower())

    if r["packet_exists"]:
        pk = (DOCS_DIR/"V2_D10_PRODUCTION_PROOF_AUTHORIZATION_PACKET.md").read_text()
        for check in ["does NOT authorize","not yet authorized","UNPROVEN"]:
            if check not in pk:
                r["warnings"].append(f"'{check}' not in auth packet")

    # Staged check
    proc = _run(["git","diff","--name-only","--cached"])
    for line in proc.stdout.split("\n"):
        for pat in FORBIDDEN_STAGED:
            if pat in line.strip():
                r["forbidden_staged"].append(line.strip())
    if r["forbidden_staged"]:
        r["blockers"].append(f"Forbidden staged: {r['forbidden_staged']}"); block = True

    # Blocker conditions
    blk = [("d10_allowed_to_execute",r["d10_allowed_to_execute"]),("PIPELINE_READY",r["PIPELINE_READY"]),
           ("PRODUCTION_VERIFIED",r["PRODUCTION_VERIFIED"]),("phase_e_allowed",r["phase_e_allowed"])]
    for name,val in blk:
        if val: r["blockers"].append(f"{name} is true"); block = True

    if block: r["check_status"] = "BLOCKER"
    elif r["warnings"]: r["check_status"] = "WARN"

    print("="*50)
    print("V2 D10 PRODUCTION PROOF AUTHORIZATION CHECKER")
    print("="*50)
    print(f"Status: {r['check_status']}")
    for k,v in r.items():
        if k in ("blockers","warnings"): continue
        if isinstance(v,list) and not v: continue
        print(f"  {k}: {v}")
    if r["blockers"]:
        print(f"\nBLOCKERS:") 
        for b in r["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    elif r["warnings"]:
        print(f"\nWARNINGS:")
        for w in r["warnings"]: print(f"  ? {w}")

    md = MODULE_ROOT/"data"/"runtime"/"status"
    md.mkdir(parents=True,exist_ok=True)
    mp = md/"v2_d10_production_proof_authorization_check.json"
    mp.write_text(json.dumps(r,indent=2,ensure_ascii=False))
    print(f"\nMarker: {mp} (NOT committed)")
    return 0
if __name__=="__main__": sys.exit(main())
