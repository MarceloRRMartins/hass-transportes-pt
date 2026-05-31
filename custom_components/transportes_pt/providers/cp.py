"""CP — Comboios de Portugal provider with real-time data from comboios.live."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import aiohttp

from . import Alert, Arrival, VehiclePosition
from .gtfs_base import GtfsProvider

_LOGGER = logging.getLogger(__name__)

# comboios.live public API (no auth required)
_COMBOIOS_LIVE_BASE = "https://comboios.live/api"
_VEHICLES_URL = f"{_COMBOIOS_LIVE_BASE}/vehicles"
_STATIONS_URL = f"{_COMBOIOS_LIVE_BASE}/stations"

# GTFS-RT feeds from cp-gtfsrt.jdcp.workers.dev
_GTFS_RT_VP_URL = "https://cp-gtfsrt.jdcp.workers.dev/vehicle-positions/pb"
_GTFS_RT_TU_URL = "https://cp-gtfsrt.jdcp.workers.dev/trip-updates/pb"

# Service code → display name
_SERVICE_NAMES: dict[str, str] = {
    "1": "Alfa Pendular",
    "2": "Intercidades",
    "3": "InterRegional",
    "4": "Regional",
    "12": "Internacional",
    "40": "Regional Alta Qualidade",
    "45": "Urbanos de Lisboa",
    "55": "Urbanos do Porto",
}


def _gtfs_to_live_stop_id(stop_id: str) -> str:
    """Convert GTFS stop_id (94_30007) to comboios.live format (94-30007)."""
    return stop_id.replace("_", "-")


def _live_to_gtfs_stop_id(station_id: str) -> str:
    """Convert comboios.live station_id (94-30007) to GTFS format (94_30007)."""
    return station_id.replace("-", "_")


class CpProvider(GtfsProvider):
    """Provider for CP — Comboios de Portugal (national rail).

    Features:
        - GTFS Static for scheduled arrivals and stop list
        - GTFS-RT for trip updates and vehicle positions (protobuf)
        - comboios.live API for enriched real-time arrivals, vehicle tracking,
          and cancelled train alerts
    """

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize."""
        super().__init__(session)

    @property
    def provider_id(self) -> str:
        return "cp"

    @property
    def name(self) -> str:
        return "CP - Comboios de Portugal"

    @property
    def gtfs_url(self) -> str:
        return "https://publico.cp.pt/gtfs/gtfs.zip"

    @property
    def gtfs_rt_vehicle_positions_url(self) -> str | None:
        return _GTFS_RT_VP_URL

    @property
    def gtfs_rt_trip_updates_url(self) -> str | None:
        return _GTFS_RT_TU_URL

    async def async_get_arrivals(self, stop_id: str) -> list[Arrival]:
        """Get real-time arrivals for a CP station.

        Tries comboios.live enriched data first, falls back to GTFS-RT/static.
        """
        live_arrivals = await self._get_live_arrivals(stop_id)
        if live_arrivals is not None:
            return live_arrivals

        return await super().async_get_arrivals(stop_id)

    async def _get_live_arrivals(self, stop_id: str) -> list[Arrival] | None:
        """Fetch arrivals from comboios.live station API."""
        station_code = _gtfs_to_live_stop_id(stop_id)
        url = f"{_STATIONS_URL}/{station_code}/arrivals"

        try:
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

            if not data or not isinstance(data, list):
                return None

            arrivals: list[Arrival] = []
            now_ts = int(datetime.now(tz=UTC).timestamp())

            for entry in data:
                train_number = entry.get("trainNumber")
                if not train_number:
                    continue

                service = entry.get("trainService", {})
                service_code = str(service.get("code", ""))
                service_name = _SERVICE_NAMES.get(
                    service_code, service.get("designation", "")
                )

                destination = entry.get("trainDestination", {}).get("designation", "")
                delay_seconds = entry.get("delay", 0) or 0

                # Parse scheduled time
                scheduled_str = entry.get("scheduledTime") or entry.get("arrival")
                scheduled_unix: int | None = None
                estimated_unix: int | None = None

                if scheduled_str:
                    try:
                        dt = datetime.fromisoformat(scheduled_str)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=UTC)
                        scheduled_unix = int(dt.timestamp())
                        estimated_unix = scheduled_unix + delay_seconds
                    except (ValueError, TypeError):
                        pass

                # Skip arrivals that have already passed
                if estimated_unix and estimated_unix < now_ts - 60:
                    continue

                estimated_iso = (
                    datetime.fromtimestamp(estimated_unix, tz=UTC).isoformat()
                    if estimated_unix
                    else None
                )
                scheduled_iso = (
                    datetime.fromtimestamp(scheduled_unix, tz=UTC).isoformat()
                    if scheduled_unix
                    else None
                )

                arrivals.append(
                    Arrival(
                        line_id=service_code,
                        line_name=f"{service_name} {train_number}",
                        destination=destination,
                        estimated_arrival=estimated_iso,
                        scheduled_arrival=scheduled_iso,
                        estimated_arrival_unix=estimated_unix,
                        scheduled_arrival_unix=scheduled_unix,
                        vehicle_id=str(train_number),
                        trip_id=str(train_number),
                    )
                )

            # Sort by ETA
            arrivals.sort(key=lambda a: a.estimated_arrival_unix or a.scheduled_arrival_unix or 0)
            return arrivals[:10] if arrivals else None
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("CP comboios.live arrivals error for %s: %s", stop_id, err)
            return None

    async def async_get_alerts(self) -> list[Alert]:
        """Get alerts for cancelled CP trains from comboios.live."""
        alerts = await self._get_cancelled_alerts()
        if alerts is not None:
            return alerts
        return []

    async def _get_cancelled_alerts(self) -> list[Alert] | None:
        """Fetch cancelled trains from comboios.live vehicles endpoint."""
        try:
            async with self.session.get(
                _VEHICLES_URL,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

            if not data or not isinstance(data, list):
                return None

            alerts: list[Alert] = []
            for vehicle in data:
                status = vehicle.get("status", "")
                if status != "CANCELLED":
                    continue

                train_number = vehicle.get("trainNumber", "")
                service = vehicle.get("service", {})
                service_code = str(service.get("code", ""))
                service_name = _SERVICE_NAMES.get(
                    service_code, service.get("designation", "")
                )
                origin = vehicle.get("origin", {}).get("designation", "")
                destination = vehicle.get("destination", {}).get("designation", "")
                run_date = vehicle.get("runDate", "")

                alerts.append(
                    Alert(
                        alert_id=f"cp_cancelled_{train_number}_{run_date}",
                        title=f"Comboio {train_number} suprimido",
                        description=(
                            f"{service_name} {train_number}: {origin} → {destination}"
                        ),
                        affected_lines=[service_code] if service_code else [],
                    )
                )

            return alerts
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("CP comboios.live alerts error: %s", err)
            return None

    async def async_get_vehicles(
        self, line_ids: list[str] | None = None
    ) -> list[VehiclePosition]:
        """Get real-time vehicle positions from comboios.live.

        Falls back to GTFS-RT protobuf on failure.
        """
        live_vehicles = await self._get_live_vehicles(line_ids)
        if live_vehicles is not None:
            return live_vehicles

        return await super().async_get_vehicles(line_ids)

    async def _get_live_vehicles(
        self, line_ids: list[str] | None = None
    ) -> list[VehiclePosition] | None:
        """Fetch vehicle positions from comboios.live."""
        try:
            async with self.session.get(
                _VEHICLES_URL,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

            if not data or not isinstance(data, list):
                return None

            vehicles: list[VehiclePosition] = []
            for vehicle in data:
                status = vehicle.get("status", "")
                # Skip completed/cancelled trains
                if status in ("COMPLETED", "CANCELLED"):
                    continue

                lat = vehicle.get("lat")
                lng = vehicle.get("lng")
                if lat is None or lng is None:
                    continue

                try:
                    latitude = float(lat)
                    longitude = float(lng)
                except (ValueError, TypeError):
                    continue

                service = vehicle.get("service", {})
                service_code = str(service.get("code", ""))

                # Filter by line_ids if provided
                if line_ids and service_code not in line_ids:
                    continue

                train_number = str(vehicle.get("trainNumber", ""))
                bearing = vehicle.get("bearing")
                speed = vehicle.get("speed")
                last_station = vehicle.get("lastStation", "")
                gtfs_data = vehicle.get("gtfs", {})
                trip_id = gtfs_data.get("tripId") if gtfs_data else None

                vehicles.append(
                    VehiclePosition(
                        vehicle_id=train_number,
                        line_id=service_code,
                        trip_id=trip_id or train_number,
                        latitude=latitude,
                        longitude=longitude,
                        heading=float(bearing) if bearing is not None else None,
                        speed=float(speed) if speed is not None else None,
                        stop_id=_live_to_gtfs_stop_id(last_station) if last_station else None,
                    )
                )

            return vehicles
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("CP comboios.live vehicles error: %s", err)
            return None
