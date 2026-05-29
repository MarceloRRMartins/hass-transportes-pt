"""CIM Tâmega e Sousa provider."""

from __future__ import annotations

import aiohttp

from .gtfs_base import GtfsProvider


class CimTsProvider(GtfsProvider):
    """Provider for CIM Tâmega e Sousa — Intermunicipal transport."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "cim_tamega_sousa"

    @property
    def name(self) -> str:
        return "CIM Tâmega e Sousa"

    @property
    def gtfs_url(self) -> str:
        return "https://transportes.cimtamegaesousa.pt/Servico/services/consultas.svc/Feed/OpenGTFS"
