"""Carris Metropolitana transit provider."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from ..const import CARRIS_BASE_URL
from . import (
    Alert,
    Arrival,
    Line,
    Stop,
    TransitProvider,
    VehiclePosition,
)

_LOGGER = logging.getLogger(__name__)


class CarrisMetropolitanaProvider(TransitProvider):
    """Provider for Carris Metropolitana (Lisboa/AML) API v2."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the provider."""
        self._session = session
        self._owns_session = session is None

    @property
    def provider_id(self) -> str:
        """Unique identifier for this provider."""
        return "carris_metropolitana"

    @property
    def name(self) -> str:
        """Human-readable name."""
        return "Carris Metropolitana"

    async def async_init(self) -> None:
        """Initialize the provider session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

    async def async_close(self) -> None:
        """Close the provider session."""
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    async def async_test_connection(self) -> bool:
        """Test if the Carris API is reachable."""
        try:
            async with self._session.get(
                f"{CARRIS_BASE_URL}/lines", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, TimeoutError):
            return False

    async def async_get_arrivals(self, stop_id: str) -> list[Arrival]:
        """Get estimated arrivals for a stop."""
        url = f"{CARRIS_BASE_URL}/arrivals/by_stop/{stop_id}"
        data = await self._api_get(url)
        if not data:
            return []

        arrivals: list[Arrival] = []
        for item in data:
            arrivals.append(
                Arrival(
                    line_id=item.get("line_id", ""),
                    line_name=item.get("line_id", ""),
                    destination=item.get("headsign", ""),
                    estimated_arrival=item.get("estimated_arrival"),
                    scheduled_arrival=item.get("scheduled_arrival"),
                    estimated_arrival_unix=item.get("estimated_arrival_unix"),
                    scheduled_arrival_unix=item.get("scheduled_arrival_unix"),
                    vehicle_id=item.get("vehicle_id"),
                    trip_id=item.get("trip_id"),
                )
            )
        return arrivals

    async def async_get_alerts(self) -> list[Alert]:
        """Get active service alerts."""
        url = f"{CARRIS_BASE_URL}/alerts"
        data = await self._api_get(url)
        if not data:
            return []

        alerts: list[Alert] = []
        entities = data if isinstance(data, list) else data.get("entity", [])
        for entity in entities:
            alert_data = entity.get("alert", entity)
            header = alert_data.get("headerText", {})
            desc = alert_data.get("descriptionText", {})

            title = self._extract_translation(header)
            description = self._extract_translation(desc)

            informed = alert_data.get("informedEntity", [])
            affected_lines = []
            affected_stops = []
            for ie in informed:
                if route_id := ie.get("routeId"):
                    affected_lines.append(route_id)
                if stop_id := ie.get("stopId"):
                    affected_stops.append(stop_id)

            active_period = alert_data.get("activePeriod", [{}])
            start_time = None
            end_time = None
            if active_period:
                start_time = active_period[0].get("start")
                end_time = active_period[0].get("end")

            alerts.append(
                Alert(
                    alert_id=entity.get("id", ""),
                    title=title,
                    description=description,
                    affected_lines=affected_lines,
                    affected_stops=affected_stops,
                    start_time=str(start_time) if start_time else None,
                    end_time=str(end_time) if end_time else None,
                    url=alert_data.get("url", {}).get("translation", [{}])[0].get("text"),
                )
            )
        return alerts

    async def async_get_vehicles(self, line_ids: list[str] | None = None) -> list[VehiclePosition]:
        """Get real-time vehicle positions."""
        url = f"{CARRIS_BASE_URL}/vehicles"
        data = await self._api_get(url)
        if not data:
            return []

        vehicles: list[VehiclePosition] = []
        entities = data if isinstance(data, list) else data.get("entity", [])
        for entity in entities:
            vehicle = entity.get("vehicle", entity)
            position = vehicle.get("position", {})
            trip = vehicle.get("trip", {})
            line_id = trip.get("routeId", vehicle.get("lineId", ""))

            if line_ids and line_id not in line_ids:
                continue

            lat = position.get("latitude") or vehicle.get("lat")
            lon = position.get("longitude") or vehicle.get("lon")
            if lat is None or lon is None:
                continue

            vehicles.append(
                VehiclePosition(
                    vehicle_id=vehicle.get("vehicle", {}).get("id", entity.get("id", "")),
                    line_id=line_id,
                    trip_id=trip.get("tripId", vehicle.get("tripId")),
                    latitude=float(lat),
                    longitude=float(lon),
                    heading=position.get("bearing") or vehicle.get("heading"),
                    speed=position.get("speed") or vehicle.get("speed"),
                    stop_id=vehicle.get("stopId"),
                )
            )
        return vehicles

    async def async_get_stops(self, search: str | None = None) -> list[Stop]:
        """Get stops, optionally filtered by search term."""
        url = f"{CARRIS_BASE_URL}/stops"
        data = await self._api_get(url)
        if not data:
            return []

        stops: list[Stop] = []
        for item in data:
            name = item.get("long_name", item.get("name", ""))
            if search and search.lower() not in name.lower():
                continue
            stops.append(
                Stop(
                    stop_id=item.get("id", ""),
                    name=name,
                    latitude=float(item.get("lat", 0)),
                    longitude=float(item.get("lon", 0)),
                    lines=item.get("line_ids", []),
                    municipality=item.get("municipality_name"),
                )
            )
        return stops

    async def async_get_lines(self) -> list[Line]:
        """Get all lines."""
        url = f"{CARRIS_BASE_URL}/lines"
        data = await self._api_get(url)
        if not data:
            return []

        lines: list[Line] = []
        for item in data:
            lines.append(
                Line(
                    line_id=item.get("id", item.get("line_id", "")),
                    short_name=item.get("short_name", ""),
                    long_name=item.get("long_name", ""),
                    color=item.get("color"),
                )
            )
        return lines

    async def _api_get(self, url: str) -> Any:
        """Make a GET request to the Carris API."""
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Carris API returned %s for %s", resp.status, url)
                    return None
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Error fetching %s: %s", url, err)
            return None

    @staticmethod
    def _extract_translation(text_obj: dict) -> str:
        """Extract text from a GTFS-RT translation object."""
        if not text_obj:
            return ""
        translations = text_obj.get("translation", [])
        if translations:
            return translations[0].get("text", "")
        return text_obj.get("text", "")
