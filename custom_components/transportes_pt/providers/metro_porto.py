"""Metro do Porto provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class MetroPortoProvider(GtfsProvider):
    """Provider for Metro do Porto."""

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
        return "https://www.metrodoporto.pt/metrodoporto/uploads/document/file/794/google_transit_07_04_2026.zip"

    @property
    def gtfs_cache_ttl(self) -> int:
        # Metro Porto updates infrequently
        return 172800  # 48h
