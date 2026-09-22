#!/usr/bin/env python3
"""Continuously refresh EQ Timing results and serve the local viewer."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Sequence

from eqtiming_scraper import (
    DEFAULT_CLUB,
    DEFAULT_EVENT_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_YEAR,
    EqtimingScraper,
    StoltzenHistory,
    build_output_rows,
    normalize_name,
    write_csv,
)


def historical_result_urls(club: str, year: int) -> Sequence[str]:
    if normalize_name(club) != normalize_name(DEFAULT_CLUB):
        return ()
    return (
        f"http://www.stoltzen.no/resultater/{year - 1}/resklubb_16.html",
        f"http://www.stoltzen.no/resultater/{year - 2}/resklubb_16.html",
    )


class LiveUpdater:
    def __init__(self, event_id: str, club: str, year: int, output: Path,
                 interval: int, timeout: int, no_history: bool):
        self.event_id = event_id
        self.club = club
        self.year = year
        self.output = output
        self.interval = interval
        self.no_history = no_history
        self.eq = EqtimingScraper(timeout=timeout)
        self.history = StoltzenHistory(
            timeout=timeout,
            result_urls=historical_result_urls(club, year),
        )
        self.stop_event = threading.Event()

    def update_once(self) -> int:
        current = self.eq.fetch_current(self.event_id, self.club)
        rows = build_output_rows(
            current,
            self.year,
            self.history,
            self.no_history,
        )
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="results_",
                suffix=".csv",
                dir=self.output.parent,
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
            write_csv(rows, str(temporary_path))
            os.replace(temporary_path, self.output)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
        return len(rows)

    def run(self) -> None:
        while not self.stop_event.wait(self.interval):
            try:
                count = self.update_once()
                print(f"Oppdaterte {count} deltakere", flush=True)
            except Exception as exc:
                print(f"Live-oppdatering feilet: {exc}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh EQ Timing results continuously and serve results_viewer.html"
    )
    parser.add_argument("--event-id", default=DEFAULT_EVENT_ID)
    parser.add_argument("--club", default=DEFAULT_CLUB)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--output", default="results.csv")
    parser.add_argument("--interval", type=int, default=30, help="Refresh interval in seconds")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--no-history", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()

    if args.interval < 5:
        parser.error("--interval must be at least 5 seconds")

    project_root = Path(__file__).resolve().parent.parent
    output = Path(args.output)
    if not output.is_absolute():
        output = project_root / output

    updater = LiveUpdater(
        args.event_id,
        args.club,
        args.year,
        output,
        args.interval,
        args.timeout,
        args.no_history,
    )
    try:
        count = updater.update_once()
    except Exception as exc:
        print(f"Første oppdatering feilet: {exc}", file=sys.stderr)
        return 1

    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        partial(SimpleHTTPRequestHandler, directory=str(project_root)),
    )
    update_thread = threading.Thread(target=updater.run, daemon=True)
    update_thread.start()
    viewer_url = f"http://127.0.0.1:{args.port}/results_viewer.html"
    print(f"Skrev {count} deltakere. Live-visning: {viewer_url}", flush=True)
    print(f"Oppdaterer hvert {args.interval}. sekund. Trykk Ctrl+C for å stoppe.", flush=True)
    if args.open_browser:
        webbrowser.open(viewer_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopper live-visningen.")
    finally:
        updater.stop_event.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
