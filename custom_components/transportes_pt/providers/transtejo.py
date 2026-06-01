"""Transtejo Soflusa (TTSL) transit provider with real-time departures."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any

import aiohttp

from ..const import TTSL_BASE_URL, TTSL_PAGE_ID
from . import (
    Alert,
    Arrival,
    Line,
    Stop,
    TransitProvider,
    VehiclePosition,
)

_LOGGER = logging.getLogger(__name__)

# Hardcoded terminals with GPS coordinates (from OpenStreetMap)
TERMINALS: dict[str, dict[str, Any]] = {
    "cais_do_sodre": {
        "name": "Cais do Sodré",
        "latitude": 38.7063,
        "longitude": -9.1443,
    },
    "cacilhas": {
        "name": "Cacilhas",
        "latitude": 38.6870,
        "longitude": -9.1498,
    },
    "terreiro_do_paco": {
        "name": "Terreiro do Paço",
        "latitude": 38.7082,
        "longitude": -9.1365,
    },
    "barreiro": {
        "name": "Barreiro",
        "latitude": 38.6634,
        "longitude": -9.0720,
    },
    "seixal": {
        "name": "Seixal",
        "latitude": 38.6401,
        "longitude": -9.1010,
    },
    "montijo": {
        "name": "Montijo",
        "latitude": 38.7075,
        "longitude": -8.9732,
    },
    "trafaria": {
        "name": "Trafaria",
        "latitude": 38.6668,
        "longitude": -9.2362,
    },
    "porto_brandao": {
        "name": "Porto Brandão",
        "latitude": 38.6738,
        "longitude": -9.2108,
    },
}

# Hardcoded lines (routes)
LINES: list[dict[str, str]] = [
    {
        "id": "cacilhas_cais_do_sodre",
        "short_name": "Cacilhas",
        "long_name": "Cacilhas - Cais do Sodré",
        "color": "#FFD700",
    },
    {
        "id": "barreiro_terreiro_do_paco",
        "short_name": "Barreiro",
        "long_name": "Barreiro - Terreiro do Paço",
        "color": "#1E90FF",
    },
    {
        "id": "seixal_cais_do_sodre",
        "short_name": "Seixal",
        "long_name": "Seixal - Cais do Sodré",
        "color": "#32CD32",
    },
    {
        "id": "montijo_cais_do_sodre",
        "short_name": "Montijo",
        "long_name": "Montijo - Cais do Sodré",
        "color": "#FF6347",
    },
    {
        "id": "trafaria_porto_brandao",
        "short_name": "Trafaria",
        "long_name": "Trafaria - Porto Brandão - Belém",
        "color": "#9370DB",
    },
]

# Map terminal display names to stop IDs
_TERMINAL_NAME_MAP: dict[str, str] = {
    "CAIS DO SODRÉ": "cais_do_sodre",
    "CAIS DO SODRE": "cais_do_sodre",
    "CACILHAS": "cacilhas",
    "TERREIRO DO PAÇO": "terreiro_do_paco",
    "TERREIRO DO PACO": "terreiro_do_paco",
    "BARREIRO": "barreiro",
    "SEIXAL": "seixal",
    "MONTIJO": "montijo",
    "TRAFARIA": "trafaria",
    "PORTO BRANDÃO": "porto_brandao",
    "PORTO BRANDAO": "porto_brandao",
}


def _normalize_terminal(name: str) -> str:
    """Normalize a terminal name to a stop_id."""
    return _TERMINAL_NAME_MAP.get(name.strip().upper(), "")


def _derive_line_id(origin: str, destination: str) -> str:
    """Derive a line ID from origin and destination terminals."""
    origin_id = _normalize_terminal(origin)
    dest_id = _normalize_terminal(destination)

    for line in LINES:
        line_id = line["id"]
        if origin_id in line_id or dest_id in line_id:
            return line_id
    # Fallback: combine origin and destination
    if origin_id and dest_id:
        return f"{origin_id}_{dest_id}"
    return "unknown"


def _derive_line_name(origin: str, destination: str) -> str:
    """Derive a human-readable line name."""
    return f"{origin.strip().title()} - {destination.strip().title()}"


class _DepartureParser(HTMLParser):
    """Parse the TTSL departures HTML table."""

    def __init__(self) -> None:
        """Initialize parser state."""
        super().__init__()
        self.departures: list[dict[str, str]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_row: list[str] = []
        self._current_data = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle opening tags."""
        if tag == "table":
            attr_dict = dict(attrs)
            if "partidas" in (attr_dict.get("class") or ""):
                self._in_table = True
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._current_row = []
        elif tag == "td" and self._in_row:
            self._in_cell = True
            self._current_data = ""

    def handle_endtag(self, tag: str) -> None:
        """Handle closing tags."""
        if tag == "table" and self._in_table:
            self._in_table = False
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if len(self._current_row) >= 4:
                self.departures.append(
                    {
                        "time": self._current_row[0].strip(),
                        "terminal": self._current_row[1].strip(),
                        "destination": self._current_row[2].strip(),
                        "status": self._current_row[3].strip(),
                        "gate": self._current_row[4].strip()
                        if len(self._current_row) > 4
                        else "",
                    }
                )
        elif tag == "td" and self._in_cell:
            self._in_cell = False
            self._current_row.append(self._current_data)

    def handle_data(self, data: str) -> None:
        """Handle text content."""
        if self._in_cell:
            self._current_data += data


def _parse_departures(html: str) -> list[dict[str, str]]:
    """Parse the HTML departures table and return structured data."""
    parser = _DepartureParser()
    parser.feed(html)
    return parser.departures


def _time_to_unix(time_str: str, now: datetime | None = None) -> int | None:
    """Convert HH:MM time string to today's unix timestamp.

    If the time is more than 6 hours behind current time, assume next day.
    """
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
    except (ValueError, IndexError):
        return None

    if now is None:
        now = datetime.now(tz=timezone.utc)
    departure = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If departure seems to be in the past by more than 6 hours, it's tomorrow
    diff = (now - departure).total_seconds()
    if diff > 6 * 3600:
        departure = departure + timedelta(days=1)

    return int(departure.timestamp())


class TranstejoProvider(TransitProvider):
    """Provider for Transtejo Soflusa real-time ferry departures."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the provider."""
        self._session = session
        self._owns_session = session is None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Return the active session."""
        assert self._session is not None
        return self._session

    @property
    def provider_id(self) -> str:
        """Unique identifier for this provider."""
        return "transtejo"

    @property
    def name(self) -> str:
        """Human-readable name."""
        return "Transtejo Soflusa"

    async def async_init(self) -> None:
        """Initialize the provider session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

    async def async_close(self) -> None:
        """Close the provider session."""
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    async def async_test_connection(self) -> bool:
        """Test if the TTSL API is reachable."""
        try:
            url = f"{TTSL_BASE_URL}/pages/{TTSL_PAGE_ID}?_fields=id"
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, TimeoutError):
            return False

    async def async_get_arrivals(self, stop_id: str) -> list[Arrival]:
        """Get real-time departures for a terminal.

        Fetches the TTSL homepage content from WordPress REST API,
        parses the HTML departures table, and filters by terminal.
        """
        html = await self._fetch_departures_html()
        if not html:
            return []

        departures = _parse_departures(html)
        arrivals: list[Arrival] = []

        for dep in departures:
            # Skip departed ferries
            status_val = dep["status"].lower()
            if status_val == "partiu":
                continue

            # Filter by terminal (origin)
            terminal_id = _normalize_terminal(dep["terminal"])
            if terminal_id != stop_id:
                continue

            # Compute ETA
            if status_val == "embarque":
                # Currently boarding — effectively 0 min
                estimated_unix = int(datetime.now(tz=timezone.utc).timestamp())
            else:
                estimated_unix = _time_to_unix(dep["time"])

            line_id = _derive_line_id(dep["terminal"], dep["destination"])
            line_name = _derive_line_name(dep["terminal"], dep["destination"])

            arrivals.append(
                Arrival(
                    line_id=line_id,
                    line_name=line_name,
                    destination=dep["destination"].title(),
                    estimated_arrival=dep["time"],
                    scheduled_arrival=dep["time"],
                    estimated_arrival_unix=estimated_unix,
                    scheduled_arrival_unix=_time_to_unix(dep["time"]),
                    vehicle_id=None,
                    trip_id=f"{dep['status']}|sala:{dep['gate']}"
                    if dep["gate"]
                    else dep["status"],
                )
            )

        return arrivals

    async def async_get_alerts(self) -> list[Alert]:
        """Get service alerts from TTSL WordPress avisos."""
        url = f"{TTSL_BASE_URL}/avisos?per_page=10&_fields=id,title,content,date,link"
        data = await self._api_get(url)
        if not data:
            return []

        alerts: list[Alert] = []
        for item in data:
            title_obj = item.get("title", {})
            content_obj = item.get("content", {})

            title = (
                title_obj.get("rendered", "")
                if isinstance(title_obj, dict)
                else str(title_obj)
            )
            description = (
                content_obj.get("rendered", "")
                if isinstance(content_obj, dict)
                else str(content_obj)
            )

            # Strip HTML tags for cleaner display
            description = self._strip_html(description)
            title = self._strip_html(title)

            alerts.append(
                Alert(
                    alert_id=str(item.get("id", "")),
                    title=title,
                    description=description[:500],
                    affected_lines=[],
                    affected_stops=[],
                    start_time=item.get("date"),
                    end_time=None,
                    url=item.get("link"),
                )
            )

        return alerts

    async def async_get_vehicles(
        self, line_ids: list[str] | None = None
    ) -> list[VehiclePosition]:
        """Get vehicle positions — not available for ferries."""
        return []

    async def async_get_stops(self, search: str | None = None) -> list[Stop]:
        """Get TTSL terminals."""
        stops: list[Stop] = []
        for stop_id, info in TERMINALS.items():
            name = info["name"]
            if search and search.lower() not in name.lower():
                continue
            stops.append(
                Stop(
                    stop_id=stop_id,
                    name=name,
                    latitude=info["latitude"],
                    longitude=info["longitude"],
                    lines=[line["id"] for line in LINES if stop_id in line["id"]],
                    municipality="Lisboa"
                    if stop_id in ("cais_do_sodre", "terreiro_do_paco")
                    else "Almada/Margem Sul",
                )
            )
        return stops

    async def async_get_lines(self) -> list[Line]:
        """Get TTSL lines (routes)."""
        return [
            Line(
                line_id=line["id"],
                short_name=line["short_name"],
                long_name=line["long_name"],
                color=line.get("color"),
            )
            for line in LINES
        ]

    async def _fetch_departures_html(self) -> str | None:
        """Fetch the departures page content from WordPress REST API."""
        url = f"{TTSL_BASE_URL}/pages/{TTSL_PAGE_ID}?_fields=content"
        data = await self._api_get(url)
        if not data:
            return None

        content = data.get("content", {})
        if isinstance(content, dict):
            return content.get("rendered", "")
        return str(content) if content else None

    async def _api_get(self, url: str) -> Any:
        """Make a GET request to the TTSL API."""
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "TTSL API returned %s for %s", resp.status, url
                    )
                    return None
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Error fetching %s: %s", url, err)
            return None

    @staticmethod
    def _strip_html(text: str) -> str:
        """Strip HTML tags from a string."""

        class _TagStripper(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []

            def handle_data(self, data: str) -> None:
                self.parts.append(data)

        stripper = _TagStripper()
        stripper.feed(text)
        return "".join(stripper.parts).strip()
