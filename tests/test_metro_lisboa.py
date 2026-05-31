"""Tests for the Metro de Lisboa provider line status parsing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.transportes_pt.providers.metro_lisboa import (
    LineStatus,
    MetroLisboaProvider,
    _parse_line_status,
)


# Simplified HTML similar to what the API returns (mobile version)
MOCK_HTML_ALL_NORMAL = """
<div class="et_pb_column fundo_linha_azul">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Azul</div>
<div class="circ_mobile">normal</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detAzulMobile"><strong>Estado da Linha: </strong>normal.</div>
</div></div>
<div class="et_pb_column fundo_linha_amarela">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Amarela</div>
<div class="circ_mobile">normal</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detAmarelaMobile"><strong>Estado da Linha: </strong>normal.</div>
</div></div>
<div class="et_pb_column fundo_linha_verde">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Verde</div>
<div class="circ_mobile">normal</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detVerdMobile"><strong>Estado da Linha: </strong>normal.</div>
</div></div>
<div class="et_pb_column fundo_linha_vermelha">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Vermelha</div>
<div class="circ_mobile">normal</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detVermMobile"><strong>Estado da Linha: </strong>normal.</div>
</div></div>
"""

MOCK_HTML_DISRUPTION = """
<div class="et_pb_column fundo_linha_azul">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Azul</div>
<div class="circ_mobile">interrompida</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detAzulMobile"><strong>Estado da Linha: </strong>interrompida entre Reboleira e Pontinha.</div>
</div></div>
<div class="et_pb_column fundo_linha_amarela">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Amarela</div>
<div class="circ_mobile">normal</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detAmarelaMobile"><strong>Estado da Linha: </strong>normal.</div>
</div></div>
<div class="et_pb_column fundo_linha_verde">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Verde</div>
<div class="circ_mobile">parcialmente interrompida</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detVerdMobile"><strong>Estado da Linha: </strong>parcialmente interrompida entre Rossio e Cais do Sodre.</div>
</div></div>
<div class="et_pb_column fundo_linha_vermelha">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Vermelha</div>
<div class="circ_mobile">normal</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detVermMobile"><strong>Estado da Linha: </strong>normal.</div>
</div></div>
"""


def test_parse_all_normal():
    """When all lines are normal, no alerts should be returned."""
    alerts = _parse_line_status(MOCK_HTML_ALL_NORMAL)
    assert alerts == []


def test_parse_disruption():
    """When lines have disruptions, alerts should be returned."""
    alerts = _parse_line_status(MOCK_HTML_DISRUPTION)

    assert len(alerts) == 2

    # First alert: Linha Azul
    azul = alerts[0]
    assert azul.alert_id == "metro_lisboa_azul_status"
    assert "Linha Azul" in azul.title
    assert "interrompida" in azul.title
    assert azul.affected_lines == ["AZ"]
    assert "interrompida entre Reboleira e Pontinha" in azul.description

    # Second alert: Linha Verde
    verde = alerts[1]
    assert verde.alert_id == "metro_lisboa_verde_status"
    assert "Linha Verde" in verde.title
    assert "parcialmente interrompida" in verde.title
    assert verde.affected_lines == ["VD"]


def test_parse_empty_html():
    """Empty HTML should return no alerts."""
    alerts = _parse_line_status("")
    assert alerts == []


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
async def test_async_get_alerts_normal(mock_session):
    """Test that no alerts are returned when all lines are normal."""
    mock_session.get = MagicMock(return_value=_mock_text_response(MOCK_HTML_ALL_NORMAL))
    provider = MetroLisboaProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


@pytest.mark.asyncio
async def test_async_get_alerts_disruption(mock_session):
    """Test that alerts are returned for disrupted lines."""
    mock_session.get = MagicMock(return_value=_mock_text_response(MOCK_HTML_DISRUPTION))
    provider = MetroLisboaProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert len(alerts) == 2
    assert alerts[0].affected_lines == ["AZ"]
    assert alerts[1].affected_lines == ["VD"]


@pytest.mark.asyncio
async def test_async_get_alerts_api_error(mock_session):
    """Test that API errors return empty alerts."""
    mock_session.get = MagicMock(return_value=_mock_text_response("", status=500))
    provider = MetroLisboaProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


@pytest.mark.asyncio
async def test_async_get_alerts_network_error(mock_session):
    """Test that network errors return empty alerts."""
    mock_session.get = MagicMock(side_effect=Exception("Connection failed"))
    provider = MetroLisboaProvider(session=mock_session)

    alerts = await provider.async_get_alerts()
    assert alerts == []


# --- LineStatus enum tests ---


def test_line_status_from_text_normal():
    """Normal status is parsed correctly."""
    assert LineStatus.from_text("normal") == LineStatus.NORMAL
    assert LineStatus.from_text("Normal") == LineStatus.NORMAL


def test_line_status_from_text_interrupted():
    """Interrupted status is parsed correctly."""
    assert LineStatus.from_text("interrompida") == LineStatus.INTERRUPTED
    assert LineStatus.from_text("interrompida entre X e Y") == LineStatus.INTERRUPTED


def test_line_status_from_text_partial():
    """Partial interruption is parsed correctly."""
    assert LineStatus.from_text("parcialmente interrompida") == LineStatus.PARTIAL
    assert LineStatus.from_text("Parcialmente Interrompida entre A e B") == LineStatus.PARTIAL


def test_line_status_from_text_reduced():
    """Reduced circulation is parsed correctly."""
    assert LineStatus.from_text("circulação condicionada") == LineStatus.REDUCED


def test_line_status_from_text_closed():
    """Closed status is parsed correctly."""
    assert LineStatus.from_text("encerrada") == LineStatus.CLOSED


def test_line_status_from_text_unknown():
    """Unknown text falls back to NORMAL."""
    assert LineStatus.from_text("something random") == LineStatus.NORMAL


# --- Severity sorting tests ---


MOCK_HTML_MULTI_DISRUPTION = """
<div class="et_pb_column fundo_linha_azul">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Azul</div>
<div class="circ_mobile">parcialmente interrompida</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detAzulMobile"><strong>Estado da Linha: </strong>parcialmente interrompida entre Reboleira e Pontinha.</div>
</div></div>
<div class="et_pb_column fundo_linha_amarela">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Amarela</div>
<div class="circ_mobile">interrompida</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detAmarelaMobile"><strong>Estado da Linha: </strong>interrompida por avaria.</div>
</div></div>
<div class="et_pb_column fundo_linha_verde">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Verde</div>
<div class="circ_mobile">normal</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detVerdMobile"><strong>Estado da Linha: </strong>normal.</div>
</div></div>
<div class="et_pb_column fundo_linha_vermelha">
<div class="et_pb_toggle_title">
<div style="display:inline-block">
<div class="nomeLinhaMobile">Linha Vermelha</div>
<div class="circ_mobile">circulação condicionada</div>
</div></div>
<div class="et_pb_toggle_content">
<div id="detVermMobile"><strong>Estado da Linha: </strong>circulação condicionada.</div>
</div></div>
"""


def test_parse_severity_sorting():
    """Alerts should be sorted by severity (most critical first)."""
    alerts = _parse_line_status(MOCK_HTML_MULTI_DISRUPTION)

    assert len(alerts) == 3
    # Interrupted (severity 1) should come first
    assert alerts[0].affected_lines == ["AM"]
    assert "interrompida" in alerts[0].title
    # Partial (severity 2) next
    assert alerts[1].affected_lines == ["AZ"]
    assert "parcialmente" in alerts[1].title
    # Reduced (severity 3) last
    assert alerts[2].affected_lines == ["VM"]
    assert "condicionada" in alerts[2].title


# --- Wait times tests ---


MOCK_WAIT_TIMES_RESPONSE = [
    {"linha": "AZ", "destino": "Reboleira", "tempoChegada1": 120, "tempoChegada2": 300},
    {"linha": "AZ", "destino": "Santa Apolónia", "tempoChegada1": 60, "tempoChegada2": None},
]


def _mock_json_response(data, status: int = 200):
    """Create a mock response with .json() method."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_get_wait_times_success(mock_session):
    """Test wait times retrieval from API."""
    mock_session.get = MagicMock(return_value=_mock_json_response(MOCK_WAIT_TIMES_RESPONSE))
    provider = MetroLisboaProvider(session=mock_session)

    arrivals = await provider.async_get_arrivals("AP")
    assert len(arrivals) == 3
    # First entry: Reboleira 120s = 2 min
    assert arrivals[0].line_id == "AZ"
    assert arrivals[0].line_name == "Linha Azul"
    assert arrivals[0].destination == "Reboleira"
    assert arrivals[0].estimated_arrival == "2 min"
    # Second entry for Reboleira: 300s = 5 min
    assert arrivals[1].estimated_arrival == "5 min"
    # Third entry: Santa Apolónia 60s = 1 min
    assert arrivals[2].destination == "Santa Apolónia"
    assert arrivals[2].estimated_arrival == "1 min"


@pytest.mark.asyncio
async def test_get_wait_times_empty(mock_session):
    """When wait times API returns empty, falls back to None (then GTFS static)."""
    mock_session.get = MagicMock(return_value=_mock_json_response([]))
    provider = MetroLisboaProvider(session=mock_session)

    # _get_wait_times returns None for empty, triggering parent fallback
    result = await provider._get_wait_times("AP")
    assert result is None


@pytest.mark.asyncio
async def test_get_wait_times_api_error(mock_session):
    """When wait times API errors, returns None."""
    mock_session.get = MagicMock(return_value=_mock_json_response(None, status=500))
    provider = MetroLisboaProvider(session=mock_session)

    result = await provider._get_wait_times("AP")
    assert result is None


@pytest.mark.asyncio
async def test_get_wait_times_network_error(mock_session):
    """When network error, returns None."""
    mock_session.get = MagicMock(side_effect=Exception("Timeout"))
    provider = MetroLisboaProvider(session=mock_session)

    result = await provider._get_wait_times("AP")
    assert result is None
