"""Horários do Funchal provider — Autocarros da Madeira."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class HorariosFunchalProvider(GtfsProvider):
    """Provider for Horários do Funchal — Madeira island buses."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "horarios_funchal"

    @property
    def name(self) -> str:
        return "Horários do Funchal"

    @property
    def gtfs_url(self) -> str:
        return "https://www.horariosdofunchal.pt/googletransit.zip"
