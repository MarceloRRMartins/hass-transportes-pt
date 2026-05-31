"""Metro de Lisboa provider with real-time line status and wait times."""

from __future__ import annotations

import logging
import re
from enum import Enum

import aiohttp

from . import Alert, Arrival
from .gtfs_base import GtfsProvider

_LOGGER = logging.getLogger(__name__)

# Line status API (returns HTML with per-line operational status)
_LINE_STATUS_URL = "https://www.metrolisboa.pt/wp-json/ml/v1/estado_linhas_mobile"

# Wait times API (returns estimated wait times per station)
_WAIT_TIMES_URL = "https://www.metrolisboa.pt/wp-json/ml/v1/tempos_espera/"


class LineStatus(Enum):
    """Operational status of a Metro line."""

    NORMAL = "normal"
    INTERRUPTED = "interrompida"
    PARTIAL = "parcialmente interrompida"
    REDUCED = "circulação condicionada"
    CLOSED = "encerrada"

    @classmethod
    def from_text(cls, text: str) -> LineStatus:
        """Parse status text into enum (case-insensitive)."""
        normalized = text.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        # Partial match for variants like "parcialmente interrompida entre X e Y"
        if "interrompida" in normalized and "parcialmente" in normalized:
            return cls.PARTIAL
        if "interrompida" in normalized:
            return cls.INTERRUPTED
        if "condicionada" in normalized:
            return cls.REDUCED
        if "encerrada" in normalized:
            return cls.CLOSED
        return cls.NORMAL


# Maps Metro line names to GTFS route identifiers
_LINE_ROUTE_MAP: dict[str, str] = {
    "azul": "AZ",
    "amarela": "AM",
    "verde": "VD",
    "vermelha": "VM",
}

# Maps line key to color (for UI rendering)
_LINE_COLOR_MAP: dict[str, str] = {
    "azul": "#0060AA",
    "amarela": "#F4C800",
    "verde": "#00A84F",
    "vermelha": "#EE1C25",
}

# Severity ordering for sorting alerts
_SEVERITY_ORDER: dict[LineStatus, int] = {
    LineStatus.CLOSED: 0,
    LineStatus.INTERRUPTED: 1,
    LineStatus.PARTIAL: 2,
    LineStatus.REDUCED: 3,
    LineStatus.NORMAL: 4,
}


class MetroLisboaProvider(GtfsProvider):
    """Provider for Metropolitano de Lisboa with real-time line status.

    Features:
        - GTFS Static for scheduled arrivals
        - Real-time line operational status (disruption alerts)
        - Estimated wait times per station (when available from API)
    """

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "metro_lisboa"

    @property
    def name(self) -> str:
        return "Metro de Lisboa"

    @property
    def gtfs_url(self) -> str:
        return "https://www.metrolisboa.pt/google_transit/googleTransit.zip"

    @property
    def gtfs_headers(self) -> dict[str, str]:
        # Metro de Lisboa blocks requests without User-Agent (returns 403)
        return {"User-Agent": "HomeAssistant/TransportesPT"}

    async def async_get_arrivals(self, stop_id: str) -> list[Arrival]:
        """Get arrivals for a Metro stop.

        Tries the wait times API first for real-time estimates,
        falling back to GTFS static schedule.
        """
        rt_arrivals = await self._get_wait_times(stop_id)
        if rt_arrivals:
            return rt_arrivals

        # Fall back to GTFS static schedule
        return await super().async_get_arrivals(stop_id)

    async def _get_wait_times(self, stop_id: str) -> list[Arrival] | None:
        """Fetch estimated wait times from Metro de Lisboa API.

        The API returns per-station wait times when available.
        Returns None if the API doesn't have data for this stop.
        """
        try:
            async with self.session.get(
                f"{_WAIT_TIMES_URL}{stop_id}",
                timeout=aiohttp.ClientTimeout(total=10),
                headers=self.gtfs_headers,
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

            if not data or not isinstance(data, list):
                return None

            arrivals: list[Arrival] = []
            for entry in data:
                destination = entry.get("destino", "")
                wait_secs = entry.get("tempoChegada1")
                line_id = entry.get("linha", "")

                if wait_secs is None:
                    continue

                # Convert wait seconds to minutes string
                wait_min = max(0, int(wait_secs) // 60)
                arrivals.append(
                    Arrival(
                        line_id=line_id,
                        line_name=self._line_display_name(line_id),
                        destination=destination,
                        estimated_arrival=f"{wait_min} min",
                        scheduled_arrival=None,
                        estimated_arrival_unix=None,
                        scheduled_arrival_unix=None,
                        vehicle_id=None,
                        trip_id=None,
                    )
                )

                # Second train estimate if available
                wait_secs_2 = entry.get("tempoChegada2")
                if wait_secs_2 is not None:
                    wait_min_2 = max(0, int(wait_secs_2) // 60)
                    arrivals.append(
                        Arrival(
                            line_id=line_id,
                            line_name=self._line_display_name(line_id),
                            destination=destination,
                            estimated_arrival=f"{wait_min_2} min",
                            scheduled_arrival=None,
                            estimated_arrival_unix=None,
                            scheduled_arrival_unix=None,
                            vehicle_id=None,
                            trip_id=None,
                        )
                    )

            return arrivals if arrivals else None
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Metro Lisboa wait times error for %s: %s", stop_id, err)
            return None

    @staticmethod
    def _line_display_name(line_id: str) -> str:
        """Convert a line ID to display name."""
        names = {
            "AZ": "Linha Azul",
            "AM": "Linha Amarela",
            "VD": "Linha Verde",
            "VM": "Linha Vermelha",
        }
        return names.get(line_id.upper(), f"Linha {line_id}")

    async def async_get_alerts(self) -> list[Alert]:
        """Get real-time line status from Metro de Lisboa API.

        Returns alerts for lines that are NOT operating normally.
        Alerts are sorted by severity (most critical first).
        """
        try:
            async with self.session.get(
                _LINE_STATUS_URL,
                timeout=aiohttp.ClientTimeout(total=15),
                headers=self.gtfs_headers,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Metro Lisboa status API returned %s", resp.status)
                    return []
                html = await resp.text()

            return _parse_line_status(html)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Metro Lisboa line status error: %s", err)
            return []


def _parse_line_status(html: str) -> list[Alert]:
    """Parse the Metro de Lisboa line status HTML into alerts.

    Only returns alerts for lines NOT in 'normal' status.
    Results are sorted by severity (closed > interrupted > partial > reduced).
    """
    alerts: list[Alert] = []

    # Pattern: nomeLinhaMobile with line name, followed by circ_mobile with status
    pattern = re.compile(
        r'class="nomeLinhaMobile"\s*>([^<]+)</div>\s*'
        r'<div\s+class="circ_mobile">([^<]+)</div>',
        re.IGNORECASE,
    )

    # Pattern for detailed status per line
    detail_pattern = re.compile(
        r'id="det(\w+)Mobile"[^>]*>.*?Estado da Linha:?\s*</strong>\s*([^<.]+)',
        re.IGNORECASE | re.DOTALL,
    )

    # Extract detailed status messages
    details: dict[str, str] = {}
    for match in detail_pattern.finditer(html):
        line_key = match.group(1).lower()  # e.g., "azul", "amarela", "verd", "verm"
        detail_status = match.group(2).strip()
        details[line_key] = detail_status

    for match in pattern.finditer(html):
        line_name = match.group(1).strip()  # e.g., "Linha Azul"
        status_text = match.group(2).strip()  # e.g., "normal" or disruption text

        line_status = LineStatus.from_text(status_text)
        if line_status == LineStatus.NORMAL:
            continue

        # Determine route_id from line name
        line_key = line_name.lower().replace("linha ", "").strip()
        route_id = _LINE_ROUTE_MAP.get(line_key, line_key.upper())

        # Get detailed description if available
        detail_key = line_key[:4]  # "azul", "amar", "verd", "verm"
        description = details.get(detail_key, status_text)

        alerts.append(
            Alert(
                alert_id=f"metro_lisboa_{line_key}_status",
                title=f"{line_name}: {status_text}",
                description=description,
                affected_lines=[route_id],
                url="https://www.metrolisboa.pt/viajar/",
            )
        )

    # Sort by severity (most critical first)
    alerts.sort(key=lambda a: _SEVERITY_ORDER.get(
        LineStatus.from_text(a.title.split(": ", 1)[-1]) if ": " in a.title else LineStatus.NORMAL,
        4,
    ))

    return alerts
