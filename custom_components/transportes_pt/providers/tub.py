"""TUB — Transportes Urbanos de Braga provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class TubProvider(GtfsProvider):
    """Provider for TUB — Transportes Urbanos de Braga."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "tub"

    @property
    def name(self) -> str:
        return "TUB (Braga)"

    @property
    def gtfs_url(self) -> str:
        return "https://www.tub.pt/developer/gtfs/feed/tub.zip"
