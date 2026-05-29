"""TUBA (Barcelos) provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class TubaProvider(GtfsProvider):
    """Provider for TUBA — Transportes Urbanos de Barcelos."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "tuba"

    @property
    def name(self) -> str:
        return "TUBA (Barcelos)"

    @property
    def gtfs_url(self) -> str:
        return (
            "https://map.mobility.ubiwhere.com/dataset/"
            "1842a15c-1aec-4f65-8e29-e57c8b4cbd74/resource/"
            "a595ee4b-bf86-4323-b1f4-7e3b3eb00e5e/download/gtfs_bar.zip"
        )
