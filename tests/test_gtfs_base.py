"""Tests for the GtfsProvider base class."""

from __future__ import annotations

import io
import csv
import time
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.transportes_pt.providers.gtfs_base import GtfsProvider, DEFAULT_GTFS_CACHE_TTL
from custom_components.transportes_pt.providers.gtfs_utils import GtfsData
from custom_components.transportes_pt.providers import Stop, Line, Arrival


class ConcreteProvider(GtfsProvider):
    """Concrete GTFS provider for testing."""

    @property
    def provider_id(self) -> str:
        return "test_gtfs"

    @property
    def name(self) -> str:
        return "Test GTFS Provider"

    @property
    def gtfs_url(self) -> str:
        return "https://test.example.com/gtfs.zip"


class ProviderWithRT(GtfsProvider):
    """Provider with GTFS-RT for testing."""

    @property
    def provider_id(self) -> str:
        return "test_rt"

    @property
    def name(self) -> str:
        return "Test RT Provider"

    @property
    def gtfs_url(self) -> str:
        return "https://test.example.com/gtfs.zip"

    @property
    def gtfs_rt_vehicle_positions_url(self) -> str | None:
        return "https://test.example.com/gtfs-rt/vehicles"

    @property
    def gtfs_rt_trip_updates_url(self) -> str | None:
        return "https://test.example.com/gtfs-rt/trips"

    @property
    def gtfs_rt_alerts_url(self) -> str | None:
        return "https://test.example.com/gtfs-rt/alerts"


class ProviderWithHeaders(GtfsProvider):
    """Provider with custom headers."""

    @property
    def provider_id(self) -> str:
        return "test_headers"

    @property
    def name(self) -> str:
        return "Test Headers Provider"

    @property
    def gtfs_url(self) -> str:
        return "https://test.example.com/gtfs.zip"

    @property
    def gtfs_headers(self) -> dict[str, str]:
        return {"User-Agent": "TestAgent/1.0", "Authorization": "Bearer token"}

    @property
    def gtfs_cache_ttl(self) -> int:
        return 3600  # 1 hour


def _make_gtfs_zip() -> bytes:
    """Create a minimal valid GTFS ZIP."""

    def csv_str(rows):
        if not rows:
            return ""
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
        return out.getvalue()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("stops.txt", csv_str([
            {"stop_id": "S1", "stop_name": "Praça A", "stop_lat": "38.7", "stop_lon": "-9.1", "location_type": "0", "zone_id": "Lisboa"},
            {"stop_id": "S2", "stop_name": "Estação B", "stop_lat": "38.8", "stop_lon": "-9.2", "location_type": "0", "zone_id": "Porto"},
            {"stop_id": "ST1", "stop_name": "Station", "stop_lat": "38.7", "stop_lon": "-9.1", "location_type": "1"},  # station, not stop
        ]))
        zf.writestr("routes.txt", csv_str([
            {"route_id": "R1", "route_short_name": "15E", "route_long_name": "Praça - Algés", "route_type": "0", "route_color": "FFCC00"},
            {"route_id": "R2", "route_short_name": "28E", "route_long_name": "Graça - Prazeres", "route_type": "0", "route_color": "FF0000"},
        ]))
        zf.writestr("trips.txt", csv_str([
            {"trip_id": "T1", "route_id": "R1", "service_id": "SVC1", "trip_headsign": "Algés"},
            {"trip_id": "T2", "route_id": "R2", "service_id": "SVC1", "trip_headsign": "Prazeres"},
        ]))
        zf.writestr("stop_times.txt", csv_str([
            {"trip_id": "T1", "stop_id": "S1", "arrival_time": "08:00:00", "departure_time": "08:01:00", "stop_sequence": "1"},
            {"trip_id": "T1", "stop_id": "S2", "arrival_time": "08:30:00", "departure_time": "08:31:00", "stop_sequence": "2"},
            {"trip_id": "T2", "stop_id": "S1", "arrival_time": "08:15:00", "departure_time": "08:16:00", "stop_sequence": "1"},
        ]))
        zf.writestr("calendar.txt", csv_str([
            {"service_id": "SVC1", "monday": "1", "tuesday": "1", "wednesday": "1", "thursday": "1", "friday": "1", "saturday": "0", "sunday": "0", "start_date": "20260101", "end_date": "20261231"},
        ]))
    return buf.getvalue()


def _mock_response(data=None, status=200):
    """Create a mock async context manager response."""
    resp = AsyncMock()
    resp.status = status
    if data is not None:
        resp.read = AsyncMock(return_value=data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestGtfsProviderProperties:
    """Test base property behavior."""

    def test_default_no_rt_urls(self):
        p = ConcreteProvider()
        assert p.gtfs_rt_vehicle_positions_url is None
        assert p.gtfs_rt_trip_updates_url is None
        assert p.gtfs_rt_alerts_url is None

    def test_default_no_headers(self):
        p = ConcreteProvider()
        assert p.gtfs_headers == {}

    def test_default_cache_ttl(self):
        p = ConcreteProvider()
        assert p.gtfs_cache_ttl == DEFAULT_GTFS_CACHE_TTL

    def test_custom_headers(self):
        p = ProviderWithHeaders()
        assert p.gtfs_headers["User-Agent"] == "TestAgent/1.0"
        assert p.gtfs_headers["Authorization"] == "Bearer token"

    def test_custom_cache_ttl(self):
        p = ProviderWithHeaders()
        assert p.gtfs_cache_ttl == 3600


class TestGtfsProviderInit:
    """Test provider initialization."""

    @pytest.mark.asyncio
    async def test_init_creates_session_if_none(self):
        p = ConcreteProvider(session=None)
        assert p._owns_session is True
        await p.async_init()
        assert p._session is not None
        await p.async_close()

    @pytest.mark.asyncio
    async def test_init_uses_provided_session(self):
        session = MagicMock()
        p = ConcreteProvider(session=session)
        await p.async_init()
        assert p._session is session
        assert p._owns_session is False

    @pytest.mark.asyncio
    async def test_close_only_closes_owned_session(self):
        session = MagicMock()
        session.close = AsyncMock()
        p = ConcreteProvider(session=session)
        await p.async_init()
        await p.async_close()
        # Should NOT close the session since it was provided externally
        session.close.assert_not_called()


class TestGtfsProviderConnection:
    """Test connection testing."""

    @pytest.mark.asyncio
    async def test_connection_success(self):
        session = MagicMock()
        session.head = MagicMock(return_value=_mock_response(status=200))
        p = ConcreteProvider(session=session)
        result = await p.async_test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        session = MagicMock()
        session.head = MagicMock(return_value=_mock_response(status=404))
        p = ConcreteProvider(session=session)
        result = await p.async_test_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_connection_fallback_to_get(self):
        """Test that HEAD 405 falls back to GET with Range header."""
        session = MagicMock()
        head_resp = _mock_response(status=405)
        get_resp = _mock_response(status=206)
        session.head = MagicMock(return_value=head_resp)
        session.get = MagicMock(return_value=get_resp)
        p = ConcreteProvider(session=session)
        result = await p.async_test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        session = MagicMock()
        session.head = MagicMock(side_effect=aiohttp.ClientError("timeout"))
        p = ConcreteProvider(session=session)
        result = await p.async_test_connection()
        assert result is False


class TestGtfsProviderData:
    """Test GTFS data fetching and caching."""

    @pytest.mark.asyncio
    async def test_fetch_and_parse_gtfs(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        data = await p._ensure_gtfs_data()

        assert data is not None
        assert len(data.stops) == 3
        assert len(data.routes) == 2
        assert len(data.trips) == 2

    @pytest.mark.asyncio
    async def test_cache_prevents_refetch(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        # First fetch
        await p._ensure_gtfs_data()
        # Second fetch should use cache
        await p._ensure_gtfs_data()
        # Only one HTTP call
        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_expires(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        await p._ensure_gtfs_data()
        # Force cache expiry
        p._gtfs_last_fetch = time.time() - (DEFAULT_GTFS_CACHE_TTL + 1)
        await p._ensure_gtfs_data()
        assert session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_download_error_returns_stale(self):
        """When download fails, return stale cached data."""
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        # First call succeeds
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))
        p = ConcreteProvider(session=session)
        await p._ensure_gtfs_data()

        # Expire cache and fail on refetch
        p._gtfs_last_fetch = 0
        session.get = MagicMock(return_value=_mock_response(status=500))
        data = await p._ensure_gtfs_data()
        # Should return the stale data
        assert data is not None
        assert len(data.stops) == 3


class TestGtfsProviderStops:
    """Test async_get_stops."""

    @pytest.mark.asyncio
    async def test_get_all_stops(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        stops = await p.async_get_stops()

        # Should exclude station (location_type=1)
        assert len(stops) == 2
        names = [s.name for s in stops]
        assert "Praça A" in names
        assert "Estação B" in names
        assert "Station" not in names

    @pytest.mark.asyncio
    async def test_get_stops_with_search(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        stops = await p.async_get_stops(search="Praça")

        assert len(stops) == 1
        assert stops[0].name == "Praça A"

    @pytest.mark.asyncio
    async def test_get_stops_search_case_insensitive(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        stops = await p.async_get_stops(search="ESTAÇÃO")

        assert len(stops) == 1
        assert stops[0].name == "Estação B"

    @pytest.mark.asyncio
    async def test_stops_include_lines(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        stops = await p.async_get_stops()

        s1 = next(s for s in stops if s.stop_id == "S1")
        assert "15E" in s1.lines
        assert "28E" in s1.lines

    @pytest.mark.asyncio
    async def test_stops_include_municipality(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        stops = await p.async_get_stops()

        s1 = next(s for s in stops if s.stop_id == "S1")
        assert s1.municipality == "Lisboa"

    @pytest.mark.asyncio
    async def test_get_stops_no_data(self):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(status=500))

        p = ConcreteProvider(session=session)
        stops = await p.async_get_stops()
        assert stops == []


class TestGtfsProviderLines:
    """Test async_get_lines."""

    @pytest.mark.asyncio
    async def test_get_all_lines(self):
        gtfs_data = _make_gtfs_zip()
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(data=gtfs_data, status=200))

        p = ConcreteProvider(session=session)
        lines = await p.async_get_lines()

        assert len(lines) == 2
        line_ids = [l.line_id for l in lines]
        assert "R1" in line_ids
        assert "R2" in line_ids

        r1 = next(l for l in lines if l.line_id == "R1")
        assert r1.short_name == "15E"
        assert r1.long_name == "Praça - Algés"
        assert r1.color == "FFCC00"


class TestGtfsProviderVehicles:
    """Test async_get_vehicles with and without GTFS-RT."""

    @pytest.mark.asyncio
    async def test_no_rt_url_returns_empty(self):
        session = MagicMock()
        p = ConcreteProvider(session=session)
        vehicles = await p.async_get_vehicles()
        assert vehicles == []

    @pytest.mark.asyncio
    async def test_rt_error_returns_empty(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=Exception("connection error"))
        p = ProviderWithRT(session=session)
        vehicles = await p.async_get_vehicles()
        assert vehicles == []


class TestGtfsProviderAlerts:
    """Test async_get_alerts."""

    @pytest.mark.asyncio
    async def test_no_rt_url_returns_empty(self):
        session = MagicMock()
        p = ConcreteProvider(session=session)
        alerts = await p.async_get_alerts()
        assert alerts == []

    @pytest.mark.asyncio
    async def test_rt_error_returns_empty(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=Exception("timeout"))
        p = ProviderWithRT(session=session)
        alerts = await p.async_get_alerts()
        assert alerts == []
