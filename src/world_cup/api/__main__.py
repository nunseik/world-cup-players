"""Launcher for the API server:  world-cup-api --port 8000

argparse (consistent with the scraper CLI) wrapping uvicorn. Use --reload for
local dev and --workers N in production (mind: workers * api_pool_max must stay
under the database's connection ceiling).
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="world-cup-api", description="World Cup stats HTTP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Auto-reload (dev only)")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(
        "world_cup.api.app:app",
        host=args.host, port=args.port, reload=args.reload,
        workers=args.workers if not args.reload else 1,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
