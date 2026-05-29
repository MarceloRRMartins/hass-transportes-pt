"""TCB — Transportes Colectivos do Barreiro provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class TcbProvider(GtfsProvider):
    """Provider for TCB — Transportes Colectivos do Barreiro."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "tcb"

    @property
    def name(self) -> str:
        return "TCB (Barreiro)"

    @property
    def gtfs_url(self) -> str:
        return "https://backend.tcbarreiro.pt/download-gtfs"
