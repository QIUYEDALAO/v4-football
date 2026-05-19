# Intel Ops Refresh Contract
Phase: INTEL-OPS-1 | One-command readonly refresh.

Command: python3 tools/intel_ops_refresh.py --date 2026-05-20 --history-from 2026-05-17 --history-to 2026-05-20

Executes: V2 current + V2 historical + builder + checker.
All guards default false. No QQ, no state, no verified, no D13.
