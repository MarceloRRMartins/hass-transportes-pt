"""Tests for GTFS-RT protobuf parsing utilities."""

from __future__ import annotations

from google.transit import gtfs_realtime_pb2

from custom_components.transportes_pt.providers.gtfs_rt_utils import (
    parse_alerts,
    parse_trip_updates,
    parse_vehicle_positions,
)


def _make_vehicle_feed(*vehicles) -> bytes:
    """Build a GTFS-RT VehiclePositions feed from tuples."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 1000000

    for v in vehicles:
        entity = feed.entity.add()
        entity.id = v["id"]
        vp = entity.vehicle
        vp.vehicle.id = v.get("vehicle_id", v["id"])
        vp.trip.route_id = v.get("route_id", "")
        vp.trip.trip_id = v.get("trip_id", "")
        vp.position.latitude = v.get("lat", 0.0)
        vp.position.longitude = v.get("lon", 0.0)
        vp.position.bearing = v.get("bearing", 0.0)
        vp.position.speed = v.get("speed", 0.0)
        if "stop_id" in v:
            vp.stop_id = v["stop_id"]

    return feed.SerializeToString()


def _make_trip_update_feed(*updates) -> bytes:
    """Build a GTFS-RT TripUpdates feed."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 1000000

    for u in updates:
        entity = feed.entity.add()
        entity.id = u["id"]
        tu = entity.trip_update
        tu.trip.trip_id = u.get("trip_id", "T1")
        tu.trip.route_id = u.get("route_id", "R1")
        for stu_data in u.get("stop_times", []):
            stu = tu.stop_time_update.add()
            stu.stop_id = stu_data["stop_id"]
            if "arrival_time" in stu_data:
                stu.arrival.time = stu_data["arrival_time"]
                stu.arrival.delay = stu_data.get("delay", 0)
            if "departure_time" in stu_data:
                stu.departure.time = stu_data["departure_time"]

    return feed.SerializeToString()


def _make_alert_feed(*alerts) -> bytes:
    """Build a GTFS-RT ServiceAlerts feed."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 1000000

    for a in alerts:
        entity = feed.entity.add()
        entity.id = a["id"]
        alert = entity.alert

        if "title" in a:
            t = alert.header_text.translation.add()
            t.text = a["title"]
            t.language = a.get("lang", "pt")

        if "description" in a:
            t = alert.description_text.translation.add()
            t.text = a["description"]
            t.language = a.get("lang", "pt")

        for route_id in a.get("routes", []):
            ie = alert.informed_entity.add()
            ie.route_id = route_id

        for stop_id in a.get("stops", []):
            ie = alert.informed_entity.add()
            ie.stop_id = stop_id

        if "start" in a or "end" in a:
            period = alert.active_period.add()
            if "start" in a:
                period.start = a["start"]
            if "end" in a:
                period.end = a["end"]

    return feed.SerializeToString()


class TestParseVehiclePositions:
    """Test vehicle position parsing."""

    def test_basic_vehicle(self):
        data = _make_vehicle_feed(
            {"id": "V1", "route_id": "R1", "lat": 38.7, "lon": -9.1, "bearing": 90.0, "speed": 5.0}
        )
        result = parse_vehicle_positions(data)
        assert len(result) == 1
        v = result[0]
        assert v.vehicle_id == "V1"
        assert v.line_id == "R1"
        assert abs(v.latitude - 38.7) < 0.001
        assert abs(v.longitude - (-9.1)) < 0.001
        assert v.heading == 90.0
        assert v.speed == 5.0

    def test_filter_by_line(self):
        data = _make_vehicle_feed(
            {"id": "V1", "route_id": "R1", "lat": 38.7, "lon": -9.1},
            {"id": "V2", "route_id": "R2", "lat": 38.8, "lon": -9.2},
        )
        result = parse_vehicle_positions(data, line_ids=["R1"])
        assert len(result) == 1
        assert result[0].vehicle_id == "V1"

    def test_skip_no_position(self):
        data = _make_vehicle_feed({"id": "V1", "route_id": "R1", "lat": 0.0, "lon": 0.0})
        result = parse_vehicle_positions(data)
        assert len(result) == 0

    def test_empty_feed(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        result = parse_vehicle_positions(feed.SerializeToString())
        assert result == []

    def test_vehicle_with_stop_id(self):
        data = _make_vehicle_feed(
            {"id": "V1", "route_id": "R1", "lat": 38.7, "lon": -9.1, "stop_id": "S100"}
        )
        result = parse_vehicle_positions(data)
        assert result[0].stop_id == "S100"


class TestParseTripUpdates:
    """Test trip update parsing."""

    def test_basic_update(self):
        data = _make_trip_update_feed(
            {
                "id": "E1",
                "trip_id": "T1",
                "route_id": "R1",
                "stop_times": [
                    {"stop_id": "S1", "arrival_time": 1700000000, "delay": 60},
                ],
            }
        )
        result = parse_trip_updates(data, "S1")
        assert len(result) == 1
        assert result[0]["trip_id"] == "T1"
        assert result[0]["route_id"] == "R1"
        assert result[0]["arrival_time"] == 1700000000
        assert result[0]["delay"] == 60

    def test_filters_by_stop(self):
        data = _make_trip_update_feed(
            {
                "id": "E1",
                "stop_times": [
                    {"stop_id": "S1", "arrival_time": 1700000000},
                    {"stop_id": "S2", "arrival_time": 1700000100},
                ],
            }
        )
        result = parse_trip_updates(data, "S2")
        assert len(result) == 1
        assert result[0]["stop_id"] == "S2"

    def test_departure_fallback(self):
        data = _make_trip_update_feed(
            {
                "id": "E1",
                "stop_times": [
                    {"stop_id": "S1", "departure_time": 1700000000},
                ],
            }
        )
        result = parse_trip_updates(data, "S1")
        assert len(result) == 1
        assert result[0]["arrival_time"] == 1700000000

    def test_empty_feed(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        result = parse_trip_updates(feed.SerializeToString(), "S1")
        assert result == []


class TestParseAlerts:
    """Test alert parsing."""

    def test_basic_alert(self):
        data = _make_alert_feed(
            {
                "id": "A1",
                "title": "Greve",
                "description": "Paragem de serviço",
                "routes": ["R1", "R2"],
                "stops": ["S1"],
                "start": 1700000000,
                "end": 1700100000,
            }
        )
        result = parse_alerts(data)
        assert len(result) == 1
        a = result[0]
        assert a.alert_id == "A1"
        assert a.title == "Greve"
        assert a.description == "Paragem de serviço"
        assert a.affected_lines == ["R1", "R2"]
        assert a.affected_stops == ["S1"]
        assert a.start_time == "1700000000"
        assert a.end_time == "1700100000"

    def test_empty_feed(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        result = parse_alerts(feed.SerializeToString())
        assert result == []

    def test_prefers_portuguese(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        entity = feed.entity.add()
        entity.id = "A1"
        alert = entity.alert
        t_en = alert.header_text.translation.add()
        t_en.text = "Strike"
        t_en.language = "en"
        t_pt = alert.header_text.translation.add()
        t_pt.text = "Greve"
        t_pt.language = "pt"

        result = parse_alerts(feed.SerializeToString())
        assert result[0].title == "Greve"
