# AGENTS

Main agent may execute project tasks directly when BOSS explicitly provides a
BOSS 强制指令 and the target project path is clear.

For `/Users/liudehua/.openclaw/workspace/v2_football_quant`, the following are
allowed when explicitly requested by BOSS:
- Project runtime access
- Project code modification
- Project checker execution
- Project dry-run execution
- Git commit and push

Do not require `/agent <project-id>` unless a separate project-agent system is
actually available and confirmed.

Security boundaries remain active:
- no secrets
- no `.env`
- no `git add .`
- no `git add -A`
- no unauthorized DEFAULT_RULES changes
- no unauthorized validation recomputation
- no unauthorized validation history mutation
- no unauthorized live bet record mutation
- no unauthorized QQ push
- no free kill/retry of watchdog tasks
