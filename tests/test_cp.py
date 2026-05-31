"""Tests for the CP - Comboios de Portugal provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.transportes_pt.providers.cp import (
    CpProvider,
    _gtfs_to_live_stop_id,
    _live_to_gtfs_stop_id,
)


def _future_iso(minutes: int) -> str:
    """Return an ISO timestamp minutes from now (for mock data that won't expire)."""
    dt = datetime.now(tz=UTC) + timedelta(minutes=minutes)
    return dt.isoformat()


# --- Mock data based on real comboios.live API responses ---

MOCK_ARRIVALS_RESPONSE = [
    {
        "trainNumber": 528,
        "trainService": {"code": 2, "designation": "Intercidades"},
        "trainDestination": {"designation": "Lisboa Santa Apolónia"},
        "scheduledTime": _future_iso(10),
        "delay": 120,
        "arrival": _future_iso(10),
    },
    {
        "trainNumber": 4321,
        "trainService": {"code": 4, "designation": "Regional"},
        "trainDestination": {"designation": "Coimbra-B"},
        "scheduledTime": _future_iso(20),
        "delay": 0,
        "arrival": _future_iso(20),
    },
    {
        "trainNumber": 130,
        "trainService": {"code": 1, "designation": "Alfa Pendular"},
        "trainDestination": {"designation": "Faro"},
        "scheduledTime": _future_iso(30),
        "delay": -60,
        "arrival": _future_iso(30),
    },
]

MOCK_VEHICLES_RESPONSE = [
    {
        "trainNumber": 528,
        "status": "IN_TRANSIT",
        "service": {"code": 2, "designation": "Intercidades"},
        "origin": {"designation": "Porto Campanhã"},
        "destination": {"designation": "Lisboa Santa Apolónia"},
        "lat": "40.3456",
        "lng": "-8.6789",
        "bearing": 180.5,
        "speed": 120.3,
        "lastStation": "94-30007",
        "runDate": "2026-05-31",
        "gtfs": {"tripId": "trip_528_20260531"},
    },
    {
        "trainNumber": 4321,
        "status": "AT_STATION",
        "service": {"code": 4, "designation": "Regional"},
        "origin": {"designation": "Aveiro"},
        "destination": {"designation": "Coimbra-B"},
        "lat": "40.2100",
        "lng": "-8.4300",
        "bearing": None,
        "speed": 0,
        "lastStation": "94-39006",
        "runDate": "2026-05-31",
        "gtfs": {"tripId": "trip_4321_20260531"},
    },
    {
        "trainNumber": 999,
        "status": "CANCELLED",
        "service": {"code": 1, "designation": "Alfa Pendular"},
        "origin": {"designation": "Braga"},
        "destination": {"designation": "Faro"},
        "lat": None,
        "lng": None,
        "bearing": None,
        "speed": None,
        "lastStation": "",
        "runDate": "2026-05-31",
        "gtfs": None,
    },
    {
        "trainNumber": 100,
        "status": "COMPLETED",
        "service": {"code": 2, "designation": "Intercidades"},
        "origin": {"designation": "Lisboa"},
        "destination": {"designation": "Porto"},
        "lat": "41.1500",
        "lng": "-8.6100",
        "bearing": 0,
        "speed": 0,
        "lastStation": "94-35004",
        "runDate": "2026-05-31",
        "gtfs": {"tripId": "trip_100_20260531"},
    },
]


def _mock_json_response(data, status: int = 200):
    """Create a mock response with .json() method."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = MagicMock()
    return session


# --- Stop ID conversion tests ---


def test_gtfs_to_live_stop_id():
    """GTFS stop_id format converts to comboios.live format."""
    assert _gtfs_to_live_stop_id("94_30007") == "94-30007"
    assert _gtfs_to_live_stop_id("94_35004") == "94-35004"


def test_live_to_gtfs_stop_id():
    """comboios.live station_id converts to GTFS format."""
    assert _live_to_gtfs_stop_id("94-30007") == "94_30007"
    assert _live_to_gtfs_stop_id("94-35004") == "94_35004"


def test_stop_id_roundtrip():
    """Stop ID conversion is reversible."""
    original = "94_30007"
    assert _live_to_gtfs_stop_id(_gtfs_to_live_stop_id(original)) == original


# --- Provider properties tests ---


def test_provider_id():
    """Provider ID is correct."""
    provider = CpProvider(session=MagicMock())
    assert provider.provider_id == "cp"


def test_provider_name():
    """Provider name is correct."""
    provider = CpProvider(session=MagicMock())
    assert provider.name == "CP - Comboios de Portugal"


def test_gtfs_url():
    """GTFS URL points to official CP feed."""
    provider = CpProvider(session=MagicMock())
    assert provider.gtfs_url == "https://publico.cp.pt/gtfs/gtfs.zip"


def test_gtfs_rt_urls():
    """GTFS-RT URLs are set."""
    provider = CpProvider(session=MagicMock())
    assert provider.gtfs_rt_vehicle_positions_url is not None
    assert provider.gtfs_rt_trip_updates_url is not None


# --- Arrivals tests ---


@pytest.mark.asyncio
async def test_async_get_arrivals_success(mock_session):
    """Test arrivals parsing from comboios.live."""
    mock_session.get = MagicMock(return_value=_mock_json_response(MOCK_ARRIVALS_RESPONSE))
    provider = CpProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("94_30007")

    assert len(arrivals) == 3
    # First arrival: Intercidades 528
    assert arrivals[0].line_id == "2"
    assert "Intercidades" in arrivals[0].line_name
    assert "528" in arrivals[0].line_name
    assert arrivals[0].destination == "Lisboa Santa Apolónia"
    assert arrivals[0].vehicle_id == "528"
    assert arrivals[0].estimated_arrival_unix is not None
    assert arrivals[0].scheduled_arrival_unix is not None
    # Delay of 120s means estimated > scheduled
    assert arrivals[0].estimated_arrival_unix == arrivals[0].scheduled_arrival_unix + 120


@pytest.mark.asyncio
async def test_async_get_arrivals_uses_correct_url(mock_session):
    """Test that stop_id is converted for the API call."""
    mock_session.get = MagicMock(return_value=_mock_json_response([]))
    provider = CpProvider(session=mock_session)

    await provider._get_live_arrivals("94_30007")

    # Verify the URL uses dash format
    call_args = mock_session.get.call_args
    url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert "94-30007" in url


@pytest.mark.asyncio
async def test_async_get_arrivals_empty_response(mock_session):
    """Empty station returns None (triggers GTFS fallback)."""
    mock_session.get = MagicMock(return_value=_mock_json_response([]))
    provider = CpProvider(session=mock_session)

    result = await provider._get_live_arrivals("94_30007")
    assert result is None


@pytest.mark.asyncio
async def test_async_get_arrivals_api_error(mock_session):
    """API error returns None (triggers fallback)."""
    mock_session.get = MagicMock(return_value=_mock_json_response(None, status=500))
    provider = CpProvider(session=mock_session)

    result = await provider._get_live_arrivals("94_30007")
    assert result is None


@pytest.mark.asyncio
async def test_async_get_arrivals_network_error(mock_session):
    """Network error returns None (triggers fallback)."""
    mock_session.get = MagicMock(side_effect=Exception("Connection timeout"))
    provider = CpProvider(session=mock_session)

    result = await provider._get_live_arrivals("94_30007")
    assert result is None


@pytest.mark.asyncio
async def test_async_get_arrivals_negative_delay(mock_session):
    """Negative delay (early train) is handled correctly."""
    mock_session.get = MagicMock(return_value=_mock_json_response(MOCK_ARRIVALS_RESPONSE))
    provider = CpProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("94_30007")

    # Third arrival has delay=-60 (1 minute early)
    ap_arrival = next(a for a in arrivals if "130" in a.line_name)
    assert ap_arrival.estimated_arrival_unix == ap_arrival.scheduled_arrival_unix - 60


# --- Alerts tests ---


@pytest.mark.asyncio
async def test_async_get_alerts_cancelled_trains(mock_session):
    """Test that cancelled trains are returned as alerts."""
    mock_session.get = MagicMock(return_value=_mock_json_response(MOCK_VEHICLES_RESPONSE))
    provider = CpProvider(session=mock_session)

    alerts = await provider.async_get_alerts()

    assert len(alerts) == 1
    alert = alerts[0]
    assert "999" in alert.alert_id
    assert "suprimido" in alert.title
    assert "999" in alert.title
    assert "Braga" in alert.description
    assert "Faro" in alert.description
    assert alert.affected_lines == ["1"]


@pytest.mark.asyncio
async def test_async_get_alerts_no_cancelled(mock_session):
    """No cancelled trains means no alerts."""
    active_only = [v for v in MOCK_VEHICLES_RESPONSE if v["status"] != "CANCELLED"]
    mock_session.get = MagicMock(return_value=_mock_json_response(active_only))
    provider = CpProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


@pytest.mark.asyncio
async def test_async_get_alerts_api_error(mock_session):
    """API error returns empty alerts."""
    mock_session.get = MagicMock(return_value=_mock_json_response(None, status=500))
    provider = CpProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


@pytest.mark.asyncio
async def test_async_get_alerts_network_error(mock_session):
    """Network error returns empty alerts."""
    mock_session.get = MagicMock(side_effect=Exception("DNS failure"))
    provider = CpProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


# --- Vehicles tests ---


@pytest.mark.asyncio
async def test_async_get_vehicles_success(mock_session):
    """Test vehicle position parsing from comboios.live."""
    mock_session.get = MagicMock(return_value=_mock_json_response(MOCK_VEHICLES_RESPONSE))
    provider = CpProvider(session=mock_session)

    vehicles = await provider._get_live_vehicles()

    # CANCELLED and COMPLETED are excluded, null lat/lng excluded
    assert len(vehicles) == 2

    # First vehicle: Intercidades 528
    v1 = next(v for v in vehicles if v.vehicle_id == "528")
    assert v1.line_id == "2"
    assert v1.latitude == 40.3456
    assert v1.longitude == -8.6789
    assert v1.heading == 180.5
    assert v1.speed == 120.3
    assert v1.stop_id == "94_30007"  # Converted back to GTFS format
    assert v1.trip_id == "trip_528_20260531"

    # Second vehicle: Regional 4321
    v2 = next(v for v in vehicles if v.vehicle_id == "4321")
    assert v2.line_id == "4"
    assert v2.heading is None  # bearing was None
    assert v2.speed == 0.0
    assert v2.stop_id == "94_39006"


@pytest.mark.asyncio
async def test_async_get_vehicles_filter_by_line(mock_session):
    """Test filtering vehicles by line_ids."""
    mock_session.get = MagicMock(return_value=_mock_json_response(MOCK_VEHICLES_RESPONSE))
    provider = CpProvider(session=mock_session)

    vehicles = await provider._get_live_vehicles(line_ids=["2"])

    assert len(vehicles) == 1
    assert vehicles[0].vehicle_id == "528"
    assert vehicles[0].line_id == "2"


@pytest.mark.asyncio
async def test_async_get_vehicles_filter_no_match(mock_session):
    """Filtering by non-existent line returns empty."""
    mock_session.get = MagicMock(return_value=_mock_json_response(MOCK_VEHICLES_RESPONSE))
    provider = CpProvider(session=mock_session)

    vehicles = await provider._get_live_vehicles(line_ids=["99"])
    assert vehicles == []


@pytest.mark.asyncio
async def test_async_get_vehicles_api_error(mock_session):
    """API error returns None (triggers GTFS-RT fallback)."""
    mock_session.get = MagicMock(return_value=_mock_json_response(None, status=500))
    provider = CpProvider(session=mock_session)

    result = await provider._get_live_vehicles()
    assert result is None


@pytest.mark.asyncio
async def test_async_get_vehicles_network_error(mock_session):
    """Network error returns None (triggers fallback)."""
    mock_session.get = MagicMock(side_effect=Exception("Timeout"))
    provider = CpProvider(session=mock_session)

    result = await provider._get_live_vehicles()
    assert result is None


@pytest.mark.asyncio
async def test_async_get_vehicles_excludes_no_coords(mock_session):
    """Vehicles without coordinates are excluded."""
    # The CANCELLED train (999) has lat=None, lng=None — should be excluded
    mock_session.get = MagicMock(return_value=_mock_json_response(MOCK_VEHICLES_RESPONSE))
    provider = CpProvider(session=mock_session)

    vehicles = await provider._get_live_vehicles()
    vehicle_ids = [v.vehicle_id for v in vehicles]
    assert "999" not in vehicle_ids
