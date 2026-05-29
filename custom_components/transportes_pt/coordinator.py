"""Data coordinator for Transportes PT."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL_ALERTS,
    DEFAULT_SCAN_INTERVAL_ARRIVALS,
    DEFAULT_SCAN_INTERVAL_VEHICLES,
    DOMAIN,
)
from .providers import Alert, Arrival, TransitProvider, VehiclePosition

_LOGGER = logging.getLogger(__name__)


@dataclass
class TransportesData:
    """Container for coordinator data."""

    arrivals: dict[str, list[Arrival]] = field(default_factory=dict)
    alerts: list[Alert] = field(default_factory=list)
    vehicles: list[VehiclePosition] = field(default_factory=list)


class TransportesCoordinator(DataUpdateCoordinator[TransportesData]):
    """Coordinator that fetches transit data from a provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        provider: TransitProvider,
        stop_ids: list[str],
        line_ids: list[str] | None = None,
        enable_vehicles: bool = True,
        scan_interval_arrivals: timedelta = DEFAULT_SCAN_INTERVAL_ARRIVALS,
        scan_interval_alerts: timedelta = DEFAULT_SCAN_INTERVAL_ALERTS,
        scan_interval_vehicles: timedelta = DEFAULT_SCAN_INTERVAL_VEHICLES,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{provider.provider_id}",
            update_interval=scan_interval_arrivals,
        )
        self.provider = provider
        self.stop_ids = stop_ids
        self.line_ids = line_ids
        self.enable_vehicles = enable_vehicles
        self._scan_interval_alerts = scan_interval_alerts
        self._scan_interval_vehicles = scan_interval_vehicles
        self._alerts_last_update: float = 0
        self._vehicles_last_update: float = 0

    async def _async_update_data(self) -> TransportesData:
        """Fetch data from the provider."""
        import time

        now = time.time()
        data = TransportesData()

        # Always fetch arrivals (primary polling interval)
        try:
            for stop_id in self.stop_ids:
                arrivals = await self.provider.async_get_arrivals(stop_id)
                data.arrivals[stop_id] = arrivals
        except Exception as err:
            raise UpdateFailed(f"Error fetching arrivals: {err}") from err

        # Fetch alerts at a slower interval
        if now - self._alerts_last_update >= self._scan_interval_alerts.total_seconds():
            try:
                data.alerts = await self.provider.async_get_alerts()
                self._alerts_last_update = now
            except Exception as err:
                _LOGGER.warning("Error fetching alerts: %s", err)
                data.alerts = self.data.alerts if self.data else []
        else:
            data.alerts = self.data.alerts if self.data else []

        # Fetch vehicles at a faster interval (if enabled)
        if self.enable_vehicles:
            if now - self._vehicles_last_update >= self._scan_interval_vehicles.total_seconds():
                try:
                    data.vehicles = await self.provider.async_get_vehicles(self.line_ids)
                    self._vehicles_last_update = now
                except Exception as err:
                    _LOGGER.warning("Error fetching vehicles: %s", err)
                    data.vehicles = self.data.vehicles if self.data else []
            else:
                data.vehicles = self.data.vehicles if self.data else []

        return data
