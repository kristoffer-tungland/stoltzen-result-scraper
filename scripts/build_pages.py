"""Build the static 2026 GitHub Pages site in docs/."""

from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs"
SOURCE = ROOT / "results.csv"
SITE_FILES = (
    "results_viewer.html",
    "oversikter.html",
    "diplomer.html",
    "highlights.js",
    "diplomas.js",
)
REQUIRED_COLUMNS = {"Gruppe", "Navn", "Tid", "Maalpassering", "Trappetid"}


def validate_snapshot(data: bytes) -> tuple[int, int]:
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV mangler kolonner: {', '.join(sorted(missing))}")
        rows = list(reader)
    except UnicodeDecodeError as error:
        raise ValueError("CSV må være UTF-8-kodet") from error

    if not rows or any(not (row.get("Navn") or "").strip() for row in rows):
        raise ValueError("CSV må ha deltakere med navn")
    finished = sum(bool((row.get("Tid") or "").strip()) for row in rows)
    if not finished:
        raise ValueError("CSV inneholder ingen sluttider")
    return len(rows), finished


def build_site() -> tuple[int, int]:
    snapshot = SOURCE.read_bytes()
    total, finished = validate_snapshot(snapshot)
    if not OUTPUT.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Ugyldig publiseringsmappe")
    OUTPUT.mkdir(exist_ok=True)
    for filename in SITE_FILES:
        shutil.copy2(ROOT / filename, OUTPUT / filename)
    shutil.copytree(ROOT / "assets", OUTPUT / "assets", dirs_exist_ok=True)
    (OUTPUT / "results.csv").write_bytes(snapshot)
    print(f"docs/ klar: {total} på startlisten, {finished} i mål. Kun 2026-data.")
    return total, finished


if __name__ == "__main__":
    build_site()
