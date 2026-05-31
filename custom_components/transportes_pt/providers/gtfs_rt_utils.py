"""GTFS Realtime (Protocol Buffers) parser utilities."""

from __future__ import annotations

import logging
from typing import Any

from google.transit import gtfs_realtime_pb2

from . import Alert, VehiclePosition

_LOGGER = logging.getLogger(__name__)


def parse_vehicle_positions(
    data: bytes, line_ids: list[str] | None = None
) -> list[VehiclePosition]:
    """Parse GTFS-RT VehiclePositions feed.

    Args:
        data: Raw protobuf bytes.
        line_ids: Optional filter by route/line IDs.

    Returns:
        List of VehiclePosition objects.
    """
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)

    vehicles: list[VehiclePosition] = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue

        vehicle = entity.vehicle
        position = vehicle.position
        trip = vehicle.trip

        route_id = trip.route_id if trip.route_id else ""
        if line_ids and route_id not in line_ids:
            continue

        if not position.latitude or not position.longitude:
            continue

        vehicle_id = vehicle.vehicle.id if vehicle.vehicle.id else entity.id

        vehicles.append(
            VehiclePosition(
                vehicle_id=vehicle_id,
                line_id=route_id,
                trip_id=trip.trip_id if trip.trip_id else None,
                latitude=position.latitude,
                longitude=position.longitude,
                heading=position.bearing if position.bearing else None,
                speed=position.speed if position.speed else None,
                stop_id=vehicle.stop_id if vehicle.stop_id else None,
            )
        )

    return vehicles


def parse_trip_updates(data: bytes, stop_id: str) -> list[dict[str, Any]]:
    """Parse GTFS-RT TripUpdates for a specific stop.

    Returns list of dicts with arrival time info for the given stop.
    """
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)

    updates: list[dict[str, Any]] = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        trip_update = entity.trip_update
        trip = trip_update.trip

        for stu in trip_update.stop_time_update:
            if stu.stop_id != stop_id:
                continue

            arrival_time = None
            departure_time = None

            if stu.HasField("arrival") and stu.arrival.time:
                arrival_time = stu.arrival.time
            if stu.HasField("departure") and stu.departure.time:
                departure_time = stu.departure.time

            updates.append(
                {
                    "trip_id": trip.trip_id,
                    "route_id": trip.route_id,
                    "stop_id": stop_id,
                    "arrival_time": arrival_time or departure_time,
                    "delay": stu.arrival.delay if stu.HasField("arrival") else 0,
                }
            )

    return updates


def parse_alerts(data: bytes) -> list[Alert]:
    """Parse GTFS-RT ServiceAlerts feed.

    Returns list of Alert objects.
    """
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)

    alerts: list[Alert] = []
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue

        alert = entity.alert

        # Extract translated text
        title = _get_translation(alert.header_text)
        description = _get_translation(alert.description_text)

        # Extract affected entities
        affected_lines: list[str] = []
        affected_stops: list[str] = []
        for ie in alert.informed_entity:
            if ie.route_id:
                affected_lines.append(ie.route_id)
            if ie.stop_id:
                affected_stops.append(ie.stop_id)

        # Active periods
        start_time = None
        end_time = None
        if alert.active_period:
            period = alert.active_period[0]
            start_time = str(period.start) if period.start else None
            end_time = str(period.end) if period.end else None

        # URL
        url = _get_translation(alert.url) if alert.HasField("url") else None

        alerts.append(
            Alert(
                alert_id=entity.id,
                title=title,
                description=description,
                affected_lines=affected_lines,
                affected_stops=affected_stops,
                start_time=start_time,
                end_time=end_time,
                url=url,
            )
        )

    return alerts


def _get_translation(translated_string) -> str:
    """Extract text from a GTFS-RT TranslatedString, preferring Portuguese."""
    if not translated_string or not translated_string.translation:
        return ""
    # Prefer Portuguese
    for t in translated_string.translation:
        if t.language in ("pt", "pt-PT", "pt-BR"):
            return t.text
    # Fallback to first translation
    return translated_string.translation[0].text
