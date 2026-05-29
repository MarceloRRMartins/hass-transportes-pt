"""The Transportes PT integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ENABLE_VEHICLES,
    CONF_LINES,
    CONF_PROVIDER,
    CONF_STOPS,
    DOMAIN,
    PLATFORMS,
    PROVIDER_BUSWAY_CIRA,
    PROVIDER_BUSWAY_COIMBRA,
    PROVIDER_CARRIS,
    PROVIDER_CARRIS_METROPOLITANA,
    PROVIDER_CIM_TAMEGA_SOUSA,
    PROVIDER_CP,
    PROVIDER_FERTAGUS,
    PROVIDER_GUIMABUS,
    PROVIDER_HORARIOS_FUNCHAL,
    PROVIDER_METRO_LISBOA,
    PROVIDER_METRO_PORTO,
    PROVIDER_MOBIAVE,
    PROVIDER_MOBICASCAIS,
    PROVIDER_MTS,
    PROVIDER_STCP,
    PROVIDER_TCB,
    PROVIDER_TRANSTEJO,
    PROVIDER_TUB,
    PROVIDER_TUBA,
)
from .coordinator import TransportesCoordinator
from .providers import TransitProvider
from .providers.carris_metropolitana import CarrisMetropolitanaProvider
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

TransportesConfigEntry = ConfigEntry


def _create_provider(
    provider_id: str, hass: HomeAssistant
) -> TransitProvider:
    """Create a transit provider instance."""
    session = async_get_clientsession(hass)
    if provider_id == PROVIDER_CARRIS_METROPOLITANA:
        return CarrisMetropolitanaProvider(session=session)

    # Lazy-import GTFS-based providers to avoid import overhead
    if provider_id == PROVIDER_CARRIS:
        from .providers.carris import CarrisProvider
        return CarrisProvider(session=session)
    if provider_id == PROVIDER_STCP:
        from .providers.stcp import StcpProvider
        return StcpProvider(session=session)
    if provider_id == PROVIDER_METRO_PORTO:
        from .providers.metro_porto import MetroPortoProvider
        return MetroPortoProvider(session=session)
    if provider_id == PROVIDER_CP:
        from .providers.cp import CpProvider
        return CpProvider(session=session)
    if provider_id == PROVIDER_METRO_LISBOA:
        from .providers.metro_lisboa import MetroLisboaProvider
        return MetroLisboaProvider(session=session)
    if provider_id == PROVIDER_FERTAGUS:
        from .providers.fertagus import FertagusProvider
        return FertagusProvider(session=session)
    if provider_id == PROVIDER_TRANSTEJO:
        from .providers.transtejo import TranstejoProvider
        return TranstejoProvider(session=session)
    if provider_id == PROVIDER_MTS:
        from .providers.mts import MtsProvider
        return MtsProvider(session=session)
    if provider_id == PROVIDER_TCB:
        from .providers.tcb import TcbProvider
        return TcbProvider(session=session)
    if provider_id == PROVIDER_TUB:
        from .providers.tub import TubProvider
        return TubProvider(session=session)
    if provider_id == PROVIDER_HORARIOS_FUNCHAL:
        from .providers.horarios_funchal import HorariosFunchalProvider
        return HorariosFunchalProvider(session=session)
    if provider_id == PROVIDER_MOBICASCAIS:
        from .providers.mobicascais import MobiCascaisProvider
        return MobiCascaisProvider(session=session)
    if provider_id == PROVIDER_CIM_TAMEGA_SOUSA:
        from .providers.cim_tamega_sousa import CimTsProvider
        return CimTsProvider(session=session)
    if provider_id == PROVIDER_BUSWAY_COIMBRA:
        from .providers.busway_coimbra import BuswayCoimbraProvider
        return BuswayCoimbraProvider(session=session)
    if provider_id == PROVIDER_BUSWAY_CIRA:
        from .providers.busway_cira import BuswayCiraProvider
        return BuswayCiraProvider(session=session)
    if provider_id == PROVIDER_MOBIAVE:
        from .providers.mobiave import MobiaveProvider
        return MobiaveProvider(session=session)
    if provider_id == PROVIDER_TUBA:
        from .providers.tuba import TubaProvider
        return TubaProvider(session=session)
    if provider_id == PROVIDER_GUIMABUS:
        from .providers.guimabus import GuimabusProvider
        return GuimabusProvider(session=session)

    raise ValueError(f"Unknown provider: {provider_id}")


async def async_setup_entry(hass: HomeAssistant, entry: TransportesConfigEntry) -> bool:
    """Set up Transportes PT from a config entry."""
    provider_id = entry.data[CONF_PROVIDER]
    stop_ids = entry.data[CONF_STOPS]
    line_ids = entry.data.get(CONF_LINES)
    enable_vehicles = entry.data.get(CONF_ENABLE_VEHICLES, True)

    provider = _create_provider(provider_id, hass)
    await provider.async_init()

    coordinator = TransportesCoordinator(
        hass,
        provider=provider,
        stop_ids=stop_ids,
        line_ids=line_ids,
        enable_vehicles=enable_vehicles,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once, for the first entry)
    if len(hass.data[DOMAIN]) == 1:
        await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TransportesConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: TransportesCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.provider.async_close()

        # Unregister services when last entry is removed
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)

    return unload_ok
