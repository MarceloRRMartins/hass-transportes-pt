"""Transtejo Soflusa (TTSL) provider — Ferries across the Tagus."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class TranstejoProvider(GtfsProvider):
    """Provider for Transtejo Soflusa — Tagus river ferries."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "transtejo"

    @property
    def name(self) -> str:
        return "Transtejo Soflusa"

    @property
    def gtfs_url(self) -> str:
        return "https://api.transtejo.pt/files/GTFS.zip"
