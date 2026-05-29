"""Tests for the TransportesCoordinator."""

from __future__ import annotations

import time
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.transportes_pt.coordinator import TransportesCoordinator, TransportesData
from custom_components.transportes_pt.providers import (
    Alert,
    Arrival,
    TransitProvider,
    VehiclePosition,
)

from .conftest import MOCK_ALERTS, MOCK_ARRIVALS, MOCK_STOP_ID, MOCK_VEHICLES


@pytest.fixture
def mock_provider():
    """Create a mock transit provider."""
    provider = AsyncMock(spec=TransitProvider)
    provider.provider_id = "test_provider"
    provider.name = "Test Provider"
    provider.async_get_arrivals = AsyncMock(return_value=MOCK_ARRIVALS)
    provider.async_get_alerts = AsyncMock(return_value=MOCK_ALERTS)
    provider.async_get_vehicles = AsyncMock(return_value=MOCK_VEHICLES)
    return provider


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.loop = MagicMock()
    return hass


def _make_coordinator(hass, provider, **kwargs):
    """Create a coordinator with default intervals set to 0 for testing."""
    defaults = {
        "stop_ids": [MOCK_STOP_ID],
        "scan_interval_arrivals": timedelta(seconds=30),
        "scan_interval_alerts": timedelta(seconds=0),  # always fetch in tests
        "scan_interval_vehicles": timedelta(seconds=0),  # always fetch in tests
    }
    defaults.update(kwargs)
    return TransportesCoordinator(hass, provider=provider, **defaults)


class TestTransportesData:
    """Tests for TransportesData dataclass."""

    def test_default_values(self):
        data = TransportesData()
        assert data.arrivals == {}
        assert data.alerts == []
        assert data.vehicles == []

    def test_with_data(self):
        data = TransportesData(
            arrivals={MOCK_STOP_ID: MOCK_ARRIVALS},
            alerts=MOCK_ALERTS,
            vehicles=MOCK_VEHICLES,
        )
        assert len(data.arrivals[MOCK_STOP_ID]) == 2
        assert len(data.alerts) == 1
        assert len(data.vehicles) == 1


class TestCoordinatorInit:
    """Tests for coordinator initialization."""

    def test_init_with_defaults(self, mock_hass, mock_provider):
        coord = TransportesCoordinator(
            mock_hass,
            provider=mock_provider,
            stop_ids=[MOCK_STOP_ID],
        )
        assert coord.provider == mock_provider
        assert coord.stop_ids == [MOCK_STOP_ID]
        assert coord.line_ids is None
        assert coord.enable_vehicles is True

    def test_init_with_options(self, mock_hass, mock_provider):
        coord = TransportesCoordinator(
            mock_hass,
            provider=mock_provider,
            stop_ids=[MOCK_STOP_ID],
            line_ids=["2727"],
            enable_vehicles=False,
        )
        assert coord.line_ids == ["2727"]
        assert coord.enable_vehicles is False


class TestCoordinatorUpdate:
    """Tests for _async_update_data."""

    @pytest.mark.asyncio
    async def test_fetches_arrivals(self, mock_hass, mock_provider):
        coord = _make_coordinator(mock_hass, mock_provider)
        data = await coord._async_update_data()
        mock_provider.async_get_arrivals.assert_called_once_with(MOCK_STOP_ID)
        assert MOCK_STOP_ID in data.arrivals
        assert len(data.arrivals[MOCK_STOP_ID]) == 2

    @pytest.mark.asyncio
    async def test_fetches_multiple_stops(self, mock_hass, mock_provider):
        coord = _make_coordinator(mock_hass, mock_provider, stop_ids=["060002", "060003"])
        data = await coord._async_update_data()
        assert mock_provider.async_get_arrivals.call_count == 2

    @pytest.mark.asyncio
    async def test_fetches_alerts(self, mock_hass, mock_provider):
        coord = _make_coordinator(mock_hass, mock_provider)
        data = await coord._async_update_data()
        mock_provider.async_get_alerts.assert_called_once()
        assert len(data.alerts) == 1

    @pytest.mark.asyncio
    async def test_alerts_interval_skips_when_recent(self, mock_hass, mock_provider):
        """Test that alerts are NOT fetched when interval hasn't passed."""
        coord = _make_coordinator(
            mock_hass, mock_provider, scan_interval_alerts=timedelta(minutes=5)
        )
        # Simulate recent fetch
        coord._alerts_last_update = time.time()
        data = await coord._async_update_data()
        mock_provider.async_get_alerts.assert_not_called()
        assert data.alerts == []  # No previous data

    @pytest.mark.asyncio
    async def test_alerts_interval_preserves_stale_data(self, mock_hass, mock_provider):
        """Test that skipping alerts returns previous alert data."""
        coord = _make_coordinator(
            mock_hass, mock_provider, scan_interval_alerts=timedelta(minutes=5)
        )
        # Set existing data
        coord.data = TransportesData(alerts=MOCK_ALERTS)
        coord._alerts_last_update = time.time()
        data = await coord._async_update_data()
        assert data.alerts == MOCK_ALERTS

    @pytest.mark.asyncio
    async def test_fetches_vehicles_when_enabled(self, mock_hass, mock_provider):
        coord = _make_coordinator(mock_hass, mock_provider, line_ids=["2727"], enable_vehicles=True)
        data = await coord._async_update_data()
        mock_provider.async_get_vehicles.assert_called_once_with(["2727"])
        assert len(data.vehicles) == 1

    @pytest.mark.asyncio
    async def test_skips_vehicles_when_disabled(self, mock_hass, mock_provider):
        coord = _make_coordinator(mock_hass, mock_provider, enable_vehicles=False)
        data = await coord._async_update_data()
        mock_provider.async_get_vehicles.assert_not_called()
        assert data.vehicles == []

    @pytest.mark.asyncio
    async def test_vehicles_interval_skips_when_recent(self, mock_hass, mock_provider):
        """Test that vehicles are NOT fetched when interval hasn't passed."""
        coord = _make_coordinator(
            mock_hass, mock_provider, scan_interval_vehicles=timedelta(seconds=15)
        )
        coord._vehicles_last_update = time.time()
        data = await coord._async_update_data()
        mock_provider.async_get_vehicles.assert_not_called()

    @pytest.mark.asyncio
    async def test_arrival_error_raises_update_failed(self, mock_hass, mock_provider):
        """Test that arrival errors propagate as UpdateFailed."""
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_provider.async_get_arrivals = AsyncMock(side_effect=Exception("API down"))
        coord = _make_coordinator(mock_hass, mock_provider)
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_alert_error_handled_gracefully(self, mock_hass, mock_provider):
        """Test that alert errors don't crash the coordinator."""
        mock_provider.async_get_alerts = AsyncMock(side_effect=Exception("timeout"))
        coord = _make_coordinator(mock_hass, mock_provider)
        coord.data = None
        data = await coord._async_update_data()
        assert data.alerts == []

    @pytest.mark.asyncio
    async def test_alert_error_preserves_old_data(self, mock_hass, mock_provider):
        """Test that alert errors keep previous data."""
        mock_provider.async_get_alerts = AsyncMock(side_effect=Exception("timeout"))
        coord = _make_coordinator(mock_hass, mock_provider)
        coord.data = TransportesData(alerts=MOCK_ALERTS)
        data = await coord._async_update_data()
        assert data.alerts == MOCK_ALERTS

    @pytest.mark.asyncio
    async def test_vehicle_error_handled_gracefully(self, mock_hass, mock_provider):
        """Test that vehicle errors don't crash the coordinator."""
        mock_provider.async_get_vehicles = AsyncMock(side_effect=Exception("timeout"))
        coord = _make_coordinator(mock_hass, mock_provider, enable_vehicles=True)
        coord.data = None
        data = await coord._async_update_data()
        assert data.vehicles == []

    @pytest.mark.asyncio
    async def test_vehicle_error_preserves_old_data(self, mock_hass, mock_provider):
        """Test that vehicle errors keep previous data."""
        mock_provider.async_get_vehicles = AsyncMock(side_effect=Exception("timeout"))
        coord = _make_coordinator(mock_hass, mock_provider, enable_vehicles=True)
        coord.data = TransportesData(vehicles=MOCK_VEHICLES)
        data = await coord._async_update_data()
        assert data.vehicles == MOCK_VEHICLES
