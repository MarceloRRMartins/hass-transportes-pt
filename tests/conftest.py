"""Fixtures for Transportes PT tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.transportes_pt.const import (
    CONF_ENABLE_VEHICLES,
    CONF_LINES,
    CONF_PROVIDER,
    CONF_STOPS,
    PROVIDER_CARRIS_METROPOLITANA,
)
from custom_components.transportes_pt.providers import (
    Alert,
    Arrival,
    Line,
    Stop,
    VehiclePosition,
)

MOCK_STOP_ID = "060002"

MOCK_ARRIVALS = [
    Arrival(
        line_id="2727",
        line_name="2727",
        destination="Loures (Centro Comercial)",
        estimated_arrival="06:10:41",
        scheduled_arrival="06:09:11",
        estimated_arrival_unix=1780031441,
        scheduled_arrival_unix=1780031351,
        vehicle_id="42|2328",
        trip_id="[P6Q8K]2727_0_1|1|1|0605",
    ),
    Arrival(
        line_id="1523",
        line_name="1523",
        destination="Moscavide",
        estimated_arrival="06:15:00",
        scheduled_arrival="06:14:00",
        estimated_arrival_unix=1780031700,
        scheduled_arrival_unix=1780031640,
        vehicle_id="42|1101",
        trip_id="[P6Q8K]1523_0_1|1|1|0610",
    ),
]

MOCK_ALERTS = [
    Alert(
        alert_id="alert_1",
        title="Desvio de percurso na linha 2727",
        description="Obras na Av. da República",
        affected_lines=["2727"],
        affected_stops=["060002"],
        start_time="1780020000",
        end_time="1780106400",
        url="https://www.carrismetropolitana.pt/alertas/1",
    ),
]

MOCK_VEHICLES = [
    VehiclePosition(
        vehicle_id="42|2328",
        line_id="2727",
        trip_id="[P6Q8K]2727_0_1|1|1|0605",
        latitude=38.7677,
        longitude=-9.0990,
        heading=180.0,
        speed=25.0,
        stop_id="060003",
    ),
]

MOCK_STOPS = [
    Stop(
        stop_id="060002",
        name="Gare do Oriente 24-C",
        latitude=38.7677,
        longitude=-9.0990,
        lines=["2727", "1523", "4704"],
        municipality="Lisboa",
    ),
    Stop(
        stop_id="060003",
        name="Gare do Oriente 24-D",
        latitude=38.7678,
        longitude=-9.0991,
        lines=["2727"],
        municipality="Lisboa",
    ),
]

MOCK_LINES = [
    Line(line_id="2727", short_name="2727", long_name="Oriente - Loures", color="#FF0000"),
    Line(line_id="1523", short_name="1523", long_name="Oriente - Moscavide", color="#00FF00"),
]

MOCK_CONFIG_ENTRY_DATA = {
    CONF_PROVIDER: PROVIDER_CARRIS_METROPOLITANA,
    CONF_STOPS: [MOCK_STOP_ID],
    CONF_LINES: [],
    CONF_ENABLE_VEHICLES: True,
}


@pytest.fixture
def hass():
    """Create a mock Home Assistant instance."""
    from unittest.mock import MagicMock

    hass = MagicMock()
    hass.loop = MagicMock()
    return hass


@pytest.fixture
def mock_provider():
    """Create a mock transit provider."""
    with patch(
        "custom_components.transportes_pt.providers.carris_metropolitana.CarrisMetropolitanaProvider"
    ) as mock_cls:
        provider = AsyncMock()
        provider.provider_id = PROVIDER_CARRIS_METROPOLITANA
        provider.name = "Carris Metropolitana"
        provider.async_init = AsyncMock()
        provider.async_close = AsyncMock()
        provider.async_test_connection = AsyncMock(return_value=True)
        provider.async_get_arrivals = AsyncMock(return_value=MOCK_ARRIVALS)
        provider.async_get_alerts = AsyncMock(return_value=MOCK_ALERTS)
        provider.async_get_vehicles = AsyncMock(return_value=MOCK_VEHICLES)
        provider.async_get_stops = AsyncMock(return_value=MOCK_STOPS)
        provider.async_get_lines = AsyncMock(return_value=MOCK_LINES)
        mock_cls.return_value = provider
        yield provider
