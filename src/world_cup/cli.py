"""Command-line entrypoint:  world-cup scrape --year 2022 [--dry-run]"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog
from rich.console import Console
from rich.table import Table

from .pipeline import run_year

log = structlog.get_logger(__name__)
console = Console()


def _print_stats(year: int, stats: list) -> None:
    table = Table(title=f"World Cup {year} — {len(stats)} players")
    for col in ("Player", "Team", "#", "GP", "G", "A", "Min", "Fouls", "YC", "RC", "src"):
        table.add_column(col)
    for s in sorted(stats, key=lambda x: (-(x.goals or 0), x.player.full_name)):
        table.add_row(
            s.player.full_name,
            s.team.name if s.team else "",
            *(str(v) if v is not None else "" for v in (
                s.jersey_number, s.appearances, s.goals, s.assists,
                s.minutes_played, s.fouls_committed, s.yellow_cards, s.red_cards,
            )),
            s.source,
        )
    console.print(table)


def _build_sources(source: str):
    """Map the --source choice to (primary, fallback, use_fallback)."""
    from .sources.espn import EspnSource
    from .sources.fbref import FbrefSource

    if source == "fbref":
        return FbrefSource(), EspnSource(), False
    if source == "espn":
        return EspnSource(), FbrefSource(), False
    return FbrefSource(), EspnSource(), True  # "both": FBref primary + ESPN cross-check


CHROME_MACOS = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WARMUP_URL = "https://fbref.com/en/comps/1/history/World-Cups-Seasons"


async def _browser(args: argparse.Namespace) -> int:
    """Launch the user's real Chrome with a DevTools port so scrape can attach.

    A Chrome you launch yourself is not automation-fingerprinted, so Cloudflare
    Turnstile validates normally (unlike a Playwright-launched browser).
    """
    import subprocess
    from pathlib import Path

    from . import config

    if not Path(CHROME_MACOS).exists():
        console.print(f"[red]Google Chrome not found at:[/red] {CHROME_MACOS}")
        console.print("Install Chrome, or launch it yourself with "
                      f"--remote-debugging-port={args.port} and a dedicated --user-data-dir.")
        return 1

    profile = str(Path(config.settings.scrape_user_data_dir).resolve())
    subprocess.Popen(
        [CHROME_MACOS, f"--remote-debugging-port={args.port}",
         f"--user-data-dir={profile}", WARMUP_URL],
        start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    console.print(
        f"[green]Launched Chrome[/green] (debug port {args.port}, profile {profile}).\n"
        "If FBref shows a Cloudflare challenge, solve it once (it will validate in this "
        "real browser). Leave the window open, then in another terminal run:\n\n"
        f"  uv run world-cup scrape --year 2022 --cdp\n"
    )
    return 0


async def _scrape(args: argparse.Namespace) -> int:
    from . import config
    from .tournaments import YEARS  # static tournament list

    if args.cdp:
        config.settings.scrape_cdp_url = args.cdp

    primary, fallback, use_fallback = _build_sources(args.source)
    years = [args.year] if args.year else YEARS
    for year in years:
        try:
            stats = await run_year(
                year, dry_run=args.dry_run, primary=primary,
                fallback=fallback, use_fallback=use_fallback,
            )
        except Exception as exc:  # noqa: BLE001 - report per-year and continue
            console.print(f"[yellow]{year}: {type(exc).__name__}: {exc}[/yellow]")
            continue
        if args.dry_run:
            _print_stats(year, stats)
        else:
            console.print(f"[green]{year}: loaded {len(stats)} players[/green]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="world-cup", description="FIFA World Cup stats scraper")
    sub = parser.add_subparsers(dest="command", required=True)

    scrape = sub.add_parser("scrape", help="Scrape one or all World Cup years")
    scrape.add_argument("--year", type=int, help="Single year (default: all seeded years)")
    scrape.add_argument("--dry-run", action="store_true", help="Parse + print; no DB writes")
    scrape.add_argument(
        "--source", choices=("both", "fbref", "espn"), default="both",
        help="both = FBref primary + ESPN cross-check (default); or a single source",
    )
    scrape.add_argument(
        "--cdp", nargs="?", const="http://localhost:9222", default=None,
        help="Attach to a Chrome started via `world-cup browser` (needed for FBref). "
             "Optional URL; defaults to http://localhost:9222",
    )
    scrape.set_defaults(func=_scrape)

    browser = sub.add_parser(
        "browser",
        help="Launch your real Chrome with a DevTools port so `scrape --cdp` can "
             "attach to it (the only way past FBref's Cloudflare Turnstile).",
    )
    browser.add_argument("--port", type=int, default=9222, help="DevTools port (default 9222)")
    browser.set_defaults(func=_browser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
