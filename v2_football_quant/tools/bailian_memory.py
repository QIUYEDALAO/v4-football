#!/usr/bin/env python3
"""
阿里云百炼长期记忆 API 集成脚本
基于 OpenClaw 系统，将对话关键信息自动存储并支持语义检索。

Base URL: https://dashscope.aliyuncs.com/api/v2/apps/memory/
Auth: Bearer $DASHSCOPE_API_KEY

用法:
  python3 bailian_memory.py add --user "boss" --msg "用户: 我用FastAPI做项目" --msg "助理: 好的"
  python3 bailian_memory.py search --user "boss" --query "项目技术栈"
  python3 bailian_memory.py list --user "boss"
  python3 bailian_memory.py delete --node-id <id>
  python3 bailian_memory.py stats --user "boss"
"""

import os, sys, json, urllib.request, argparse
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
BASE_URL = "https://dashscope.aliyuncs.com/api/v2/apps/memory"


def _api_key() -> str:
    """获取 DashScope API Key。"""
    import re
    # Only check DASHSCOPE_API_KEY env var (not OPENAI_API_KEY — that's Zhipu)
    v = os.environ.get("DASHSCOPE_API_KEY")
    if v and len(v) > 15:
        return v
    # Fallback: scan .env and .zshrc for any sk- key
    for path in [os.path.expanduser("~/.openclaw/.env"), os.path.expanduser("~/.zshrc")]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    m = re.search(r"(?i)(?:DASHSCOPE_API_KEY)[=:]['\"]?([a-zA-Z0-9_\-]{20,})['\"]?", line)
                    if m:
                        v = m.group(1)
                        if v and len(v) > 10 and v != "***":
                            return v
    return ""


def _headers():
    key = _api_key()
    if not key:
        print("❌ API Key 未配置。请在环境变量设置 DASHSCOPE_API_KEY", file=sys.stderr)
        sys.exit(1)
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _post(path: str, data: dict) -> dict:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ HTTP {e.code}: {body[:300]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 请求失败: {e}", file=sys.stderr)
        sys.exit(1)


def _get(path: str, params: dict = None) -> dict:
    qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in (params or {}).items()) if params else ""
    url = f"{BASE_URL}/{path.lstrip('/')}?{qs}" if qs else f"{BASE_URL}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ HTTP {e.code}: {body[:300]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 请求失败: {e}", file=sys.stderr)
        sys.exit(1)


def _delete(path: str) -> dict:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    req = urllib.request.Request(url, data=b"{}", headers=_headers(), method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ HTTP {e.code}: {body[:300]}", file=sys.stderr)
        sys.exit(1)


# ── 命令处理 ──

def cmd_add(args):
    """添加记忆片段（自动提炼+向量化）"""
    if not args.msg and not args.custom:
        print("❌ 需要 --msg 或 --custom", file=sys.stderr)
        sys.exit(1)

    data = {
        "user_id": args.user,
        "meta_data": {"source": "openclaw_v4", "timestamp": datetime.now(CST).isoformat()},
    }
    if args.custom:
        data["custom_content"] = args.custom
    else:
        data["messages"] = [{"role": "user" if i % 2 == 0 else "assistant", "content": m} for i, m in enumerate(args.msg)]
    if args.library_id:
        data["memory_library_id"] = args.library_id

    result = _post("add", data)
    nodes = result.get("memory_nodes", [])
    print(f"✅ 已添加 {len(nodes)} 条记忆 (request_id={result.get('request_id','?')})")
    for n in nodes:
        print(f"  [{n.get('event','?')}] {n.get('memory_node_id','?')}: {n.get('content','')[:80]}")


def cmd_search(args):
    """语义搜索记忆"""
    data = {
        "user_id": args.user,
        "messages": [{"role": "user", "content": args.query}],
        "top_k": args.top_k or 10,
        "min_score": args.min_score or 0.3,
    }
    if args.library_id:
        data["memory_library_id"] = args.library_id

    result = _post("memory_nodes/search", data)
    nodes = result.get("memory_nodes", [])
    print(f"🔍 搜索到 {len(nodes)} 条相关记忆 (request_id={result.get('request_id','?')})")
    for i, n in enumerate(nodes, 1):
        score = n.get("score", "")
        score_str = f" (score={score:.2f})" if isinstance(score, (int, float)) else ""
        print(f"\n  [{i}]{score_str}")
        print(f"  ID: {n.get('memory_node_id','?')}")
        print(f"  内容: {n.get('content','')[:200]}")


def cmd_list(args):
    """列出所有记忆"""
    params = {"user_id": args.user, "page_num": args.page or 1, "page_size": args.size or 10}
    if args.library_id:
        params["memory_library_id"] = args.library_id

    result = _get("memory_nodes", params)
    nodes = result.get("memory_nodes", [])
    total = result.get("total", len(nodes))
    print(f"📋 共 {total} 条记忆 (第{params['page_num']}页, 每页{params['page_size']}条)")
    for i, n in enumerate(nodes, 1):
        created = n.get("created_at", 0)
        if created:
            dt = datetime.fromtimestamp(created, tz=CST).strftime("%m-%d %H:%M")
        else:
            dt = "?"
        print(f"  [{i}] {dt} {n.get('memory_node_id','?')}")
        print(f"       {n.get('content','')[:120]}")


def cmd_delete(args):
    """删除指定记忆"""
    if not args.node_id:
        print("❌ 需要 --node-id", file=sys.stderr)
        sys.exit(1)
    path = f"memory_nodes/{args.node_id}"
    if args.library_id:
        path += f"?memory_library_id={args.library_id}"
    result = _delete(path)
    print(f"🗑️ 已删除 (request_id={result.get('request_id','?')})")


def cmd_stats(args):
    """查看记忆统计"""
    result = _get("memory_nodes", {"user_id": args.user, "page_num": 1, "page_size": 1})
    total = result.get("total", 0)
    print(f"📊 记忆统计 (user: {args.user})")
    print(f"  总记忆数: {total}")
    # Quick connectivity test
    print(f"  API 状态: ✅ 连通" if "memory_nodes" in result else f"  API 状态: ⚠️ 异常")
    return total


# ── CLI ──

def main():
    p = argparse.ArgumentParser(description="阿里云百炼长期记忆 API 工具")
    p.add_argument("--user", default="boss", help="记忆实体 ID（默认: boss）")
    p.add_argument("--library-id", help="记忆库 ID")
    p.add_argument("--node-id", help="记忆片段 ID")
    p.add_argument("--query", help="搜索关键词")
    p.add_argument("--msg", action="append", help="对话消息（可多次）")
    p.add_argument("--custom", help="自定义内容（与 --msg 互斥）")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--min-score", type=float, default=0.3)

    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("add", help="添加记忆")
    sp.add_argument("--msg", action="append")
    sp.add_argument("--custom")
    sp.add_argument("--user")
    sp.add_argument("--library-id")

    sp = sub.add_parser("search", help="搜索记忆")
    sp.add_argument("--query", required=True)
    sp.add_argument("--user")
    sp.add_argument("--top-k", type=int)
    sp.add_argument("--min-score", type=float)
    sp.add_argument("--library-id")

    sp = sub.add_parser("list", help="列出记忆")
    sp.add_argument("--user")
    sp.add_argument("--page", type=int)
    sp.add_argument("--size", type=int)
    sp.add_argument("--library-id")

    sp = sub.add_parser("delete", help="删除记忆")
    sp.add_argument("--node-id", required=True)
    sp.add_argument("--library-id")

    sp = sub.add_parser("stats", help="记忆统计")
    sp.add_argument("--user")

    args = p.parse_args()
    cmd_map = {"add": cmd_add, "search": cmd_search, "list": cmd_list, "delete": cmd_delete, "stats": cmd_stats}
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
