"""Fertagus provider — Comboios suburbanos Setúbal-Lisboa."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class FertagusProvider(GtfsProvider):
    """Provider for Fertagus — suburban rail across Tagus."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "fertagus"

    @property
    def name(self) -> str:
        return "Fertagus"

    @property
    def gtfs_url(self) -> str:
        return "https://www.fertagus.pt/GTFSTMLzip/Fertagus_GTFS.zip"
