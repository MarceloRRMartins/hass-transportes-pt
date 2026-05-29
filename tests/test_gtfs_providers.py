"""Tests for GTFS provider infrastructure."""

from __future__ import annotations

import io
import csv
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.transportes_pt.providers.gtfs_utils import (
    GtfsData,
    get_scheduled_arrivals,
    gtfs_time_to_seconds,
    is_service_active,
    parse_gtfs_zip,
)


def _make_gtfs_zip(
    stops=None, routes=None, trips=None, stop_times=None, calendar=None, calendar_dates=None
) -> bytes:
    """Create a minimal GTFS ZIP in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if stops is not None:
            zf.writestr("stops.txt", _csv_str(stops))
        if routes is not None:
            zf.writestr("routes.txt", _csv_str(routes))
        if trips is not None:
            zf.writestr("trips.txt", _csv_str(trips))
        if stop_times is not None:
            zf.writestr("stop_times.txt", _csv_str(stop_times))
        if calendar is not None:
            zf.writestr("calendar.txt", _csv_str(calendar))
        if calendar_dates is not None:
            zf.writestr("calendar_dates.txt", _csv_str(calendar_dates))
    return buf.getvalue()


def _csv_str(rows: list[dict]) -> str:
    """Convert list of dicts to CSV string."""
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# -- Test GTFS time parsing --


class TestGtfsTimeParsing:
    """Test GTFS time string conversion."""

    def test_normal_time(self):
        assert gtfs_time_to_seconds("08:30:00") == 8 * 3600 + 30 * 60

    def test_midnight(self):
        assert gtfs_time_to_seconds("00:00:00") == 0

    def test_after_midnight(self):
        # GTFS allows times > 24:00 for services running past midnight
        assert gtfs_time_to_seconds("25:10:30") == 25 * 3600 + 10 * 60 + 30

    def test_end_of_day(self):
        assert gtfs_time_to_seconds("23:59:59") == 23 * 3600 + 59 * 60 + 59


# -- Test GTFS ZIP parsing --


class TestParseGtfsZip:
    """Test parsing GTFS Static ZIP files."""

    def test_parse_stops(self):
        data = _make_gtfs_zip(
            stops=[
                {
                    "stop_id": "S001",
                    "stop_name": "Praça do Comércio",
                    "stop_lat": "38.7077",
                    "stop_lon": "-9.1365",
                    "location_type": "0",
                },
                {
                    "stop_id": "S002",
                    "stop_name": "Cais do Sodré",
                    "stop_lat": "38.7069",
                    "stop_lon": "-9.1438",
                    "location_type": "0",
                },
            ],
            routes=[],
            trips=[],
            stop_times=[],
        )
        gtfs = parse_gtfs_zip(data)
        assert len(gtfs.stops) == 2
        assert gtfs.stops["S001"]["stop_name"] == "Praça do Comércio"
        assert gtfs.stops["S002"]["stop_lat"] == "38.7069"

    def test_parse_routes(self):
        data = _make_gtfs_zip(
            stops=[],
            routes=[
                {
                    "route_id": "R1",
                    "route_short_name": "15E",
                    "route_long_name": "Praça da Figueira - Algés",
                    "route_type": "0",
                    "route_color": "FFCC00",
                },
            ],
            trips=[],
            stop_times=[],
        )
        gtfs = parse_gtfs_zip(data)
        assert len(gtfs.routes) == 1
        assert gtfs.routes["R1"]["route_short_name"] == "15E"
        assert gtfs.routes["R1"]["route_color"] == "FFCC00"

    def test_parse_trips_and_stop_times(self):
        data = _make_gtfs_zip(
            stops=[
                {"stop_id": "S001", "stop_name": "A", "stop_lat": "38.7", "stop_lon": "-9.1", "location_type": "0"},
            ],
            routes=[
                {"route_id": "R1", "route_short_name": "15E", "route_long_name": "A-B", "route_type": "0"},
            ],
            trips=[
                {"trip_id": "T1", "route_id": "R1", "service_id": "SVC1", "trip_headsign": "Algés"},
            ],
            stop_times=[
                {"trip_id": "T1", "stop_id": "S001", "arrival_time": "08:00:00", "departure_time": "08:01:00", "stop_sequence": "1"},
            ],
        )
        gtfs = parse_gtfs_zip(data)
        assert "T1" in gtfs.trips
        assert gtfs.trips["T1"]["route_id"] == "R1"
        assert len(gtfs.stop_times) == 1
        # stop_routes should map S001 -> {R1}
        assert "R1" in gtfs.stop_routes.get("S001", set())

    def test_parse_calendar(self):
        data = _make_gtfs_zip(
            stops=[],
            routes=[],
            trips=[],
            stop_times=[],
            calendar=[
                {
                    "service_id": "SVC1",
                    "monday": "1",
                    "tuesday": "1",
                    "wednesday": "1",
                    "thursday": "1",
                    "friday": "1",
                    "saturday": "0",
                    "sunday": "0",
                    "start_date": "20260101",
                    "end_date": "20261231",
                },
            ],
        )
        gtfs = parse_gtfs_zip(data)
        assert "SVC1" in gtfs.calendar
        assert gtfs.calendar["SVC1"]["monday"] == "1"
        assert gtfs.calendar["SVC1"]["saturday"] == "0"

    def test_empty_zip(self):
        """Test that a ZIP with no GTFS files still returns a valid GtfsData."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            pass  # Empty ZIP
        gtfs = parse_gtfs_zip(buf.getvalue())
        assert gtfs.stops == {}
        assert gtfs.routes == {}

    def test_bom_handling(self):
        """Test that BOM (byte order mark) in CSV is handled."""
        # Create CSV with BOM prefix
        stops_csv = "\ufeffstop_id,stop_name,stop_lat,stop_lon,location_type\nS001,Test,38.7,-9.1,0\n"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("stops.txt", stops_csv)
            zf.writestr("routes.txt", "route_id,route_short_name,route_long_name,route_type\n")
            zf.writestr("trips.txt", "trip_id,route_id,service_id,trip_headsign\n")
            zf.writestr("stop_times.txt", "trip_id,stop_id,arrival_time,departure_time,stop_sequence\n")
        gtfs = parse_gtfs_zip(buf.getvalue())
        assert "S001" in gtfs.stops


# -- Test service active check --


class TestIsServiceActive:
    """Test service day/date activity checking."""

    def test_service_active_on_weekday(self):
        from datetime import date

        gtfs = GtfsData(
            agencies={},
            stops={},
            routes={},
            trips={},
            stop_times=[],
            calendar={
                "SVC1": {
                    "service_id": "SVC1",
                    "monday": "1", "tuesday": "1", "wednesday": "1",
                    "thursday": "1", "friday": "1", "saturday": "0", "sunday": "0",
                    "start_date": "20260101", "end_date": "20261231",
                }
            },
            calendar_dates={},
            stop_routes={},
        )
        # 2026-05-29 is a Friday
        assert is_service_active(gtfs, "SVC1", date(2026, 5, 29)) is True
        # Saturday
        assert is_service_active(gtfs, "SVC1", date(2026, 5, 30)) is False

    def test_service_exception_added(self):
        from datetime import date

        gtfs = GtfsData(
            agencies={},
            stops={},
            routes={},
            trips={},
            stop_times=[],
            calendar={
                "SVC1": {
                    "service_id": "SVC1",
                    "monday": "0", "tuesday": "0", "wednesday": "0",
                    "thursday": "0", "friday": "0", "saturday": "0", "sunday": "0",
                    "start_date": "20260101", "end_date": "20261231",
                }
            },
            calendar_dates=[
                {"service_id": "SVC1", "date": "20260529", "exception_type": "1"}
            ],
            stop_routes={},
        )
        # Normally no service on Friday but exception adds it
        assert is_service_active(gtfs, "SVC1", date(2026, 5, 29)) is True

    def test_service_exception_removed(self):
        from datetime import date

        gtfs = GtfsData(
            agencies={},
            stops={},
            routes={},
            trips={},
            stop_times=[],
            calendar={
                "SVC1": {
                    "service_id": "SVC1",
                    "monday": "1", "tuesday": "1", "wednesday": "1",
                    "thursday": "1", "friday": "1", "saturday": "1", "sunday": "1",
                    "start_date": "20260101", "end_date": "20261231",
                }
            },
            calendar_dates=[
                {"service_id": "SVC1", "date": "20260529", "exception_type": "2"}
            ],
            stop_routes={},
        )
        # Normally service on Friday but exception removes it
        assert is_service_active(gtfs, "SVC1", date(2026, 5, 29)) is False


# -- Test provider imports and properties --


class TestProviderProperties:
    """Test that all providers have correct properties."""

    def test_all_providers_import(self):
        """Verify all provider classes can be imported."""
        from custom_components.transportes_pt.providers.carris import CarrisProvider
        from custom_components.transportes_pt.providers.stcp import StcpProvider
        from custom_components.transportes_pt.providers.metro_porto import MetroPortoProvider
        from custom_components.transportes_pt.providers.cp import CpProvider
        from custom_components.transportes_pt.providers.metro_lisboa import MetroLisboaProvider
        from custom_components.transportes_pt.providers.fertagus import FertagusProvider
        from custom_components.transportes_pt.providers.transtejo import TranstejoProvider
        from custom_components.transportes_pt.providers.mts import MtsProvider
        from custom_components.transportes_pt.providers.tcb import TcbProvider
        from custom_components.transportes_pt.providers.tub import TubProvider
        from custom_components.transportes_pt.providers.horarios_funchal import HorariosFunchalProvider
        from custom_components.transportes_pt.providers.mobicascais import MobiCascaisProvider
        from custom_components.transportes_pt.providers.cim_tamega_sousa import CimTsProvider
        from custom_components.transportes_pt.providers.busway_coimbra import BuswayCoimbraProvider
        from custom_components.transportes_pt.providers.busway_cira import BuswayCiraProvider
        from custom_components.transportes_pt.providers.mobiave import MobiaveProvider
        from custom_components.transportes_pt.providers.tuba import TubaProvider
        from custom_components.transportes_pt.providers.guimabus import GuimabusProvider

        providers = [
            CarrisProvider(), StcpProvider(), MetroPortoProvider(), CpProvider(),
            MetroLisboaProvider(), FertagusProvider(), TranstejoProvider(), MtsProvider(),
            TcbProvider(), TubProvider(), HorariosFunchalProvider(), MobiCascaisProvider(),
            CimTsProvider(), BuswayCoimbraProvider(), BuswayCiraProvider(),
            MobiaveProvider(), TubaProvider(), GuimabusProvider(),
        ]
        assert len(providers) == 18
        for p in providers:
            assert p.provider_id
            assert p.name
            assert p.gtfs_url
            assert p.gtfs_url.startswith("http")

    def test_metro_lisboa_custom_headers(self):
        """Test Metro de Lisboa has User-Agent header."""
        from custom_components.transportes_pt.providers.metro_lisboa import MetroLisboaProvider

        p = MetroLisboaProvider()
        assert "User-Agent" in p.gtfs_headers

    def test_carris_has_realtime(self):
        """Test Carris CCFL has GTFS-RT vehicle positions URL."""
        from custom_components.transportes_pt.providers.carris import CarrisProvider

        p = CarrisProvider()
        assert p.gtfs_rt_vehicle_positions_url is not None
        assert "vehiclepositions" in p.gtfs_rt_vehicle_positions_url

    def test_default_provider_no_realtime(self):
        """Test that basic providers have no GTFS-RT URLs."""
        from custom_components.transportes_pt.providers.cp import CpProvider

        p = CpProvider()
        assert p.gtfs_rt_vehicle_positions_url is None
        assert p.gtfs_rt_trip_updates_url is None
        assert p.gtfs_rt_alerts_url is None

    def test_stcp_has_ngsi_override(self):
        """Test STCP overrides async_get_vehicles for NGSI."""
        from custom_components.transportes_pt.providers.stcp import StcpProvider
        from custom_components.transportes_pt.providers.gtfs_base import GtfsProvider

        p = StcpProvider()
        # The method should be overridden (not from base class)
        assert type(p).async_get_vehicles is not GtfsProvider.async_get_vehicles
