"""Busway Coimbra (SIT Metropolitano) provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class BuswayCoimbraProvider(GtfsProvider):
    """Provider for Busway Coimbra — SIT Metropolitano de Coimbra."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "busway_coimbra"

    @property
    def name(self) -> str:
        return "Busway (Coimbra)"

    @property
    def gtfs_url(self) -> str:
        return "http://it.busway-cira.pt/GTFS/GTFS_SIT_Metropolitano.zip"
