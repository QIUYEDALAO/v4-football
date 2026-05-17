#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Dashboard as read-only local static files")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    parser.add_argument(
        "--dir",
        default="data/runtime/dashboard",
        help="Static directory to serve (default: data/runtime/dashboard)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.dir).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"[serve_dashboard] directory not found: {root}")

    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"[serve_dashboard] serving read-only static files")
    print(f"[serve_dashboard] root: {root}")
    print(f"[serve_dashboard] url : http://{args.host}:{args.port}/index.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("[serve_dashboard] stopped")


if __name__ == "__main__":
    # Guardrail: this utility only serves static files and does not invoke any runtime jobs.
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
