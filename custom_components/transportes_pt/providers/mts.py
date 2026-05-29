"""MTS — Metro Transportes do Sul (Metro Sul do Tejo) provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class MtsProvider(GtfsProvider):
    """Provider for MTS — Metro Sul do Tejo (light rail Almada/Seixal)."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "mts"

    @property
    def name(self) -> str:
        return "MTS - Metro Sul do Tejo"

    @property
    def gtfs_url(self) -> str:
        return "https://mts.pt/imt/MTS-20240129.zip"
