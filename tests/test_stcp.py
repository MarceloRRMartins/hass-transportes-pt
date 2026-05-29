"""Tests for the STCP provider (Porto city buses)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.transportes_pt.providers.stcp import (
    STCP_CKAN_API,
    STCP_DATASET_ID,
    STCP_REALTIME_URL,
    StcpProvider,
)
from custom_components.transportes_pt.providers import VehiclePosition


MOCK_CKAN_RESPONSE = {
    "success": True,
    "result": {
        "resources": [
            {"id": "old-resource", "url": "https://example.com/old.zip"},
            {"id": "latest-resource", "url": "https://example.com/latest_gtfs.zip"},
        ]
    },
}

MOCK_NGSI_RESPONSE = [
    {
        "id": "bus:stcp:001",
        "location": {"coordinates": [-8.6110, 41.1496]},
        "lineId": {"value": "502"},
        "heading": {"value": 90.0},
        "speed": {"value": 30.0},
    },
    {
        "id": "bus:stcp:002",
        "location": {"coordinates": [-8.6200, 41.1500]},
        "lineId": {"value": "200"},
        "heading": {"value": 180.0},
        "speed": {"value": 0.0},
    },
    {
        "id": "bus:stcp:003",
        "location": {},  # No coordinates
        "lineId": {"value": "700"},
    },
]


def _mock_response(data=None, status=200, json_data=None):
    """Create mock async context manager response."""
    resp = AsyncMock()
    resp.status = status
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    if data is not None:
        resp.read = AsyncMock(return_value=data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestStcpProviderProperties:
    """Test basic STCP provider properties."""

    def test_provider_id(self):
        p = StcpProvider()
        assert p.provider_id == "stcp"

    def test_name(self):
        p = StcpProvider()
        assert "STCP" in p.name
        assert "Porto" in p.name

    def test_default_gtfs_url(self):
        """When no CKAN URL resolved, use fallback."""
        p = StcpProvider()
        assert "opendata.porto.digital" in p.gtfs_url
        assert "gtfs_feed.zip" in p.gtfs_url

    def test_resolved_gtfs_url(self):
        """When CKAN resolves a URL, use it instead."""
        p = StcpProvider()
        p._resolved_gtfs_url = "https://example.com/new.zip"
        assert p.gtfs_url == "https://example.com/new.zip"

    def test_cache_ttl_12h(self):
        p = StcpProvider()
        assert p.gtfs_cache_ttl == 43200


class TestStcpCkanResolution:
    """Test CKAN API URL resolution."""

    @pytest.mark.asyncio
    async def test_resolves_latest_url(self):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(json_data=MOCK_CKAN_RESPONSE))
        p = StcpProvider(session=session)
        await p._resolve_latest_gtfs_url()
        assert p._resolved_gtfs_url == "https://example.com/latest_gtfs.zip"

    @pytest.mark.asyncio
    async def test_ckan_failure_uses_fallback(self):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(status=500))
        p = StcpProvider(session=session)
        await p._resolve_latest_gtfs_url()
        assert p._resolved_gtfs_url is None
        # Fallback URL still works
        assert "opendata.porto.digital" in p.gtfs_url

    @pytest.mark.asyncio
    async def test_ckan_empty_resources(self):
        data = {"result": {"resources": []}}
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(json_data=data))
        p = StcpProvider(session=session)
        await p._resolve_latest_gtfs_url()
        assert p._resolved_gtfs_url is None

    @pytest.mark.asyncio
    async def test_ckan_timeout(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError("timeout"))
        p = StcpProvider(session=session)
        await p._resolve_latest_gtfs_url()
        assert p._resolved_gtfs_url is None


class TestStcpVehicles:
    """Test NGSI/FIWARE vehicle parsing."""

    @pytest.mark.asyncio
    async def test_parse_vehicles(self):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(json_data=MOCK_NGSI_RESPONSE))
        p = StcpProvider(session=session)
        p._session = session

        vehicles = await p.async_get_vehicles()

        # 3rd entity has no coordinates, should be skipped
        assert len(vehicles) == 2
        assert vehicles[0].vehicle_id == "bus:stcp:001"
        assert vehicles[0].latitude == 41.1496
        assert vehicles[0].longitude == -8.6110
        assert vehicles[0].line_id == "502"
        assert vehicles[0].heading == 90.0
        assert vehicles[0].speed == 30.0

    @pytest.mark.asyncio
    async def test_filter_by_line_ids(self):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(json_data=MOCK_NGSI_RESPONSE))
        p = StcpProvider(session=session)
        p._session = session

        vehicles = await p.async_get_vehicles(line_ids=["502"])

        assert len(vehicles) == 1
        assert vehicles[0].line_id == "502"

    @pytest.mark.asyncio
    async def test_vehicles_api_error(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError("connection refused"))
        p = StcpProvider(session=session)
        p._session = session

        vehicles = await p.async_get_vehicles()
        assert vehicles == []

    @pytest.mark.asyncio
    async def test_vehicles_non_200(self):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(json_data=[], status=503))
        p = StcpProvider(session=session)
        p._session = session

        vehicles = await p.async_get_vehicles()
        assert vehicles == []

    @pytest.mark.asyncio
    async def test_alternative_coordinate_format(self):
        """Test entities with longitude/latitude as direct fields."""
        data = [
            {
                "id": "bus:alt:001",
                "location": {},
                "longitude": {"value": -8.5},
                "latitude": {"value": 41.2},
                "lineId": {"value": "300"},
                "heading": None,
                "speed": None,
            }
        ]
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(json_data=data))
        p = StcpProvider(session=session)
        p._session = session

        vehicles = await p.async_get_vehicles()

        assert len(vehicles) == 1
        assert vehicles[0].latitude == 41.2
        assert vehicles[0].longitude == -8.5
        assert vehicles[0].heading is None
        assert vehicles[0].speed is None

    @pytest.mark.asyncio
    async def test_geojson_coordinate_order(self):
        """NGSI uses GeoJSON: [longitude, latitude]."""
        data = [
            {
                "id": "bus:geo:001",
                "location": {"coordinates": [-8.6, 41.15]},
                "routeId": "ZR",
            }
        ]
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(json_data=data))
        p = StcpProvider(session=session)
        p._session = session

        vehicles = await p.async_get_vehicles()
        # [lon, lat] → lon=-8.6, lat=41.15
        assert vehicles[0].longitude == -8.6
        assert vehicles[0].latitude == 41.15
        assert vehicles[0].line_id == "ZR"
