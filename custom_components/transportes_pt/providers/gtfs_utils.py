"""GTFS Static data parser utilities."""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any


@dataclass
class GtfsData:
    """Parsed GTFS static data."""

    agencies: dict[str, dict[str, str]] = field(default_factory=dict)
    stops: dict[str, dict[str, str]] = field(default_factory=dict)
    routes: dict[str, dict[str, str]] = field(default_factory=dict)
    trips: dict[str, dict[str, str]] = field(default_factory=dict)
    stop_times: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    calendar: dict[str, dict[str, str]] = field(default_factory=dict)
    calendar_dates: list[dict[str, str]] = field(default_factory=list)
    # Reverse index: stop_id -> list of route_ids serving it
    stop_routes: dict[str, set[str]] = field(default_factory=dict)


def parse_gtfs_zip(data: bytes) -> GtfsData:
    """Parse a GTFS ZIP file into memory.

    Args:
        data: Raw bytes of the GTFS ZIP file.

    Returns:
        GtfsData with all parsed tables.
    """
    gtfs = GtfsData()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()

        if "agency.txt" in names:
            gtfs.agencies = _parse_keyed(zf, "agency.txt", "agency_id")

        if "stops.txt" in names:
            gtfs.stops = _parse_keyed(zf, "stops.txt", "stop_id")

        if "routes.txt" in names:
            gtfs.routes = _parse_keyed(zf, "routes.txt", "route_id")

        if "trips.txt" in names:
            gtfs.trips = _parse_keyed(zf, "trips.txt", "trip_id")

        if "stop_times.txt" in names:
            gtfs.stop_times = _parse_stop_times(zf)

        if "calendar.txt" in names:
            gtfs.calendar = _parse_keyed(zf, "calendar.txt", "service_id")

        if "calendar_dates.txt" in names:
            gtfs.calendar_dates = _parse_list(zf, "calendar_dates.txt")

        # Build reverse index: stop_id -> route_ids
        _build_stop_routes_index(gtfs)

    return gtfs


def _parse_keyed(zf: zipfile.ZipFile, filename: str, key_field: str) -> dict[str, dict[str, str]]:
    """Parse a GTFS CSV file into a dict keyed by key_field."""
    result: dict[str, dict[str, str]] = {}
    with zf.open(filename) as f:
        # Handle BOM
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        reader = csv.DictReader(text)
        for row in reader:
            key = row.get(key_field, "")
            if key:
                result[key] = dict(row)
    return result


def _parse_list(zf: zipfile.ZipFile, filename: str) -> list[dict[str, str]]:
    """Parse a GTFS CSV file into a list of dicts."""
    result: list[dict[str, str]] = []
    with zf.open(filename) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        reader = csv.DictReader(text)
        for row in reader:
            result.append(dict(row))
    return result


def _parse_stop_times(zf: zipfile.ZipFile) -> dict[str, list[dict[str, str]]]:
    """Parse stop_times.txt grouped by stop_id for efficient lookup."""
    result: dict[str, list[dict[str, str]]] = {}
    with zf.open("stop_times.txt") as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        reader = csv.DictReader(text)
        for row in reader:
            stop_id = row.get("stop_id", "")
            if stop_id:
                result.setdefault(stop_id, []).append(dict(row))
    return result


def _build_stop_routes_index(gtfs: GtfsData) -> None:
    """Build a reverse index from stop_id to route_ids serving that stop."""
    # trip_id -> route_id mapping
    trip_to_route: dict[str, str] = {}
    for trip_id, trip_data in gtfs.trips.items():
        trip_to_route[trip_id] = trip_data.get("route_id", "")

    for stop_id, stop_time_list in gtfs.stop_times.items():
        routes: set[str] = set()
        for st in stop_time_list:
            trip_id = st.get("trip_id", "")
            route_id = trip_to_route.get(trip_id, "")
            if route_id:
                routes.add(route_id)
        gtfs.stop_routes[stop_id] = routes


def is_service_active(gtfs: GtfsData, service_id: str, check_date: date) -> bool:
    """Check if a service_id is active on a given date.

    Considers both calendar.txt (weekly schedule) and calendar_dates.txt (exceptions).
    """
    # Check calendar_dates exceptions first
    date_str = check_date.strftime("%Y%m%d")
    for cd in gtfs.calendar_dates:
        if cd.get("service_id") == service_id and cd.get("date") == date_str:
            exception_type = cd.get("exception_type", "")
            if exception_type == "1":
                return True  # Service added
            if exception_type == "2":
                return False  # Service removed

    # Check regular calendar
    cal = gtfs.calendar.get(service_id)
    if not cal:
        return False

    # Check date range
    start = cal.get("start_date", "")
    end = cal.get("end_date", "")
    if start and end:
        try:
            start_date = datetime.strptime(start, "%Y%m%d").date()
            end_date = datetime.strptime(end, "%Y%m%d").date()
            if check_date < start_date or check_date > end_date:
                return False
        except ValueError:
            pass

    # Check day of week
    day_names = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    day_name = day_names[check_date.weekday()]
    return cal.get(day_name, "0") == "1"


def parse_gtfs_time(time_str: str) -> tuple[int, int, int]:
    """Parse a GTFS time string (HH:MM:SS) which can exceed 24h.

    Returns (hours, minutes, seconds) tuple.
    """
    parts = time_str.strip().split(":")
    if len(parts) != 3:
        return (0, 0, 0)
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def gtfs_time_to_seconds(time_str: str) -> int:
    """Convert GTFS time to seconds since midnight."""
    h, m, s = parse_gtfs_time(time_str)
    return h * 3600 + m * 60 + s


def get_scheduled_arrivals(
    gtfs: GtfsData, stop_id: str, now: datetime, max_results: int = 10
) -> list[dict[str, Any]]:
    """Get upcoming scheduled arrivals for a stop.

    Args:
        gtfs: Parsed GTFS data.
        stop_id: The stop to get arrivals for.
        now: Current datetime (timezone-aware or naive).
        max_results: Maximum number of arrivals to return.

    Returns:
        List of arrival dicts with keys: line_id, line_name, destination,
        scheduled_arrival (ISO string), trip_id.
    """
    stop_times_for_stop = gtfs.stop_times.get(stop_id, [])
    if not stop_times_for_stop:
        return []

    today = now.date()
    current_seconds = now.hour * 3600 + now.minute * 60 + now.second

    # Collect upcoming arrivals for today and tomorrow (for after-midnight services)
    candidates: list[tuple[int, dict[str, str]]] = []

    for st in stop_times_for_stop:
        trip_id = st.get("trip_id", "")
        trip = gtfs.trips.get(trip_id)
        if not trip:
            continue

        service_id = trip.get("service_id", "")
        arrival_time_str = st.get("arrival_time", st.get("departure_time", ""))
        if not arrival_time_str:
            continue

        arrival_seconds = gtfs_time_to_seconds(arrival_time_str)

        # GTFS times > 24:00:00 are next-day services from the previous day's trip
        if arrival_seconds >= 86400:
            # This belongs to yesterday's service running into today
            check_date = today - timedelta(days=1)
            effective_seconds = arrival_seconds - 86400
        else:
            check_date = today
            effective_seconds = arrival_seconds

        # Only future arrivals
        if effective_seconds <= current_seconds and check_date == today:
            continue
        # For yesterday's trips running into today, they're valid
        if check_date == today - timedelta(days=1) and effective_seconds <= current_seconds:
            continue

        if not is_service_active(gtfs, service_id, check_date):
            continue

        # Calculate seconds from now
        if check_date == today:
            seconds_until = effective_seconds - current_seconds
        else:
            # After-midnight service from yesterday
            seconds_until = effective_seconds - current_seconds
            if seconds_until < 0:
                continue

        candidates.append((seconds_until, st))

    # Also check tomorrow's early services
    tomorrow = today + timedelta(days=1)
    for st in stop_times_for_stop:
        trip_id = st.get("trip_id", "")
        trip = gtfs.trips.get(trip_id)
        if not trip:
            continue

        service_id = trip.get("service_id", "")
        arrival_time_str = st.get("arrival_time", st.get("departure_time", ""))
        if not arrival_time_str:
            continue

        arrival_seconds = gtfs_time_to_seconds(arrival_time_str)
        if arrival_seconds >= 86400:
            continue  # Already handled above

        if not is_service_active(gtfs, service_id, tomorrow):
            continue

        seconds_until = (86400 - current_seconds) + arrival_seconds
        candidates.append((seconds_until, st))

    # Sort by time and take top results
    candidates.sort(key=lambda x: x[0])
    candidates = candidates[:max_results]

    # Build arrival objects
    arrivals: list[dict[str, Any]] = []
    for seconds_until, st in candidates:
        trip_id = st.get("trip_id", "")
        trip = gtfs.trips.get(trip_id, {})
        route_id = trip.get("route_id", "")
        route = gtfs.routes.get(route_id, {})

        # Calculate arrival datetime
        arrival_dt = now + timedelta(seconds=seconds_until)

        arrivals.append(
            {
                "line_id": route_id,
                "line_name": route.get("route_short_name", route.get("route_long_name", route_id)),
                "destination": trip.get("trip_headsign", route.get("route_long_name", "")),
                "scheduled_arrival": arrival_dt.isoformat(),
                "scheduled_arrival_unix": int(arrival_dt.timestamp()),
                "trip_id": trip_id,
            }
        )

    return arrivals
