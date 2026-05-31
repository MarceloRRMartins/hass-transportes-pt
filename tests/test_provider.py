"""Tests for the Carris Metropolitana provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.transportes_pt.providers.carris_metropolitana import (
    CarrisMetropolitanaProvider,
)

MOCK_ARRIVALS_JSON = [
    {
        "estimated_arrival": "06:10:41",
        "estimated_arrival_unix": 1780031441,
        "headsign": "Loures (Centro Comercial)",
        "line_id": "2727",
        "observed_arrival": "06:10:10",
        "observed_arrival_unix": 1780031410,
        "pattern_id": "2727_0_1",
        "route_id": "2727_0",
        "scheduled_arrival": "06:09:11",
        "scheduled_arrival_unix": 1780031351,
        "stop_sequence": 3,
        "trip_id": "[P6Q8K]2727_0_1|1|1|0605",
        "vehicle_id": "42|2328",
    },
]

MOCK_STOPS_JSON = [
    {
        "id": "060002",
        "long_name": "Gare do Oriente 24-C",
        "lat": 38.7677,
        "lon": -9.0990,
        "line_ids": ["2727", "1523"],
        "municipality_name": "Lisboa",
    },
]

MOCK_LINES_JSON = [
    {
        "id": "2727",
        "short_name": "2727",
        "long_name": "Oriente - Loures",
        "color": "#FF0000",
    },
]


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = MagicMock()
    return session


def _mock_response(data, status=200):
    """Create a mock response context manager."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_get_arrivals(mock_session):
    """Test fetching arrivals."""
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_ARRIVALS_JSON))
    provider = CarrisMetropolitanaProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("060002")

    assert len(arrivals) == 1
    assert arrivals[0].line_id == "2727"
    assert arrivals[0].destination == "Loures (Centro Comercial)"
    assert arrivals[0].estimated_arrival_unix == 1780031441
    assert arrivals[0].vehicle_id == "42|2328"


@pytest.mark.asyncio
async def test_get_stops(mock_session):
    """Test fetching stops."""
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_STOPS_JSON))
    provider = CarrisMetropolitanaProvider(session=mock_session)

    stops = await provider.async_get_stops()

    assert len(stops) == 1
    assert stops[0].stop_id == "060002"
    assert stops[0].name == "Gare do Oriente 24-C"
    assert stops[0].municipality == "Lisboa"
    assert "2727" in stops[0].lines


@pytest.mark.asyncio
async def test_get_stops_with_search(mock_session):
    """Test fetching stops with search filter."""
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_STOPS_JSON))
    provider = CarrisMetropolitanaProvider(session=mock_session)

    # Should match
    stops = await provider.async_get_stops(search="Oriente")
    assert len(stops) == 1

    # Should not match
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_STOPS_JSON))
    stops = await provider.async_get_stops(search="Carcavelos")
    assert len(stops) == 0


@pytest.mark.asyncio
async def test_get_lines(mock_session):
    """Test fetching lines."""
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_LINES_JSON))
    provider = CarrisMetropolitanaProvider(session=mock_session)

    lines = await provider.async_get_lines()

    assert len(lines) == 1
    assert lines[0].line_id == "2727"
    assert lines[0].short_name == "2727"
    assert lines[0].color == "#FF0000"


@pytest.mark.asyncio
async def test_test_connection_success(mock_session):
    """Test successful connection test."""
    mock_session.get = MagicMock(return_value=_mock_response([]))
    provider = CarrisMetropolitanaProvider(session=mock_session)

    result = await provider.async_test_connection()
    assert result is True


@pytest.mark.asyncio
async def test_test_connection_failure(mock_session):
    """Test failed connection test."""
    mock_session.get = MagicMock(return_value=_mock_response(None, status=500))
    provider = CarrisMetropolitanaProvider(session=mock_session)

    result = await provider.async_test_connection()
    assert result is False


@pytest.mark.asyncio
async def test_api_error_returns_empty(mock_session):
    """Test that API errors return empty lists."""
    mock_session.get = MagicMock(return_value=_mock_response(None, status=503))
    provider = CarrisMetropolitanaProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("060002")
    assert arrivals == []
