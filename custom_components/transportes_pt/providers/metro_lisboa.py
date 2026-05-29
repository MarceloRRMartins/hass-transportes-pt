"""Metro de Lisboa provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class MetroLisboaProvider(GtfsProvider):
    """Provider for Metropolitano de Lisboa."""

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
