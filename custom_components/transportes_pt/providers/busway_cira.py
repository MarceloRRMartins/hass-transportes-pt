"""Busway CIRA (Aveiro) provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class BuswayCiraProvider(GtfsProvider):
    """Provider for Busway CIRA — Região de Aveiro buses."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "busway_cira"

    @property
    def name(self) -> str:
        return "Busway CIRA (Aveiro)"

    @property
    def gtfs_url(self) -> str:
        return "https://it.busway-cira.pt/GTFS/GTFS_CIRA.zip"
