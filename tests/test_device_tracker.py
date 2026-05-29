"""Tests for the device tracker platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.transportes_pt.coordinator import TransportesCoordinator, TransportesData
from custom_components.transportes_pt.device_tracker import TransportesVehicleTracker
from custom_components.transportes_pt.providers import VehiclePosition

from .conftest import MOCK_VEHICLES


class TestVehicleTracker:
    """Tests for TransportesVehicleTracker."""

    def _create_tracker(self, vehicles=None, vehicle_id="42|2328"):
        """Create a vehicle tracker with mock coordinator."""
        coordinator = MagicMock(spec=TransportesCoordinator)
        coordinator.provider = MagicMock()
        coordinator.provider.name = "Test Provider"
        coordinator.data = TransportesData(
            arrivals={},
            alerts=[],
            vehicles=vehicles if vehicles is not None else MOCK_VEHICLES,
        )
        tracker = TransportesVehicleTracker(coordinator, vehicle_id, "test_entry")
        return tracker

    def test_name(self):
        tracker = self._create_tracker()
        assert "42|2328" in tracker.name

    def test_unique_id(self):
        tracker = self._create_tracker()
        assert tracker.unique_id == "test_entry_vehicle_42|2328"

    def test_source_type(self):
        from homeassistant.components.device_tracker import SourceType

        tracker = self._create_tracker()
        assert tracker.source_type == SourceType.GPS

    def test_latitude(self):
        tracker = self._create_tracker()
        assert tracker.latitude == 38.7677

    def test_longitude(self):
        tracker = self._create_tracker()
        assert tracker.longitude == -9.0990

    def test_latitude_no_vehicle(self):
        tracker = self._create_tracker(vehicle_id="nonexistent")
        assert tracker.latitude is None

    def test_longitude_no_vehicle(self):
        tracker = self._create_tracker(vehicle_id="nonexistent")
        assert tracker.longitude is None

    def test_extra_state_attributes(self):
        tracker = self._create_tracker()
        attrs = tracker.extra_state_attributes
        assert attrs["vehicle_id"] == "42|2328"
        assert attrs["line_id"] == "2727"
        assert attrs["heading"] == 180.0
        assert attrs["speed"] == 25.0
        assert attrs["stop_id"] == "060003"

    def test_extra_state_attributes_no_vehicle(self):
        tracker = self._create_tracker(vehicle_id="nonexistent")
        attrs = tracker.extra_state_attributes
        assert attrs == {"vehicle_id": "nonexistent"}

    def test_no_data(self):
        coordinator = MagicMock(spec=TransportesCoordinator)
        coordinator.provider = MagicMock()
        coordinator.provider.name = "Test"
        coordinator.data = None
        tracker = TransportesVehicleTracker(coordinator, "42|2328", "test_entry")
        assert tracker.latitude is None
        assert tracker.longitude is None

    def test_attribution_dynamic(self):
        tracker = self._create_tracker()
        assert "Test Provider" in tracker._attr_attribution

    def test_multiple_vehicles_finds_correct_one(self):
        """Test finding the correct vehicle from a list."""
        vehicles = [
            VehiclePosition(
                vehicle_id="other_vehicle",
                line_id="1523",
                trip_id="trip_2",
                latitude=38.8,
                longitude=-9.2,
            ),
            MOCK_VEHICLES[0],
        ]
        tracker = self._create_tracker(vehicles=vehicles)
        assert tracker.latitude == 38.7677

    def test_icon(self):
        tracker = self._create_tracker()
        assert tracker._attr_icon == "mdi:bus-marker"
