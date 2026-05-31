"""Tests for the Metro do Porto provider line status parsing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.transportes_pt.providers.metro_porto import (
    LineStatus,
    MetroPortoProvider,
    _parse_line_status,
)

# Simplified HTML similar to what the homepage renders (Estado das Linhas widget)
MOCK_HTML_ALL_OK = """
<html><body>
<h4>Estado das Linhas</h4>
<h4>Estádio do Dragão - Sr. de Matosinhos</h4>
Ok
<h4>Estádio do Dragão - Póvoa de Varzim</h4>
Ok
<h4>Campanhã - ISMAI</h4>
OK
<h4>Hospital S. João - Vila d'Este</h4>
Ok
<h4>Trindade - Aeroporto</h4>
Ok
<h4>Fânzeres - Senhora da Hora</h4>
Ok
</body></html>
"""

MOCK_HTML_ONE_CONDITIONED = """
<html><body>
<h4>Estado das Linhas</h4>
<h4>Estádio do Dragão - Sr. de Matosinhos</h4>
Ok
<h4>Estádio do Dragão - Póvoa de Varzim</h4>
Ok
<h4>Campanhã - ISMAI</h4>
OK
<h4>Hospital S. João - Vila d'Este</h4>
<a href="/pages/630?news_id=621">Condicionada</a>
<h4>Trindade - Aeroporto</h4>
Ok
<h4>Fânzeres - Senhora da Hora</h4>
Ok
</body></html>
"""

MOCK_HTML_MULTIPLE_DISRUPTIONS = """
<html><body>
<h4>Estado das Linhas</h4>
<h4>Estádio do Dragão - Sr. de Matosinhos</h4>
Ok
<h4>Estádio do Dragão - Póvoa de Varzim</h4>
<a href="/pages/630?news_id=700">Interrompida</a>
<h4>Campanhã - ISMAI</h4>
OK
<h4>Hospital S. João - Vila d'Este</h4>
<a href="/pages/630?news_id=621">Condicionada</a>
<h4>Trindade - Aeroporto</h4>
Ok
<h4>Fânzeres - Senhora da Hora</h4>
<a href="/pages/630?news_id=710">Condicionada</a>
</body></html>
"""


# --- _parse_line_status unit tests ---


def test_parse_all_ok():
    """When all lines are Ok, no alerts should be returned."""
    alerts = _parse_line_status(MOCK_HTML_ALL_OK)
    assert alerts == []


def test_parse_one_conditioned():
    """One conditioned line should return exactly one alert."""
    alerts = _parse_line_status(MOCK_HTML_ONE_CONDITIONED)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.alert_id == "metro_porto_d_status"
    assert "Linha D" in alert.title
    assert "Condicionada" in alert.title
    assert alert.affected_lines == ["D"]
    assert alert.url == "https://www.metrodoporto.pt/pages/630?news_id=621"


def test_parse_multiple_disruptions():
    """Multiple disruptions should be sorted by severity."""
    alerts = _parse_line_status(MOCK_HTML_MULTIPLE_DISRUPTIONS)

    assert len(alerts) == 3

    # First: Interrompida (most critical)
    assert alerts[0].affected_lines == ["B"]
    assert "Interrompida" in alerts[0].title

    # Then: Condicionada (less critical, two of them)
    assert alerts[1].affected_lines == ["D"]
    assert "Condicionada" in alerts[1].title

    assert alerts[2].affected_lines == ["F"]
    assert "Condicionada" in alerts[2].title


def test_parse_empty_html():
    """Empty HTML should return no alerts."""
    alerts = _parse_line_status("")
    assert alerts == []


def test_parse_no_estado_section():
    """HTML without any line status info should return no alerts."""
    html = "<html><body><h1>Some other page</h1><p>Content</p></body></html>"
    alerts = _parse_line_status(html)
    assert alerts == []


def test_parse_url_construction():
    """Relative URLs should be prefixed with domain."""
    alerts = _parse_line_status(MOCK_HTML_ONE_CONDITIONED)
    assert alerts[0].url.startswith("https://www.metrodoporto.pt/")


def test_parse_url_absent_for_ok():
    """Ok lines produce no alerts, so no URL to check."""
    alerts = _parse_line_status(MOCK_HTML_ALL_OK)
    assert alerts == []


# --- LineStatus enum tests ---


def test_line_status_from_text_ok():
    """Ok status is parsed correctly."""
    assert LineStatus.from_text("Ok") == LineStatus.OK
    assert LineStatus.from_text("OK") == LineStatus.OK
    assert LineStatus.from_text("ok") == LineStatus.OK


def test_line_status_from_text_conditioned():
    """Conditioned status is parsed correctly."""
    assert LineStatus.from_text("Condicionada") == LineStatus.CONDITIONED
    assert LineStatus.from_text("condicionada") == LineStatus.CONDITIONED


def test_line_status_from_text_interrupted():
    """Interrupted status is parsed correctly."""
    assert LineStatus.from_text("Interrompida") == LineStatus.INTERRUPTED
    assert LineStatus.from_text("interrompida") == LineStatus.INTERRUPTED


def test_line_status_unknown_defaults_to_ok():
    """Unknown status text defaults to OK."""
    assert LineStatus.from_text("something else") == LineStatus.OK
    assert LineStatus.from_text("") == LineStatus.OK


# --- Provider integration tests (mocked HTTP) ---


def _mock_text_response(text: str, status: int = 200):
    """Create a mock response with .text() method."""
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = MagicMock()
    return session


@pytest.mark.asyncio
async def test_async_get_alerts_all_ok(mock_session):
    """Test that no alerts are returned when all lines are Ok."""
    mock_session.get = MagicMock(return_value=_mock_text_response(MOCK_HTML_ALL_OK))
    provider = MetroPortoProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


@pytest.mark.asyncio
async def test_async_get_alerts_disruption(mock_session):
    """Test that alerts are returned for disrupted lines."""
    mock_session.get = MagicMock(
        return_value=_mock_text_response(MOCK_HTML_ONE_CONDITIONED)
    )
    provider = MetroPortoProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert len(alerts) == 1
    assert alerts[0].affected_lines == ["D"]
    assert "Condicionada" in alerts[0].title


@pytest.mark.asyncio
async def test_async_get_alerts_api_error(mock_session):
    """Test that API errors return empty alerts."""
    mock_session.get = MagicMock(return_value=_mock_text_response("", status=500))
    provider = MetroPortoProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


@pytest.mark.asyncio
async def test_async_get_alerts_network_error(mock_session):
    """Test that network errors return empty alerts."""
    mock_session.get = MagicMock(side_effect=Exception("Connection failed"))
    provider = MetroPortoProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


@pytest.mark.asyncio
async def test_async_get_alerts_multiple_disruptions(mock_session):
    """Test sorting of multiple disruptions by severity."""
    mock_session.get = MagicMock(
        return_value=_mock_text_response(MOCK_HTML_MULTIPLE_DISRUPTIONS)
    )
    provider = MetroPortoProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert len(alerts) == 3
    # Interrompida comes first
    assert alerts[0].affected_lines == ["B"]
    # Then Condicionada
    assert alerts[1].affected_lines == ["D"]
    assert alerts[2].affected_lines == ["F"]
