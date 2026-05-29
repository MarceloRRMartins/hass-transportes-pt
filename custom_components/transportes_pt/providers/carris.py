"""Carris (CCFL) Lisboa provider — Eléctricos e autocarros de Lisboa."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class CarrisProvider(GtfsProvider):
    """Provider for Carris (CCFL) — Lisboa city buses and trams."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "carris"

    @property
    def name(self) -> str:
        return "Carris (Lisboa)"

    @property
    def gtfs_url(self) -> str:
        return "https://gateway.carris.pt/gateway/gtfs/api/v2.11/GTFS"

    @property
    def gtfs_rt_vehicle_positions_url(self) -> str | None:
        return "https://gateway.carris.pt/gateway/gtfs/api/v2.8/GTFS/realtime/vehiclepositions"

    @property
    def gtfs_cache_ttl(self) -> int:
        # Carris GTFS is 67MB — cache for 48h
        return 172800
