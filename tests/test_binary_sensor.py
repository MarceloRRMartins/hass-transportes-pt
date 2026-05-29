"""Tests for Transportes PT binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.transportes_pt.binary_sensor import TransportesAlertSensor
from custom_components.transportes_pt.const import CONF_LINES, CONF_STOPS
from custom_components.transportes_pt.coordinator import TransportesCoordinator, TransportesData

from .conftest import MOCK_ALERTS, MOCK_STOP_ID


class TestAlertSensor:
    """Tests for TransportesAlertSensor."""

    def _create_sensor(self, alerts=None, stop_ids=None, line_ids=None):
        """Create a binary sensor with mock coordinator."""
        coordinator = MagicMock(spec=TransportesCoordinator)
        coordinator.provider = MagicMock()
        coordinator.provider.name = "Test Provider"
        coordinator.data = TransportesData(
            arrivals={},
            alerts=alerts if alerts is not None else MOCK_ALERTS,
            vehicles=[],
        )
        entry = MagicMock()
        entry.data = {
            CONF_STOPS: stop_ids or [MOCK_STOP_ID],
            CONF_LINES: line_ids or [],
        }
        entry.entry_id = "test_entry"
        sensor = TransportesAlertSensor(coordinator, entry)
        return sensor

    def test_is_on_with_relevant_alert(self):
        """Test sensor is ON when alert affects configured stop."""
        sensor = self._create_sensor()
        assert sensor.is_on is True

    def test_is_off_no_alerts(self):
        """Test sensor is OFF when no alerts."""
        sensor = self._create_sensor(alerts=[])
        assert sensor.is_on is False

    def test_is_off_irrelevant_alert(self):
        """Test sensor is OFF when alert doesn't affect configured stops/lines."""
        sensor = self._create_sensor(stop_ids=["999999"], line_ids=["9999"])
        assert sensor.is_on is False

    def test_is_on_line_match(self):
        """Test sensor is ON when alert matches configured line."""
        sensor = self._create_sensor(stop_ids=["999999"], line_ids=["2727"])
        assert sensor.is_on is True

    def test_extra_state_attributes(self):
        """Test alert details in attributes."""
        sensor = self._create_sensor()
        attrs = sensor.extra_state_attributes
        assert attrs["alert_count"] == 1
        assert attrs["alerts"][0]["title"] == "Desvio de percurso na linha 2727"

    def test_no_data(self):
        """Test when coordinator has no data."""
        coordinator = MagicMock(spec=TransportesCoordinator)
        coordinator.provider = MagicMock()
        coordinator.provider.name = "Test Provider"
        coordinator.data = None
        entry = MagicMock()
        entry.data = {CONF_STOPS: [MOCK_STOP_ID], CONF_LINES: []}
        entry.entry_id = "test_entry"
        sensor = TransportesAlertSensor(coordinator, entry)
        assert sensor.is_on is None
