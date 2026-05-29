"""Transit provider abstraction for Transportes PT."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Arrival:
    """Represents a transit arrival at a stop."""

    line_id: str
    line_name: str
    destination: str
    estimated_arrival: str | None
    scheduled_arrival: str | None
    estimated_arrival_unix: int | None = None
    scheduled_arrival_unix: int | None = None
    vehicle_id: str | None = None
    trip_id: str | None = None


@dataclass
class Alert:
    """Represents a service alert."""

    alert_id: str
    title: str
    description: str
    affected_lines: list[str] = field(default_factory=list)
    affected_stops: list[str] = field(default_factory=list)
    start_time: str | None = None
    end_time: str | None = None
    url: str | None = None


@dataclass
class VehiclePosition:
    """Represents a vehicle's real-time position."""

    vehicle_id: str
    line_id: str
    trip_id: str | None
    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None
    stop_id: str | None = None


@dataclass
class Stop:
    """Represents a transit stop."""

    stop_id: str
    name: str
    latitude: float
    longitude: float
    lines: list[str] = field(default_factory=list)
    municipality: str | None = None


@dataclass
class Line:
    """Represents a transit line."""

    line_id: str
    short_name: str
    long_name: str
    color: str | None = None


class TransitProvider(ABC):
    """Abstract base class for transit data providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the provider."""

    @abstractmethod
    async def async_init(self) -> None:
        """Initialize the provider (create sessions, etc.)."""

    @abstractmethod
    async def async_close(self) -> None:
        """Close the provider (cleanup sessions, etc.)."""

    @abstractmethod
    async def async_test_connection(self) -> bool:
        """Test if the provider's API is reachable."""

    @abstractmethod
    async def async_get_arrivals(self, stop_id: str) -> list[Arrival]:
        """Get estimated arrivals for a stop."""

    @abstractmethod
    async def async_get_alerts(self) -> list[Alert]:
        """Get active service alerts."""

    @abstractmethod
    async def async_get_vehicles(self, line_ids: list[str] | None = None) -> list[VehiclePosition]:
        """Get real-time vehicle positions, optionally filtered by line."""

    @abstractmethod
    async def async_get_stops(self, search: str | None = None) -> list[Stop]:
        """Get stops, optionally filtered by search term."""

    @abstractmethod
    async def async_get_lines(self) -> list[Line]:
        """Get all lines for this provider."""
