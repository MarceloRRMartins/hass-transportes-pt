"""Tests for Transportes PT sensor platform."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from custom_components.transportes_pt.coordinator import TransportesCoordinator, TransportesData
from custom_components.transportes_pt.sensor import TransportesArrivalSensor

from .conftest import MOCK_ARRIVALS, MOCK_STOP_ID


class TestArrivalSensor:
    """Tests for TransportesArrivalSensor."""

    def _create_sensor(self, arrivals=None):
        """Create a sensor with mock coordinator."""
        coordinator = MagicMock(spec=TransportesCoordinator)
        coordinator.provider = MagicMock()
        coordinator.provider.name = "Test Provider"
        coordinator.data = TransportesData(
            arrivals={MOCK_STOP_ID: arrivals if arrivals is not None else MOCK_ARRIVALS},
            alerts=[],
            vehicles=[],
        )
        sensor = TransportesArrivalSensor(coordinator, MOCK_STOP_ID, "test_entry")
        return sensor

    def test_name(self):
        """Test sensor name."""
        sensor = self._create_sensor()
        assert "060002" in sensor.name

    def test_unique_id(self):
        """Test unique ID."""
        sensor = self._create_sensor()
        assert sensor.unique_id == "test_entry_060002_arrival"

    def test_native_value_with_arrivals(self):
        """Test native value calculates minutes correctly."""
        # Set arrival to 5 minutes from now
        future_unix = int(time.time()) + 300
        arrivals = list(MOCK_ARRIVALS)
        arrivals[0] = arrivals[0].__class__(
            line_id=arrivals[0].line_id,
            line_name=arrivals[0].line_name,
            destination=arrivals[0].destination,
            estimated_arrival=arrivals[0].estimated_arrival,
            scheduled_arrival=arrivals[0].scheduled_arrival,
            estimated_arrival_unix=future_unix,
            scheduled_arrival_unix=future_unix - 60,
            vehicle_id=arrivals[0].vehicle_id,
            trip_id=arrivals[0].trip_id,
        )
        sensor = self._create_sensor(arrivals)
        value = sensor.native_value
        assert value is not None
        assert 4 <= value <= 6  # ~5 minutes

    def test_native_value_no_arrivals(self):
        """Test native value returns None when no arrivals."""
        sensor = self._create_sensor(arrivals=[])
        assert sensor.native_value is None

    def test_native_value_no_data(self):
        """Test native value returns None when coordinator has no data."""
        coordinator = MagicMock(spec=TransportesCoordinator)
        coordinator.provider = MagicMock()
        coordinator.provider.name = "Test Provider"
        coordinator.data = None
        sensor = TransportesArrivalSensor(coordinator, MOCK_STOP_ID, "test_entry")
        assert sensor.native_value is None

    def test_extra_state_attributes(self):
        """Test extra state attributes."""
        sensor = self._create_sensor()
        attrs = sensor.extra_state_attributes
        assert attrs["stop_id"] == MOCK_STOP_ID
        assert attrs["next_line"] == "2727"
        assert attrs["next_destination"] == "Loures (Centro Comercial)"
        assert len(attrs["arrivals"]) == 2

    def test_extra_state_attributes_empty(self):
        """Test attributes when no arrivals."""
        sensor = self._create_sensor(arrivals=[])
        attrs = sensor.extra_state_attributes
        assert attrs["stop_id"] == MOCK_STOP_ID
        assert attrs["arrivals"] == []
