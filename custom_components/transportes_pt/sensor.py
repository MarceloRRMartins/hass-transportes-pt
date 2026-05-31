"""Sensor platform for Transportes PT (arrivals)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STOPS, DOMAIN
from .coordinator import TransportesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up arrival sensors from a config entry."""
    coordinator: TransportesCoordinator = hass.data[DOMAIN][entry.entry_id]
    stop_ids = entry.data[CONF_STOPS]

    entities = [
        TransportesArrivalSensor(coordinator, stop_id, entry.entry_id) for stop_id in stop_ids
    ]
    async_add_entities(entities)


class TransportesArrivalSensor(CoordinatorEntity[TransportesCoordinator], SensorEntity):
    """Sensor showing minutes until next arrival at a stop."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:bus-clock"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TransportesCoordinator,
        stop_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the arrival sensor."""
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._attr_unique_id = f"{entry_id}_{stop_id}_arrival"
        self._attr_translation_key = "next_arrival"
        self._attr_attribution = f"Data provided by {coordinator.provider.name}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Paragem {self._stop_id}"

    @property
    def native_value(self) -> int | None:
        """Return minutes until next arrival."""
        arrivals = self._get_arrivals()
        if not arrivals:
            return None

        first = arrivals[0]
        # Prefer unix timestamps (more reliable than time-only strings)
        eta_unix = first.estimated_arrival_unix or first.scheduled_arrival_unix
        if eta_unix:
            import time

            diff = (eta_unix - time.time()) / 60
            return max(0, round(diff))

        # Fallback to ISO datetime string
        eta = first.estimated_arrival or first.scheduled_arrival
        if not eta:
            return None

        try:
            arrival_time = datetime.fromisoformat(eta.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            diff = (arrival_time - now).total_seconds() / 60
            return max(0, round(diff))
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes about arrivals."""
        arrivals = self._get_arrivals()
        if not arrivals:
            return {"stop_id": self._stop_id, "arrivals": []}

        first = arrivals[0]
        upcoming = []
        for a in arrivals[:5]:
            upcoming.append(
                {
                    "line": a.line_id,
                    "destination": a.destination,
                    "estimated": a.estimated_arrival,
                    "scheduled": a.scheduled_arrival,
                    "vehicle_id": a.vehicle_id,
                }
            )

        return {
            "stop_id": self._stop_id,
            "next_line": first.line_id,
            "next_destination": first.destination,
            "next_estimated": first.estimated_arrival,
            "next_scheduled": first.scheduled_arrival,
            "arrivals": upcoming,
        }

    def _get_arrivals(self):
        """Get arrivals from coordinator data."""
        if not self.coordinator.data:
            return []
        return self.coordinator.data.arrivals.get(self._stop_id, [])
