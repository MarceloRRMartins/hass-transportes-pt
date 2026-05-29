"""Base GTFS provider that implements TransitProvider using GTFS static + optional GTFS-RT."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import aiohttp

from . import (
    Alert,
    Arrival,
    Line,
    Stop,
    TransitProvider,
    VehiclePosition,
)
from .gtfs_utils import GtfsData, get_scheduled_arrivals, parse_gtfs_zip

_LOGGER = logging.getLogger(__name__)

# Default cache TTL: 24 hours
DEFAULT_GTFS_CACHE_TTL = 86400


class GtfsProvider(TransitProvider):
    """Base provider for operators using standard GTFS Static feeds.

    Subclasses must define:
        - provider_id (property)
        - name (property)
        - gtfs_url (property)

    Optionally override:
        - gtfs_rt_vehicle_positions_url
        - gtfs_rt_trip_updates_url
        - gtfs_rt_alerts_url
        - gtfs_headers (for custom HTTP headers)
        - gtfs_cache_ttl (seconds, default 24h)
    """

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the GTFS provider."""
        self._session = session
        self._owns_session = session is None
        self._gtfs_data: GtfsData | None = None
        self._gtfs_last_fetch: float = 0

    @property
    def gtfs_url(self) -> str:
        """URL to download the GTFS Static ZIP file. Must be overridden."""
        raise NotImplementedError

    @property
    def gtfs_rt_vehicle_positions_url(self) -> str | None:
        """URL for GTFS-RT VehiclePositions feed. None if not available."""
        return None

    @property
    def gtfs_rt_trip_updates_url(self) -> str | None:
        """URL for GTFS-RT TripUpdates feed. None if not available."""
        return None

    @property
    def gtfs_rt_alerts_url(self) -> str | None:
        """URL for GTFS-RT ServiceAlerts feed. None if not available."""
        return None

    @property
    def gtfs_headers(self) -> dict[str, str]:
        """Custom HTTP headers for GTFS downloads."""
        return {}

    @property
    def gtfs_cache_ttl(self) -> int:
        """Cache TTL in seconds for the GTFS static data."""
        return DEFAULT_GTFS_CACHE_TTL

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
        """Test if the GTFS feed is reachable."""
        try:
            async with self._session.head(
                self.gtfs_url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers=self.gtfs_headers,
                allow_redirects=True,
            ) as resp:
                # Some servers don't support HEAD, try GET with range
                if resp.status == 405:
                    async with self._session.get(
                        self.gtfs_url,
                        timeout=aiohttp.ClientTimeout(total=15),
                        headers={**self.gtfs_headers, "Range": "bytes=0-0"},
                        allow_redirects=True,
                    ) as resp2:
                        return resp2.status in (200, 206)
                return resp.status == 200
        except (aiohttp.ClientError, TimeoutError):
            return False

    async def _ensure_gtfs_data(self) -> GtfsData | None:
        """Download and parse GTFS data if cache is stale."""
        now = time.time()
        if self._gtfs_data and (now - self._gtfs_last_fetch) < self.gtfs_cache_ttl:
            return self._gtfs_data

        try:
            _LOGGER.debug("Downloading GTFS feed from %s", self.gtfs_url)
            async with self._session.get(
                self.gtfs_url,
                timeout=aiohttp.ClientTimeout(total=120),
                headers=self.gtfs_headers,
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "%s: GTFS download returned %s", self.name, resp.status
                    )
                    return self._gtfs_data  # Return stale data if available
                data = await resp.read()

            self._gtfs_data = parse_gtfs_zip(data)
            self._gtfs_last_fetch = now
            _LOGGER.info(
                "%s: GTFS loaded — %d stops, %d routes, %d trips",
                self.name,
                len(self._gtfs_data.stops),
                len(self._gtfs_data.routes),
                len(self._gtfs_data.trips),
            )
            return self._gtfs_data
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("%s: Error downloading GTFS: %s", self.name, err)
            return self._gtfs_data
        except Exception as err:
            _LOGGER.error("%s: Error parsing GTFS: %s", self.name, err)
            return self._gtfs_data

    async def async_get_arrivals(self, stop_id: str) -> list[Arrival]:
        """Get scheduled arrivals for a stop from GTFS static data."""
        gtfs = await self._ensure_gtfs_data()
        if not gtfs:
            return []

        now = datetime.now(tz=timezone.utc)

        # Get arrivals from GTFS-RT TripUpdates if available
        rt_arrivals = await self._get_rt_arrivals(stop_id)
        if rt_arrivals:
            return rt_arrivals

        # Fall back to static schedule
        scheduled = get_scheduled_arrivals(gtfs, stop_id, now)
        return [
            Arrival(
                line_id=a["line_id"],
                line_name=a["line_name"],
                destination=a["destination"],
                estimated_arrival=None,
                scheduled_arrival=a["scheduled_arrival"],
                estimated_arrival_unix=None,
                scheduled_arrival_unix=a.get("scheduled_arrival_unix"),
                vehicle_id=None,
                trip_id=a.get("trip_id"),
            )
            for a in scheduled
        ]

    async def _get_rt_arrivals(self, stop_id: str) -> list[Arrival] | None:
        """Try to get arrivals from GTFS-RT TripUpdates."""
        url = self.gtfs_rt_trip_updates_url
        if not url:
            return None

        try:
            from .gtfs_rt_utils import parse_trip_updates

            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers=self.gtfs_headers,
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()

            updates = parse_trip_updates(data, stop_id)
            if not updates:
                return None

            gtfs = self._gtfs_data
            arrivals: list[Arrival] = []
            for u in updates:
                route_id = u.get("route_id", "")
                route = gtfs.routes.get(route_id, {}) if gtfs else {}
                trip = gtfs.trips.get(u.get("trip_id", ""), {}) if gtfs else {}

                arrival_unix = u.get("arrival_time")
                arrival_iso = (
                    datetime.fromtimestamp(arrival_unix, tz=timezone.utc).isoformat()
                    if arrival_unix
                    else None
                )

                arrivals.append(
                    Arrival(
                        line_id=route_id,
                        line_name=route.get(
                            "route_short_name", route.get("route_long_name", route_id)
                        ),
                        destination=trip.get("trip_headsign", route.get("route_long_name", "")),
                        estimated_arrival=arrival_iso,
                        scheduled_arrival=None,
                        estimated_arrival_unix=arrival_unix,
                        scheduled_arrival_unix=None,
                        vehicle_id=None,
                        trip_id=u.get("trip_id"),
                    )
                )

            arrivals.sort(key=lambda a: a.estimated_arrival_unix or 0)
            return arrivals[:10]
        except Exception as err:
            _LOGGER.debug("%s: GTFS-RT trip updates error: %s", self.name, err)
            return None

    async def async_get_alerts(self) -> list[Alert]:
        """Get service alerts from GTFS-RT if available."""
        url = self.gtfs_rt_alerts_url
        if not url:
            return []

        try:
            from .gtfs_rt_utils import parse_alerts

            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers=self.gtfs_headers,
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.read()

            return parse_alerts(data)
        except Exception as err:
            _LOGGER.debug("%s: GTFS-RT alerts error: %s", self.name, err)
            return []

    async def async_get_vehicles(
        self, line_ids: list[str] | None = None
    ) -> list[VehiclePosition]:
        """Get vehicle positions from GTFS-RT if available."""
        url = self.gtfs_rt_vehicle_positions_url
        if not url:
            return []

        try:
            from .gtfs_rt_utils import parse_vehicle_positions

            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers=self.gtfs_headers,
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.read()

            return parse_vehicle_positions(data, line_ids)
        except Exception as err:
            _LOGGER.debug("%s: GTFS-RT vehicles error: %s", self.name, err)
            return []

    async def async_get_stops(self, search: str | None = None) -> list[Stop]:
        """Get stops from GTFS static data."""
        gtfs = await self._ensure_gtfs_data()
        if not gtfs:
            return []

        stops: list[Stop] = []
        for stop_id, stop_data in gtfs.stops.items():
            # Skip non-stops (stations, entrances, etc.)
            location_type = stop_data.get("location_type", "0")
            if location_type not in ("0", ""):
                continue

            name = stop_data.get("stop_name", "")
            if search and search.lower() not in name.lower():
                continue

            lat = stop_data.get("stop_lat", "0")
            lon = stop_data.get("stop_lon", "0")

            # Get lines serving this stop
            route_ids = gtfs.stop_routes.get(stop_id, set())
            line_names = []
            for rid in route_ids:
                route = gtfs.routes.get(rid, {})
                line_names.append(
                    route.get("route_short_name", route.get("route_long_name", rid))
                )

            stops.append(
                Stop(
                    stop_id=stop_id,
                    name=name,
                    latitude=float(lat) if lat else 0.0,
                    longitude=float(lon) if lon else 0.0,
                    lines=sorted(line_names),
                    municipality=stop_data.get("zone_id"),
                )
            )

        return stops

    async def async_get_lines(self) -> list[Line]:
        """Get all lines from GTFS static data."""
        gtfs = await self._ensure_gtfs_data()
        if not gtfs:
            return []

        lines: list[Line] = []
        for route_id, route_data in gtfs.routes.items():
            lines.append(
                Line(
                    line_id=route_id,
                    short_name=route_data.get("route_short_name", ""),
                    long_name=route_data.get("route_long_name", ""),
                    color=route_data.get("route_color"),
                )
            )

        return lines
