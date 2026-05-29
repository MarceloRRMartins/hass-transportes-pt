"""Device tracker platform for Transportes PT (vehicles)."""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENABLE_VEHICLES, DOMAIN
from .coordinator import TransportesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up vehicle trackers from a config entry."""
    if not entry.data.get(CONF_ENABLE_VEHICLES, True):
        return

    coordinator: TransportesCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Track which vehicles we've already added
    tracked_vehicles: set[str] = set()

    @callback
    def _async_add_new_vehicles() -> None:
        """Add new vehicle trackers as they appear."""
        if not coordinator.data:
            return

        new_entities = []
        for vehicle in coordinator.data.vehicles:
            if vehicle.vehicle_id not in tracked_vehicles:
                tracked_vehicles.add(vehicle.vehicle_id)
                new_entities.append(
                    TransportesVehicleTracker(coordinator, vehicle.vehicle_id, entry.entry_id)
                )

        if new_entities:
            async_add_entities(new_entities)

    # Add vehicles from initial data
    _async_add_new_vehicles()

    # Listen for new vehicles in future updates
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_vehicles))


class TransportesVehicleTracker(CoordinatorEntity[TransportesCoordinator], TrackerEntity):
    """Tracker entity for a transit vehicle."""

    _attr_icon = "mdi:bus-marker"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TransportesCoordinator,
        vehicle_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the vehicle tracker."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"{entry_id}_vehicle_{vehicle_id}"
        self._attr_attribution = f"Data provided by {coordinator.provider.name}"

    @property
    def name(self) -> str:
        """Return the name."""
        return f"Veículo {self._vehicle_id}"

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        vehicle = self._get_vehicle()
        return vehicle.latitude if vehicle else None

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        vehicle = self._get_vehicle()
        return vehicle.longitude if vehicle else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        vehicle = self._get_vehicle()
        if not vehicle:
            return {"vehicle_id": self._vehicle_id}

        return {
            "vehicle_id": self._vehicle_id,
            "line_id": vehicle.line_id,
            "trip_id": vehicle.trip_id,
            "heading": vehicle.heading,
            "speed": vehicle.speed,
            "stop_id": vehicle.stop_id,
        }

    def _get_vehicle(self):
        """Find this vehicle in coordinator data."""
        if not self.coordinator.data:
            return None
        for v in self.coordinator.data.vehicles:
            if v.vehicle_id == self._vehicle_id:
                return v
        return None
