#!/usr/bin/env python3
"""Phase commit manifest gate — validates HEAD commit file list."""
import argparse, json, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
CN = timezone(timedelta(hours=8))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--phase",required=True); p.add_argument("--required",action="append",default=[])
    p.add_argument("--forbidden",action="append",default=[])
    a=p.parse_args()
    r=subprocess.run(["git","show","--name-only","--pretty=","HEAD"],capture_output=True,text=True)
    head_files=[l.strip() for l in r.stdout.split("\n") if l.strip()]
    missing=[f for f in a.required if f not in head_files]
    found_fb=[f for f in a.forbidden if any(f in h for h in head_files)]
    status="PASS" if not missing and not found_fb else "FAIL"
    out={"schema_version":"phase_commit_manifest.v1","phase":a.phase,"status":status,
         "required_files_count":len(a.required),"required_files_present":len(a.required)-len(missing),
         "required_files_missing":missing,"forbidden_patterns_count":len(a.forbidden),
         "forbidden_files_found":found_fb,"head_files_count":len(head_files),"head_files":head_files,
         "generated_at":datetime.now(CN).isoformat()}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    if status!="PASS": raise SystemExit(2)
if __name__=="__main__": main()
# D.8.18.2 manifest gate
