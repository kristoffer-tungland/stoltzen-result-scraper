#!/usr/bin/env python3
"""Fetch current Stoltzen results from EQ Timing and enrich them with history.

EQ Timing's public API has changed field names a few times.  The parser in this
module consequently accepts both the current names and the names used by older
exports.  The pure parsing/merging functions are intentionally kept separate
from HTTP code so they can be tested with fixtures.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

CSV_FIELDS = [
    "Gruppe", "Navn", "Tid", "Klasse", "Deltagelser", "BesteTidligere",
    "BesteÅr", "NyBestetid", "Differanse",
]
DEFAULT_EVENT_ID = "78640"
DEFAULT_CLUB = "COWI"
DEFAULT_YEAR = 2026
DEFAULT_TIMEOUT = 15


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    """Return the first non-empty value, including a case-insensitive lookup."""
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    lowered = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return value
    return None


def _rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    """Extract result rows from common EQ Timing response envelopes."""
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    preferred = (
        "results", "result", "rows", "items", "data", "contestants",
        "participants", "startlist", "startList", "StartList", "searchResults", "Rows", "Items",
    )
    for key in preferred:
        value = _first(payload, key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
        if isinstance(value, Mapping):
            rows = _rows_from_payload(value)
            if rows:
                return rows
    # Some API versions return a dictionary keyed by participant id.
    values = list(payload.values())
    if values and all(isinstance(value, Mapping) for value in values):
        return [dict(value) for value in values]
    return []


def _flatten_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Bring nested Person/Participant/Competitor fields next to outer fields."""
    result = dict(row)
    nested_keys = ("participant", "Participant", "Deltaker", "deltaker", "person", "Person", "competitor", "Competitor")
    for key in nested_keys:
        nested = row.get(key)
        if isinstance(nested, Mapping):
            for nested_key, value in nested.items():
                result.setdefault(nested_key, value)
            # EQ Timing uses Deltaker.Utover.NavnFormatert and
            # Deltaker.Klasse.Navn in the 2025/2026 response shape.
            for nested_key in ("Utover", "Klasse", "Class", "Person"):
                deeper = nested.get(nested_key)
                if isinstance(deeper, Mapping):
                    for deeper_key, value in deeper.items():
                        result.setdefault(deeper_key, value)
    # Startlist rows may expose Utover/Klasse directly, without Deltaker.
    for nested_key in ("Utover", "Klasse", "Class", "Person"):
        deeper = row.get(nested_key)
        if isinstance(deeper, Mapping):
            for deeper_key, value in deeper.items():
                result.setdefault(deeper_key, value)
    return result


def normalize_name(name: Any) -> str:
    """Normalize names for exact matching while retaining word order."""
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "", text)


def parse_time(value: Any) -> Optional[str]:
    """Normalize race times to M:SS or H:MM:SS.

    Dot-separated values are common on the old Stoltzen site (07.54).  A
    three-part dot value is treated as M:SS:hundredths, not H:MM:SS.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or re.search(r"\b(?:dnf|dns|dsq|did not)\b", text, re.I):
        return None
    match = re.search(r"(?<!\d)(\d{1,3})\s*[:.]\s*(\d{2})(?:\s*[:.]\s*(\d{1,2}))?(?!\d)", text)
    if not match:
        return None
    first, second, third = match.groups()
    first_i, second_i = int(first), int(second)
    if third is None:
        if second_i >= 60:
            return None
        return f"{first_i}:{second_i:02d}"
    third_i = int(third)
    if "." in match.group(0) and third_i < 100:
        # 07.54.23 is an old-site time with hundredths.
        if second_i >= 60:
            return None
        return f"{first_i}:{second_i:02d}"
    if first_i <= 23 and second_i < 60 and third_i < 60:
        return f"{first_i}:{second_i:02d}:{third_i:02d}" if first_i else f"{second_i}:{third_i:02d}"
    if second_i < 60 and third_i < 60:
        return f"{first_i}:{second_i:02d}:{third_i:02d}"
    return None


def time_to_seconds(value: Any) -> Optional[int]:
    parsed = parse_time(value)
    if not parsed:
        return None
    parts = [int(part) for part in parsed.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def calculate_difference(current: Any, previous: Any) -> Optional[str]:
    current_seconds, previous_seconds = time_to_seconds(current), time_to_seconds(previous)
    if current_seconds is None or previous_seconds is None:
        return None
    difference = current_seconds - previous_seconds
    sign = "-" if difference < 0 else "+"
    absolute = abs(difference)
    return "0:00" if difference == 0 else f"{sign}{absolute // 60}:{absolute % 60:02d}"


def _uid(row: Mapping[str, Any]) -> Optional[str]:
    value = _first(row, "ParticipantUid", "ParticipantUID", "ParticipantId", "ParticipantID", "DeltakerUid", "DeltakerUID", "DeltakerId", "DeltakerID", "CompetitorId", "CompetitorID", "PersonId", "PersonID", "Uid", "UID", "Id", "ID")
    return str(value) if value not in (None, "") else None


def _name(row: Mapping[str, Any]) -> str:
    # In the current EQ shape, the display name is specifically under
    # Deltaker.Utover.  Check this before flattened Navn from Klasse.Navn.
    outward = row.get("Utover")
    if isinstance(outward, Mapping):
        outward_name = _first(outward, "NavnFormatert", "Name", "Navn", "FullName")
        if outward_name:
            return str(outward_name).strip()
    name = _first(row, "Name", "NavnFormatert", "FullName", "DisplayName", "ParticipantName", "AthleteName")
    if not name and not isinstance(row.get("Klasse"), Mapping):
        name = _first(row, "Navn")
    if not name and isinstance(row.get("Deltaker"), str):
        name = row["Deltaker"]
    if name:
        return str(name).strip()
    first = _first(row, "FirstName", "GivenName", "Firstname", "Fornavn")
    last = _first(row, "LastName", "Surname", "Lastname", "FamilyName", "Etternavn")
    return " ".join(part for part in (str(first or "").strip(), str(last or "").strip()) if part)


def _class_text(row: Mapping[str, Any]) -> str:
    value = _first(row, "ClassName", "ClassDescription", "CategoryName", "Category", "ContestName", "GroupName", "Gender")
    if value is None:
        for key in ("Klasse", "Class"):
            nested = row.get(key)
            if isinstance(nested, Mapping):
                value = _first(nested, "Name", "Navn", "Description")
                if value:
                    break
            elif nested not in (None, ""):
                value = nested
    return str(value or "").strip()


def group_from_class(class_text: str, row: Optional[Mapping[str, Any]] = None) -> str:
    text = (class_text or "")
    if row:
        text += " " + str(_first(row, "Gender", "Sex", "Group", "Division") or "")
    lower = text.casefold()
    if any(token in lower for token in ("kvinner", "kvinne", "women", "female", "dame")):
        return "Dame"
    if "pluss" in lower or "plus" in lower:
        return "Pluss"
    return "Mann"


def parse_eq_rows(payload: Any, *, source: str = "result") -> List[Dict[str, Any]]:
    """Map EQ rows into a stable internal representation."""
    parsed: List[Dict[str, Any]] = []
    for original in _rows_from_payload(payload):
        row = _flatten_row(original)
        name = _name(row)
        if not name:
            continue
        class_text = _class_text(row)
        time_value = _first(row, "Time", "ResultTime", "FinishTime", "NetTime", "GunTime", "Result", "ResultValue", "TimeString", "Formatert", "Formatted", "FormattedResult")
        parsed_time = parse_time(time_value)
        # EQ Timing may expose 0:00 for a participant without a valid finish.
        # It must not count as a result or a personal best.
        if time_to_seconds(parsed_time) == 0:
            parsed_time = None
        parsed.append({
            "_uid": _uid(row),
            "_name_key": normalize_name(name),
            "Navn": name,
            "Tid": parsed_time,
            "Klasse": class_text,
            "Gruppe": group_from_class(class_text, row),
            "_source": source,
            "_raw": row,
        })
    return parsed


def merge_eq_rows(results: Sequence[Mapping[str, Any]], startlist: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Merge finished results with startlist rows, retaining starters without time."""
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str]] = []

    def key(row: Mapping[str, Any]) -> Tuple[str, str]:
        uid = row.get("_uid")
        return ("uid", str(uid)) if uid else ("name", str(row.get("_name_key") or normalize_name(row.get("Navn"))))

    for row in list(startlist) + list(results):
        item = dict(row)
        item_key = key(item)
        if item_key not in merged:
            merged[item_key] = item
            order.append(item_key)
            continue
        old = merged[item_key]
        # Result rows win for time/status, while startlist fills class/name.
        for field, value in item.items():
            if field == "_raw":
                continue
            if value not in (None, "") or old.get(field) in (None, ""):
                old[field] = value
    return [merged[item_key] for item_key in order]


def parse_history_html(html: str, current_year: int) -> Dict[str, Any]:
    """Extract best pre-current-year time and historical participation count."""
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: List[Tuple[int, str]] = []
    seen: set[Tuple[int, str]] = set()
    all_years_seen: set[int] = set()

    # Stoltzen embeds an authoritative year/final-time list in a commented
    # span. Reading it directly avoids confusing intermediate split times with
    # the participant's final time.
    year_times = re.search(
        r'id=["\']yeartimes["\'][^>]*>(.*?)</span>', html or "", re.IGNORECASE | re.DOTALL
    )
    if year_times:
        for year_text, time_text in re.findall(r"(20\d{2})\s*\|\s*(\d{1,3}[.:]\d{2})", year_times.group(1)):
            year = int(year_text)
            all_years_seen.add(year)
            history_time = parse_time(time_text)
            if history_time and year < current_year:
                candidates.append((year, history_time))
    else:
        containers = soup.select("#yeartimes, .yeartimes, #history, .history, #personal_best, #last_time, #participations, table")
        if not containers:
            containers = [soup]
        for container in containers:
            rows = container.find_all("tr") if getattr(container, "find_all", None) else []
            texts = [row.get_text(" ", strip=True) for row in rows] if rows else [container.get_text(" ", strip=True)]
            for text in texts:
                years = [int(year) for year in re.findall(r"\b(20\d{2})\b", text)]
                all_years_seen.update(years)
                times = [parse_time(match.group(0)) for match in re.finditer(r"(?<!\d)\d{1,3}[:.]\d{2}(?:[:.]\d{1,2})?(?!\d)", text)]
                times = [history_time for history_time in times if history_time]
                for year, history_time in zip(years, times):
                    if year < current_year and (year, history_time) not in seen:
                        seen.add((year, history_time))
                        candidates.append((year, history_time))

    best_year, best_time = None, None
    if candidates:
        best_year, best_time = min(candidates, key=lambda item: time_to_seconds(item[1]) or 10**9)
    explicit_count = None
    participation_node = soup.select_one("#participations")
    if participation_node:
        count_match = re.search(r"\b(\d+)\b", participation_node.get_text(" ", strip=True))
        if count_match:
            explicit_count = int(count_match.group(1))
    if explicit_count is not None:
        # A profile can already contain the race year (for example when
        # regression-testing 2025). Keep this value historical here because
        # build_output_rows adds the current finished race exactly once.
        current_or_future_entries = len({year for year in all_years_seen if year >= current_year})
        participation_count = max(0, explicit_count - current_or_future_entries)
    else:
        participation_count = len(candidates)
    return {"BesteTidligere": best_time, "BesteÅr": best_year,
            "Deltagelser": participation_count,
            "history": candidates}


class StoltzenHistory:
    def __init__(self, session: Optional[requests.Session] = None, timeout: int = DEFAULT_TIMEOUT,
                 result_urls: Sequence[str] = ()):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.base_url = "http://www.stoltzen.no"
        self.result_urls = tuple(result_urls)
        self._profile_index: Optional[Dict[str, str]] = None
        self._history_cache: Dict[Tuple[str, int], Dict[str, Any]] = {}

    def _get(self, url: str) -> Optional[str]:
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            if not getattr(response, "encoding", None):
                response.encoding = "utf-8"
            return response.text
        except requests.RequestException as exc:
            print(f"Stoltzen history request failed ({url}): {exc}", file=sys.stderr)
            return None

    def find_profile_url(self, name: str) -> Optional[str]:
        url = f"{self.base_url}/statistikk/?s={quote(name)}"
        html = self._get(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one("#participations, #personal_best, #yeartimes"):
            return url
        wanted = normalize_name(name)
        for anchor in soup.find_all("a", href=True):
            anchor_name = anchor.get_text(" ", strip=True)
            if normalize_name(anchor_name) == wanted:
                return urljoin(self.base_url, anchor["href"])
        # Search templates sometimes put the exact result name in a table row.
        for element in soup.find_all(string=True):
            if normalize_name(element.strip()) == wanted:
                parent = element.parent
                anchor = parent.find_parent("a", href=True) if parent else None
                if anchor:
                    return urljoin(self.base_url, anchor["href"])
        return None

    def _indexed_profile_url(self, name: str) -> Optional[str]:
        """Find a profile through earlier COWI result pages when available.

        This is both more accurate and cheaper than the legacy name search,
        especially when Stoltzen displays hits as ``Surname, Firstname`` or
        contains multiple people with the same name.
        """
        if self._profile_index is None:
            self._profile_index = {}
            for result_url in self.result_urls:
                html = self._get(result_url)
                if not html:
                    continue
                soup = BeautifulSoup(html, "html.parser")
                for anchor in soup.find_all("a", href=re.compile(r"stat\.php\?id=\d+")):
                    key = normalize_name(anchor.get_text(" ", strip=True))
                    if key:
                        self._profile_index[key] = urljoin(result_url, anchor["href"])
        return self._profile_index.get(normalize_name(name))

    def prepare(self) -> None:
        """Load the small historical result indexes before parallel lookups."""
        self._indexed_profile_url("")

    def _search_page(self, name: str) -> Tuple[Optional[str], Optional[str]]:
        """Return a profile URL, or the HTML when search itself is a profile."""
        search_url = f"{self.base_url}/statistikk/?s={quote(name)}"
        html = self._get(search_url)
        if not html:
            return None, None
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one("#participations, #personal_best, #yeartimes"):
            return search_url, html
        wanted = normalize_name(name)
        for anchor in soup.find_all("a", href=True):
            if normalize_name(anchor.get_text(" ", strip=True)) == wanted:
                return urljoin(self.base_url, anchor["href"]), None
        for element in soup.find_all(string=True):
            if normalize_name(element.strip()) == wanted:
                parent = element.parent
                anchor = parent.find_parent("a", href=True) if parent else None
                if anchor:
                    return urljoin(self.base_url, anchor["href"]), None
        return None, None

    def history_for(self, name: str, current_year: int) -> Dict[str, Any]:
        cache_key = (normalize_name(name), current_year)
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]
        profile_url = self._indexed_profile_url(name)
        direct_html = None
        if not profile_url:
            profile_url, direct_html = self._search_page(name)
        if not profile_url:
            result = {"BesteTidligere": None, "BesteÅr": None, "Deltagelser": 0}
            self._history_cache[cache_key] = result
            return result
        html = direct_html if direct_html is not None else self._get(profile_url)
        result = parse_history_html(html or "", current_year)
        self._history_cache[cache_key] = result
        return result


class EqtimingScraper:
    def __init__(self, session: Optional[requests.Session] = None, timeout: int = DEFAULT_TIMEOUT):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.base_url = "https://live.eqtiming.com"
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update({"User-Agent": "stoltzen-result-scraper/2026", "Accept": "application/json"})

    def fetch_json(self, url: str) -> Any:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def fetch_current(self, event_id: str, club: str) -> List[Dict[str, Any]]:
        cache_buster = int(time.time() * 1000)
        result_url = (f"{self.base_url}/api/Result/Search/{quote(str(event_id))}"
                      f"?count=9999&startAt=1&station=0&round=1&passes=false"
                      f"&justTimeData=true&query={quote(club)}&proxykey={cache_buster}")
        startlist_url = (f"{self.base_url}/api/Startlist/{quote(str(event_id))}/0"
                         f"?count=9999&startAt=1&query={quote(club)}&filter=&sortcols=")
        result_payload = self.fetch_json(result_url)
        startlist_payload = self.fetch_json(startlist_url)
        results = parse_eq_rows(result_payload, source="result")
        starts = parse_eq_rows(startlist_payload, source="startlist")
        query_key = normalize_name(club)
        def in_club(row: Mapping[str, Any]) -> bool:
            raw = _flatten_row(row.get("_raw", {}))
            value = _first(raw, "KlubbTeamFormatert", "Klubbnavn", "Club", "ClubName", "Team", "TeamName", "Klubb")
            if isinstance(value, Mapping):
                value = _first(value, "Navn", "Name", "Klubbnavn", "ClubName")
            return not value or query_key in normalize_name(value)
        results = [row for row in results if in_club(row)]
        starts = [row for row in starts if in_club(row)]
        return merge_eq_rows(results, starts)


def build_output_rows(eq_rows: Sequence[Mapping[str, Any]], current_year: int, history: Optional[StoltzenHistory] = None, no_history: bool = False, workers: int = 10) -> List[Dict[str, Any]]:
    """Enrich EQ rows and produce the repository's established CSV schema."""
    histories: Dict[str, Dict[str, Any]] = {}
    if history and not no_history:
        prepare = getattr(history, "prepare", None)
        if callable(prepare):
            prepare()
        names = {str(row.get("Navn")) for row in eq_rows if row.get("Navn")}
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(history.history_for, name, current_year): name for name in names}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    histories[normalize_name(name)] = future.result()
                except Exception as exc:
                    print(f"History parsing failed for {name}: {exc}", file=sys.stderr)

    output: List[Dict[str, Any]] = []
    for row in eq_rows:
        name = str(row.get("Navn") or "").strip()
        previous = histories.get(normalize_name(name), {})
        current = row.get("Tid")
        best = previous.get("BesteTidligere")
        output.append({
            "Gruppe": row.get("Gruppe") or group_from_class(str(row.get("Klasse") or "")),
            "Navn": name,
            "Tid": current,
            "Klasse": row.get("Klasse") or "",
            "Deltagelser": previous.get("Deltagelser", 0) + (1 if current else 0),
            "BesteTidligere": best,
            "BesteÅr": previous.get("BesteÅr"),
            "NyBestetid": bool(current and (not best or (time_to_seconds(current) is not None and time_to_seconds(best) is not None and time_to_seconds(current) < time_to_seconds(best)))),
            "Differanse": calculate_difference(current, best),
        })
    group_order = {"Dame": 1, "Mann": 2, "Pluss": 3}
    output.sort(key=lambda row: (group_order.get(row["Gruppe"], 4), time_to_seconds(row["Tid"]) if row["Tid"] else 10**9, row["Navn"].casefold()))
    return output


def write_csv(rows: Iterable[Mapping[str, Any]], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Stoltzen 2026 results from EQ Timing")
    parser.add_argument("--output", "-o", default="results.csv", help="CSV output path")
    parser.add_argument("--event-id", default=DEFAULT_EVENT_ID, help="EQ Timing event id")
    parser.add_argument("--club", default=DEFAULT_CLUB, help="Club/search query")
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR, help="Current race year")
    parser.add_argument("--no-history", action="store_true", help="Do not query stoltzen.no history")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    args = parser.parse_args(argv)
    try:
        eq = EqtimingScraper(timeout=args.timeout)
        current = eq.fetch_current(args.event_id, args.club)
        if not current:
            print("No EQ Timing participants found", file=sys.stderr)
        history_result_urls: Sequence[str] = ()
        if normalize_name(args.club) == normalize_name(DEFAULT_CLUB):
            history_result_urls = (
                f"http://www.stoltzen.no/resultater/{args.year - 1}/resklubb_16.html",
                f"http://www.stoltzen.no/resultater/{args.year - 2}/resklubb_16.html",
            )
        history = StoltzenHistory(timeout=args.timeout, result_urls=history_result_urls)
        rows = build_output_rows(current, args.year, history, args.no_history)
        write_csv(rows, args.output)
        print(f"Wrote {len(rows)} participants to {args.output}")
        return 0
    except requests.RequestException as exc:
        print(f"EQ Timing request failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
