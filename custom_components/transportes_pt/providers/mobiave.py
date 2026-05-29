"""Mobiave (Vila Nova de Famalicão) provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class MobiaveProvider(GtfsProvider):
    """Provider for Mobiave — Vila Nova de Famalicão urban transport."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "mobiave"

    @property
    def name(self) -> str:
        return "Mobiave (V.N. Famalicão)"

    @property
    def gtfs_url(self) -> str:
        return (
            "https://map.mobility.ubiwhere.com/dataset/"
            "fe6015e4-86c7-437a-8d31-10759fe21a1d/resource/"
            "7ac67ef8-015c-42e8-9546-f6f0be956270/download/gtfs_vnf.zip"
        )
