"""CP — Comboios de Portugal provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class CpProvider(GtfsProvider):
    """Provider for CP — Comboios de Portugal (national rail)."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "cp"

    @property
    def name(self) -> str:
        return "CP - Comboios de Portugal"

    @property
    def gtfs_url(self) -> str:
        return "https://publico.cp.pt/gtfs/gtfs.zip"
