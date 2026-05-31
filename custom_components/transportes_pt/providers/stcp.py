"""STCP (Sociedade de Transportes Colectivos do Porto) provider."""

from __future__ import annotations

import logging

import aiohttp

from . import VehiclePosition
from .gtfs_base import GtfsProvider

_LOGGER = logging.getLogger(__name__)

# CKAN API to dynamically get latest GTFS resource
STCP_CKAN_API = "https://opendata.porto.digital/api/3/action/package_show"
STCP_DATASET_ID = "5275c986-592c-43f5-8f87-aabbd4e4f3a4"

# NGSI/FIWARE real-time vehicle positions
STCP_REALTIME_URL = (
    "https://broker.fiware.urbanplatform.portodigital.pt/v2/entities?q=vehicleType==bus&limit=1000"
)


class StcpProvider(GtfsProvider):
    """Provider for STCP — Porto city buses."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)
        self._resolved_gtfs_url: str | None = None

    @property
    def provider_id(self) -> str:
        return "stcp"

    @property
    def name(self) -> str:
        return "STCP (Porto)"

    @property
    def gtfs_url(self) -> str:
        if self._resolved_gtfs_url:
            return self._resolved_gtfs_url
        # Fallback to known-good URL
        return (
            "https://opendata.porto.digital/dataset/"
            "5275c986-592c-43f5-8f87-aabbd4e4f3a4/resource/"
            "7683b9de-6eb1-4803-9c36-1f94d7501c8b/download/gtfs_feed.zip"
        )

    @property
    def gtfs_cache_ttl(self) -> int:
        # STCP updates GTFS frequently — refresh every 12h
        return 43200

    async def async_init(self) -> None:
        """Initialize and resolve latest GTFS URL from CKAN."""
        await super().async_init()
        await self._resolve_latest_gtfs_url()

    async def _resolve_latest_gtfs_url(self) -> None:
        """Query CKAN API to find the latest GTFS resource URL."""
        try:
            async with self.session.get(
                STCP_CKAN_API,
                params={"id": STCP_DATASET_ID},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()

            resources = data.get("result", {}).get("resources", [])
            if not resources:
                return

            # Get the last resource (most recent)
            latest = resources[-1]
            url = latest.get("url", "")
            if url:
                self._resolved_gtfs_url = url
                _LOGGER.debug("STCP: Resolved latest GTFS URL: %s", url)
        except (aiohttp.ClientError, TimeoutError, KeyError) as err:
            _LOGGER.debug("STCP: Could not resolve latest GTFS URL: %s", err)

    async def async_get_vehicles(self, line_ids: list[str] | None = None) -> list[VehiclePosition]:
        """Get real-time vehicle positions from FIWARE/NGSI broker."""
        try:
            headers = {
                "Accept": "application/json",
            }
            async with self.session.get(
                STCP_REALTIME_URL,
                timeout=aiohttp.ClientTimeout(total=15),
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("STCP RT returned %s", resp.status)
                    return []
                data = await resp.json()

            vehicles: list[VehiclePosition] = []
            for entity in data:
                # NGSI SmartDataModels Vehicle format
                vehicle_id = entity.get("id", "")
                location = entity.get("location", {})
                coords = location.get("coordinates", []) if isinstance(location, dict) else []

                if not coords or len(coords) < 2:
                    # Try alternative format
                    coords = [
                        entity.get("longitude", {}).get("value"),
                        entity.get("latitude", {}).get("value"),
                    ]
                    if not all(coords):
                        continue

                # NGSI uses [longitude, latitude] order (GeoJSON)
                lon = float(coords[0]) if coords[0] else None
                lat = float(coords[1]) if coords[1] else None
                if lat is None or lon is None:
                    continue

                line_id = ""
                # Try different field names for route
                for field in ("lineId", "routeId", "category", "vehiclePlateIdentifier"):
                    val = entity.get(field)
                    if isinstance(val, dict):
                        val = val.get("value", "")
                    if val:
                        line_id = str(val)
                        break

                if line_ids and line_id not in line_ids:
                    continue

                heading = entity.get("heading", {})
                if isinstance(heading, dict):
                    heading = heading.get("value")

                speed = entity.get("speed", {})
                if isinstance(speed, dict):
                    speed = speed.get("value")

                vehicles.append(
                    VehiclePosition(
                        vehicle_id=vehicle_id,
                        line_id=line_id,
                        trip_id=None,
                        latitude=lat,
                        longitude=lon,
                        heading=float(heading) if heading else None,
                        speed=float(speed) if speed else None,
                        stop_id=None,
                    )
                )

            return vehicles
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("STCP: Real-time vehicles error: %s", err)
            return []
