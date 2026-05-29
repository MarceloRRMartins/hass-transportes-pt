"""Trip planning service for Transportes PT."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN
from .coordinator import TransportesCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_PLAN_TRIP = "plan_trip"
EVENT_TRIP_PLANNED = f"{DOMAIN}_trip_planned"

ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"
ATTR_DEPARTURE_TIME = "departure_time"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ORIGIN): cv.string,
        vol.Required(ATTR_DESTINATION): cv.string,
        vol.Optional(ATTR_DEPARTURE_TIME): cv.string,
    }
)


@dataclass
class TripLeg:
    """A single leg of a planned trip."""

    line_id: str
    line_name: str
    origin_stop_id: str
    origin_stop_name: str
    destination_stop_id: str
    destination_stop_name: str
    departure_time: str | None = None
    arrival_time: str | None = None
    num_stops: int = 0


@dataclass
class TripPlan:
    """A planned trip from origin to destination."""

    origin: str
    destination: str
    legs: list[TripLeg] = field(default_factory=list)
    total_duration_minutes: int | None = None
    transfers: int = 0


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up trip planning services."""

    async def handle_plan_trip(call: ServiceCall) -> None:
        """Handle the plan_trip service call."""
        origin_stop = call.data[ATTR_ORIGIN]
        destination_stop = call.data[ATTR_DESTINATION]

        # Find a coordinator from registered entries
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No Transportes PT integration configured")
            return

        trip = await _plan_trip(coordinator, origin_stop, destination_stop)

        if trip:
            hass.bus.async_fire(
                EVENT_TRIP_PLANNED,
                {
                    "origin": trip.origin,
                    "destination": trip.destination,
                    "legs": [
                        {
                            "line": leg.line_id,
                            "from": leg.origin_stop_name,
                            "to": leg.destination_stop_name,
                            "departure": leg.departure_time,
                            "arrival": leg.arrival_time,
                        }
                        for leg in trip.legs
                    ],
                    "total_minutes": trip.total_duration_minutes,
                    "transfers": trip.transfers,
                },
            )
        else:
            hass.bus.async_fire(
                EVENT_TRIP_PLANNED,
                {
                    "origin": origin_stop,
                    "destination": destination_stop,
                    "error": "no_route_found",
                },
            )

    hass.services.async_register(
        DOMAIN, SERVICE_PLAN_TRIP, handle_plan_trip, schema=SERVICE_SCHEMA
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload trip planning services."""
    hass.services.async_remove(DOMAIN, SERVICE_PLAN_TRIP)


def _get_coordinator(hass: HomeAssistant) -> TransportesCoordinator | None:
    """Get the first available coordinator."""
    domain_data = hass.data.get(DOMAIN, {})
    for coordinator in domain_data.values():
        if isinstance(coordinator, TransportesCoordinator):
            return coordinator
    return None


async def _plan_trip(
    coordinator: TransportesCoordinator,
    origin_stop_id: str,
    destination_stop_id: str,
) -> TripPlan | None:
    """Plan a trip between two stops.

    Strategy: Check if any line from origin also serves destination (direct route).
    If not, find common lines via intermediate stops (1 transfer).
    """
    provider = coordinator.provider

    # Get stops info to find which lines serve origin and destination
    all_stops = await provider.async_get_stops()
    origin_info = None
    dest_info = None

    for stop in all_stops:
        if stop.stop_id == origin_stop_id:
            origin_info = stop
        elif stop.stop_id == destination_stop_id:
            dest_info = stop
        if origin_info and dest_info:
            break

    if not origin_info or not dest_info:
        _LOGGER.warning("Could not find stop info for origin or destination")
        return None

    origin_lines = set(origin_info.lines)
    dest_lines = set(dest_info.lines)

    # Check direct routes (same line serves both stops)
    direct_lines = origin_lines & dest_lines
    if direct_lines:
        line_id = next(iter(direct_lines))
        # Get next departure from origin
        arrivals = await provider.async_get_arrivals(origin_stop_id)
        departure = None
        for arr in arrivals:
            if arr.line_id == line_id:
                departure = arr
                break

        leg = TripLeg(
            line_id=line_id,
            line_name=line_id,
            origin_stop_id=origin_stop_id,
            origin_stop_name=origin_info.name,
            destination_stop_id=destination_stop_id,
            destination_stop_name=dest_info.name,
            departure_time=departure.estimated_arrival if departure else None,
        )

        return TripPlan(
            origin=origin_info.name,
            destination=dest_info.name,
            legs=[leg],
            transfers=0,
        )

    # Find 1-transfer route: a stop served by both an origin-line and a dest-line
    for stop in all_stops:
        stop_lines = set(stop.lines)
        shared_with_origin = origin_lines & stop_lines
        shared_with_dest = dest_lines & stop_lines
        if shared_with_origin and shared_with_dest:
            leg1_line = next(iter(shared_with_origin))
            leg2_line = next(iter(shared_with_dest))

            leg1 = TripLeg(
                line_id=leg1_line,
                line_name=leg1_line,
                origin_stop_id=origin_stop_id,
                origin_stop_name=origin_info.name,
                destination_stop_id=stop.stop_id,
                destination_stop_name=stop.name,
            )
            leg2 = TripLeg(
                line_id=leg2_line,
                line_name=leg2_line,
                origin_stop_id=stop.stop_id,
                origin_stop_name=stop.name,
                destination_stop_id=destination_stop_id,
                destination_stop_name=dest_info.name,
            )

            return TripPlan(
                origin=origin_info.name,
                destination=dest_info.name,
                legs=[leg1, leg2],
                transfers=1,
            )

    return None
