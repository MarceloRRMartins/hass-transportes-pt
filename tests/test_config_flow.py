"""Tests for the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.transportes_pt.const import (
    CONF_ENABLE_VEHICLES,
    CONF_LINES,
    CONF_PROVIDER,
    CONF_STOPS,
    DOMAIN,
    PROVIDER_CARRIS_METROPOLITANA,
    PROVIDER_CP,
    PROVIDER_STCP,
)


class TestCreateFlowProvider:
    """Test the _create_flow_provider helper."""

    def _create_flow(self, provider_id):
        """Create a flow instance with mocked HA."""
        from custom_components.transportes_pt.config_flow import TransportesPTConfigFlow

        flow = TransportesPTConfigFlow()
        flow._provider_id = provider_id
        return flow

    def test_creates_carris_metropolitana(self):
        from custom_components.transportes_pt.providers.carris_metropolitana import (
            CarrisMetropolitanaProvider,
        )

        flow = self._create_flow(PROVIDER_CARRIS_METROPOLITANA)
        session = MagicMock()
        provider = flow._create_flow_provider(session)
        assert isinstance(provider, CarrisMetropolitanaProvider)

    def test_creates_cp_provider(self):
        from custom_components.transportes_pt.providers.cp import CpProvider

        flow = self._create_flow(PROVIDER_CP)
        session = MagicMock()
        provider = flow._create_flow_provider(session)
        assert isinstance(provider, CpProvider)

    def test_creates_stcp_provider(self):
        from custom_components.transportes_pt.providers.stcp import StcpProvider

        flow = self._create_flow(PROVIDER_STCP)
        session = MagicMock()
        provider = flow._create_flow_provider(session)
        assert isinstance(provider, StcpProvider)

    def test_unknown_provider_raises(self):
        flow = self._create_flow("nonexistent_provider")
        session = MagicMock()
        with pytest.raises(ValueError, match="Unknown provider"):
            flow._create_flow_provider(session)

    def test_all_providers_are_mapped(self):
        """Verify every known provider can be created."""
        from custom_components.transportes_pt.const import (
            PROVIDER_CARRIS,
            PROVIDER_METRO_LISBOA,
            PROVIDER_METRO_PORTO,
            PROVIDER_FERTAGUS,
            PROVIDER_TRANSTEJO,
            PROVIDER_MTS,
            PROVIDER_TCB,
            PROVIDER_TUB,
            PROVIDER_TUBA,
            PROVIDER_GUIMABUS,
            PROVIDER_MOBIAVE,
            PROVIDER_CIM_TAMEGA_SOUSA,
            PROVIDER_BUSWAY_COIMBRA,
            PROVIDER_BUSWAY_CIRA,
            PROVIDER_HORARIOS_FUNCHAL,
            PROVIDER_MOBICASCAIS,
        )

        session = MagicMock()
        all_providers = [
            PROVIDER_CARRIS_METROPOLITANA,
            PROVIDER_CARRIS,
            PROVIDER_STCP,
            PROVIDER_METRO_PORTO,
            PROVIDER_CP,
            PROVIDER_METRO_LISBOA,
            PROVIDER_FERTAGUS,
            PROVIDER_TRANSTEJO,
            PROVIDER_MTS,
            PROVIDER_TCB,
            PROVIDER_TUB,
            PROVIDER_HORARIOS_FUNCHAL,
            PROVIDER_MOBICASCAIS,
            PROVIDER_CIM_TAMEGA_SOUSA,
            PROVIDER_BUSWAY_COIMBRA,
            PROVIDER_BUSWAY_CIRA,
            PROVIDER_MOBIAVE,
            PROVIDER_TUBA,
            PROVIDER_GUIMABUS,
        ]

        for provider_id in all_providers:
            flow = self._create_flow(provider_id)
            provider = flow._create_flow_provider(session)
            assert provider is not None, f"Failed to create provider: {provider_id}"
            assert provider.provider_id == provider_id
