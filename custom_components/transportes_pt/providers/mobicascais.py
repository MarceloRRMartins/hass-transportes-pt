"""MobiCascais provider — Transportes urbanos de Cascais."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class MobiCascaisProvider(GtfsProvider):
    """Provider for MobiCascais — Cascais municipal transport."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "mobicascais"

    @property
    def name(self) -> str:
        return "MobiCascais"

    @property
    def gtfs_url(self) -> str:
        return "https://drive.google.com/uc?export=download&id=13ucYiAJRtu-gXsLa02qKJrGOgDjbnUWX"
