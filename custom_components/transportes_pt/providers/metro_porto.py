"""Metro do Porto provider with real-time line status alerts."""

from __future__ import annotations

import logging
import re
from enum import Enum

import aiohttp

from . import Alert
from .gtfs_base import GtfsProvider

_LOGGER = logging.getLogger(__name__)

# Homepage URL used to scrape "Estado das Linhas" widget
_HOMEPAGE_URL = "https://www.metrodoporto.pt/pages/1"


class LineStatus(Enum):
    """Operational status of a Metro do Porto line."""

    OK = "ok"
    CONDITIONED = "condicionada"
    INTERRUPTED = "interrompida"

    @classmethod
    def from_text(cls, text: str) -> LineStatus:
        """Parse status text into enum (case-insensitive)."""
        normalized = text.strip().lower()
        if "condicionada" in normalized:
            return cls.CONDITIONED
        if "interrompida" in normalized:
            return cls.INTERRUPTED
        return cls.OK


# Severity ordering for sorting alerts (lower = more critical)
_SEVERITY_ORDER: dict[LineStatus, int] = {
    LineStatus.INTERRUPTED: 0,
    LineStatus.CONDITIONED: 1,
    LineStatus.OK: 2,
}

# Maps route descriptions to line letter and color
_LINE_INFO: dict[str, tuple[str, str, str]] = {
    # (line_letter, color_hex, short_name)
    "Estádio do Dragão - Sr. de Matosinhos": ("A", "#2F9AC4", "Linha A"),
    "Estádio do Dragão - Póvoa de Varzim": ("B", "#E31937", "Linha B"),
    "Campanhã - ISMAI": ("C", "#6DC24B", "Linha C"),
    "Hospital S. João - Vila d'Este": ("D", "#F5C518", "Linha D"),
    "Trindade - Aeroporto": ("E", "#9B5FC0", "Linha E"),
    "Fânzeres - Senhora da Hora": ("F", "#ED8B00", "Linha F"),
}


class MetroPortoProvider(GtfsProvider):
    """Provider for Metro do Porto with real-time line status.

    Features:
        - GTFS Static for scheduled arrivals
        - Real-time line operational status (scraped from homepage)
    """

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "metro_porto"

    @property
    def name(self) -> str:
        return "Metro do Porto"

    @property
    def gtfs_url(self) -> str:
        return (
            "https://www.metrodoporto.pt/metrodoporto/uploads/document"
            "/file/794/google_transit_07_04_2026.zip"
        )

    @property
    def gtfs_cache_ttl(self) -> int:
        # Metro Porto updates infrequently
        return 172800  # 48h

    async def async_get_alerts(self) -> list[Alert]:
        """Get real-time line status from Metro do Porto homepage.

        Scrapes the 'Estado das Linhas' widget and returns alerts
        for lines that are NOT operating normally.
        Alerts are sorted by severity (most critical first).
        """
        try:
            async with self.session.get(
                _HOMEPAGE_URL,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "HomeAssistant/TransportesPT"},
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Metro Porto homepage returned %s", resp.status)
                    return []
                html = await resp.text()

            return _parse_line_status(html)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Metro Porto line status error: %s", err)
            return []


def _parse_line_status(html: str) -> list[Alert]:
    """Parse the Metro do Porto homepage HTML for line status alerts.

    Looks for the 'Estado das Linhas' section and extracts the status
    of each line. Only returns alerts for lines NOT in 'Ok' status.
    Results are sorted by severity (interrupted > conditioned).
    """
    alerts: list[Alert] = []

    # The homepage renders line status as heading blocks:
    # <h4>Route description</h4> followed by status text (Ok / Condicionada)
    # and optionally a link to a news article about the disruption.
    #
    # Pattern matches the route name and the status/link after it.
    pattern = re.compile(
        r"<h4[^>]*>\s*([^<]+?)\s*</h4>\s*"
        r"(?:<a[^>]*href=\"([^\"]+)\"[^>]*>)?\s*"
        r"(Ok|Condicionada|Interrompida)\s*"
        r"(?:</a>)?",
        re.IGNORECASE,
    )

    for match in pattern.finditer(html):
        route_desc = match.group(1).strip()
        news_url = match.group(2)  # May be None if status is "Ok"
        status_text = match.group(3).strip()

        line_status = LineStatus.from_text(status_text)
        if line_status == LineStatus.OK:
            continue

        line_info = _LINE_INFO.get(route_desc)
        if line_info:
            line_letter, _color, short_name = line_info
        else:
            line_letter = route_desc[:3].upper()
            short_name = route_desc

        full_url = (
            f"https://www.metrodoporto.pt{news_url}"
            if news_url and news_url.startswith("/")
            else news_url
        )

        alerts.append(
            Alert(
                alert_id=f"metro_porto_{line_letter.lower()}_status",
                title=f"{short_name} ({route_desc}): {status_text}",
                description=f"Linha {line_letter} - {status_text}",
                affected_lines=[line_letter],
                url=full_url,
            )
        )

    # Sort by severity (most critical first)
    alerts.sort(key=lambda a: _SEVERITY_ORDER.get(
        LineStatus.from_text(a.title.rsplit(": ", 1)[-1]) if ": " in a.title else LineStatus.OK,
        2,
    ))

    return alerts
