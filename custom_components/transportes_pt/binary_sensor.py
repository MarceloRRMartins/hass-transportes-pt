"""Binary sensor platform for Transportes PT (service alerts)."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LINES, CONF_STOPS, DOMAIN
from .coordinator import TransportesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up alert binary sensors from a config entry."""
    coordinator: TransportesCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [TransportesAlertSensor(coordinator, entry)]
    )


class TransportesAlertSensor(CoordinatorEntity[TransportesCoordinator], BinarySensorEntity):
    """Binary sensor that is ON when there are active alerts for configured stops/lines."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TransportesCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the alert binary sensor."""
        super().__init__(coordinator)
        self._stop_ids = set(entry.data.get(CONF_STOPS, []))
        self._line_ids = set(entry.data.get(CONF_LINES, []))
        self._attr_unique_id = f"{entry.entry_id}_alerts"
        self._attr_translation_key = "service_alerts"
        self._attr_attribution = f"Data provided by {coordinator.provider.name}"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Alertas de Serviço"

    @property
    def is_on(self) -> bool | None:
        """Return True if there are relevant active alerts."""
        alerts = self._get_relevant_alerts()
        return len(alerts) > 0 if alerts is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return alert details."""
        alerts = self._get_relevant_alerts()
        if not alerts:
            return {"alert_count": 0, "alerts": []}

        alert_list = []
        for alert in alerts:
            alert_list.append(
                {
                    "title": alert.title,
                    "description": alert.description,
                    "affected_lines": alert.affected_lines,
                    "affected_stops": alert.affected_stops,
                    "start": alert.start_time,
                    "end": alert.end_time,
                    "url": alert.url,
                }
            )

        return {
            "alert_count": len(alerts),
            "alerts": alert_list,
        }

    def _get_relevant_alerts(self):
        """Get alerts relevant to configured stops/lines."""
        if not self.coordinator.data:
            return None

        all_alerts = self.coordinator.data.alerts
        if not self._stop_ids and not self._line_ids:
            return all_alerts

        relevant = []
        for alert in all_alerts:
            affected_stops = set(alert.affected_stops)
            affected_lines = set(alert.affected_lines)
            if (
                affected_stops & self._stop_ids
                or affected_lines & self._line_ids
                or (not affected_stops and not affected_lines)
            ):
                relevant.append(alert)
        return relevant
