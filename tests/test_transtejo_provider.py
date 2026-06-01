"""Tests for the Transtejo Soflusa provider."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.transportes_pt.providers.transtejo import (
    LINES,
    TERMINALS,
    TranstejoProvider,
    _derive_line_id,
    _normalize_terminal,
    _parse_departures,
    _time_to_unix,
)

# Sample HTML mimicking TTSL WordPress page content
MOCK_DEPARTURES_HTML = """
<div class="entry-content">
<table class="partidas">
<tr>
<td>10:30</td>
<td>Cais do Sodré</td>
<td>Cacilhas</td>
<td>Previsto</td>
<td>A</td>
</tr>
<tr>
<td>10:45</td>
<td>Cais do Sodré</td>
<td>Seixal</td>
<td>Embarque</td>
<td>B</td>
</tr>
<tr>
<td>10:20</td>
<td>Cacilhas</td>
<td>Cais do Sodré</td>
<td>Partiu</td>
<td>C</td>
</tr>
<tr>
<td>11:00</td>
<td>Barreiro</td>
<td>Terreiro do Paço</td>
<td>Previsto</td>
<td></td>
</tr>
</table>
</div>
"""

MOCK_PAGE_JSON = {
    "content": {
        "rendered": MOCK_DEPARTURES_HTML,
    }
}

MOCK_ALERTS_JSON = [
    {
        "id": 123,
        "title": {"rendered": "Altera\u00e7\u00e3o de hor\u00e1rio"},
        "content": {"rendered": "<p>A liga\u00e7\u00e3o Cacilhas-Sodré terá horário reduzido.</p>"},
        "date": "2024-01-15T10:00:00",
        "link": "https://ttsl.pt/avisos/alteracao-horario",
    },
    {
        "id": 124,
        "title": {"rendered": "Supressão de serviço"},
        "content": {"rendered": "<p>Serviço Seixal suspenso por mau tempo.</p>"},
        "date": "2024-01-16T08:30:00",
        "link": "https://ttsl.pt/avisos/supressao",
    },
]


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    return MagicMock()


def _mock_response(data, status=200):
    """Create a mock response context manager."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# --- Unit tests for helper functions ---


class TestParserHelpers:
    """Tests for HTML parser and helper functions."""

    def test_parse_departures(self):
        """Test parsing HTML departures table."""
        departures = _parse_departures(MOCK_DEPARTURES_HTML)
        assert len(departures) == 4
        assert departures[0]["time"] == "10:30"
        assert departures[0]["terminal"] == "Cais do Sodré"
        assert departures[0]["destination"] == "Cacilhas"
        assert departures[0]["status"] == "Previsto"
        assert departures[0]["gate"] == "A"

    def test_parse_embarque_status(self):
        """Test that embarque status is parsed."""
        departures = _parse_departures(MOCK_DEPARTURES_HTML)
        assert departures[1]["status"] == "Embarque"

    def test_parse_partiu_status(self):
        """Test that partiu status is parsed."""
        departures = _parse_departures(MOCK_DEPARTURES_HTML)
        assert departures[2]["status"] == "Partiu"

    def test_parse_empty_html(self):
        """Test parsing HTML with no table."""
        departures = _parse_departures("<div>No table here</div>")
        assert departures == []

    def test_normalize_terminal(self):
        """Test terminal name normalization."""
        assert _normalize_terminal("Cais do Sodré") == "cais_do_sodre"
        assert _normalize_terminal("CACILHAS") == "cacilhas"
        assert _normalize_terminal("Terreiro do Paço") == "terreiro_do_paco"
        assert _normalize_terminal("  Barreiro  ") == "barreiro"
        assert _normalize_terminal("Unknown") == ""

    def test_derive_line_id(self):
        """Test line ID derivation."""
        assert _derive_line_id("Cais do Sodré", "Cacilhas") == "cacilhas_cais_do_sodre"
        assert _derive_line_id("Barreiro", "Terreiro do Paço") == "barreiro_terreiro_do_paco"

    def test_time_to_unix_valid(self):
        """Test time conversion to unix timestamp."""
        now = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        result = _time_to_unix("10:30", now=now)
        assert result is not None
        expected = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result == int(expected.timestamp())

    def test_time_to_unix_next_day(self):
        """Test time wrap-around to next day."""
        # Current time is 23:00, departure at 02:00 — should NOT wrap
        now = datetime(2024, 1, 15, 23, 0, 0, tzinfo=timezone.utc)
        result = _time_to_unix("02:00", now=now)
        # 02:00 is 21 hours behind 23:00, > 6h, so should wrap to next day
        expected = datetime(2024, 1, 16, 2, 0, 0, tzinfo=timezone.utc)
        assert result == int(expected.timestamp())

    def test_time_to_unix_invalid(self):
        """Test invalid time string."""
        assert _time_to_unix("invalid") is None
        assert _time_to_unix("") is None


# --- Integration tests for provider ---


@pytest.mark.asyncio
async def test_get_arrivals(mock_session):
    """Test fetching arrivals for a terminal."""
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_PAGE_JSON))
    provider = TranstejoProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("cais_do_sodre")

    # Should get 2 arrivals from Cais do Sodré (Previsto + Embarque), skip Partiu
    assert len(arrivals) == 2
    assert arrivals[0].destination == "Cacilhas"
    assert arrivals[0].estimated_arrival == "10:30"
    assert arrivals[1].destination == "Seixal"


@pytest.mark.asyncio
async def test_get_arrivals_filters_by_terminal(mock_session):
    """Test that arrivals are filtered by the requested terminal."""
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_PAGE_JSON))
    provider = TranstejoProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("barreiro")

    assert len(arrivals) == 1
    assert arrivals[0].destination == "Terreiro Do Paço"


@pytest.mark.asyncio
async def test_get_arrivals_skips_partiu(mock_session):
    """Test that departed ferries are excluded."""
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_PAGE_JSON))
    provider = TranstejoProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("cacilhas")

    # The only Cacilhas row has status "Partiu" — should be filtered
    assert len(arrivals) == 0


@pytest.mark.asyncio
async def test_get_arrivals_api_failure(mock_session):
    """Test graceful handling of API failure."""
    mock_session.get = MagicMock(return_value=_mock_response(None, status=500))
    provider = TranstejoProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("cais_do_sodre")

    assert arrivals == []


@pytest.mark.asyncio
async def test_get_alerts(mock_session):
    """Test fetching alerts."""
    mock_session.get = MagicMock(return_value=_mock_response(MOCK_ALERTS_JSON))
    provider = TranstejoProvider(session=mock_session)

    alerts = await provider.async_get_alerts()

    assert len(alerts) == 2
    assert alerts[0].alert_id == "123"
    assert "Alteração de horário" in alerts[0].title
    assert "horário reduzido" in alerts[0].description
    assert alerts[0].url == "https://ttsl.pt/avisos/alteracao-horario"
    assert alerts[1].alert_id == "124"


@pytest.mark.asyncio
async def test_get_vehicles(mock_session):
    """Test that vehicle tracking returns empty."""
    provider = TranstejoProvider(session=mock_session)
    vehicles = await provider.async_get_vehicles()
    assert vehicles == []


@pytest.mark.asyncio
async def test_get_stops(mock_session):
    """Test fetching stops."""
    provider = TranstejoProvider(session=mock_session)
    stops = await provider.async_get_stops()

    assert len(stops) == len(TERMINALS)
    stop_ids = [s.stop_id for s in stops]
    assert "cais_do_sodre" in stop_ids
    assert "cacilhas" in stop_ids
    assert "barreiro" in stop_ids


@pytest.mark.asyncio
async def test_get_stops_with_search(mock_session):
    """Test stops search filtering."""
    provider = TranstejoProvider(session=mock_session)

    stops = await provider.async_get_stops(search="Sodré")
    assert len(stops) == 1
    assert stops[0].stop_id == "cais_do_sodre"

    stops = await provider.async_get_stops(search="nonexistent")
    assert len(stops) == 0


@pytest.mark.asyncio
async def test_get_lines(mock_session):
    """Test fetching lines."""
    provider = TranstejoProvider(session=mock_session)
    lines = await provider.async_get_lines()

    assert len(lines) == len(LINES)
    assert lines[0].line_id == "cacilhas_cais_do_sodre"
    assert lines[0].short_name == "Cacilhas"


@pytest.mark.asyncio
async def test_test_connection_success(mock_session):
    """Test connection check — success."""
    mock_session.get = MagicMock(return_value=_mock_response({"id": 24}))
    provider = TranstejoProvider(session=mock_session)

    result = await provider.async_test_connection()
    assert result is True


@pytest.mark.asyncio
async def test_test_connection_failure(mock_session):
    """Test connection check — failure."""
    mock_session.get = MagicMock(return_value=_mock_response(None, status=404))
    provider = TranstejoProvider(session=mock_session)

    result = await provider.async_test_connection()
    assert result is False
