"""Guimabus (Guimarães) provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class GuimabusProvider(GtfsProvider):
    """Provider for Guimabus — Transportes Urbanos de Guimarães."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "guimabus"

    @property
    def name(self) -> str:
        return "Guimabus (Guimarães)"

    @property
    def gtfs_url(self) -> str:
        return (
            "https://map.mobility.ubiwhere.com/dataset/"
            "ee6d46e4-9f19-4f4a-ab93-1a3cd69df349/resource/"
            "08f1ee6c-2d3f-4fb3-a861-5d6fb347a6d4/download/gtfs_gui.zip"
        )
