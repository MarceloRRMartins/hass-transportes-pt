"""Config flow for Transportes PT."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    BooleanSelector,
)

from .const import (
    CONF_ENABLE_VEHICLES,
    CONF_LINES,
    CONF_PROVIDER,
    CONF_STOPS,
    DOMAIN,
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
from .providers.carris_metropolitana import CarrisMetropolitanaProvider

_LOGGER = logging.getLogger(__name__)

PROVIDERS = [
    # --- Lisboa ---
    SelectOptionDict(value=PROVIDER_CARRIS_METROPOLITANA, label="Carris Metropolitana"),
    SelectOptionDict(value=PROVIDER_CARRIS, label="Carris (Lisboa)"),
    SelectOptionDict(value=PROVIDER_METRO_LISBOA, label="Metro de Lisboa"),
    SelectOptionDict(value=PROVIDER_TRANSTEJO, label="Transtejo Soflusa"),
    SelectOptionDict(value=PROVIDER_FERTAGUS, label="Fertagus"),
    SelectOptionDict(value=PROVIDER_MTS, label="MTS - Metro Sul do Tejo"),
    SelectOptionDict(value=PROVIDER_TCB, label="TCB (Barreiro)"),
    SelectOptionDict(value=PROVIDER_MOBICASCAIS, label="MobiCascais"),
    # --- Porto ---
    SelectOptionDict(value=PROVIDER_STCP, label="STCP (Porto)"),
    SelectOptionDict(value=PROVIDER_METRO_PORTO, label="Metro do Porto"),
    # --- Nacional ---
    SelectOptionDict(value=PROVIDER_CP, label="CP - Comboios de Portugal"),
    # --- Norte ---
    SelectOptionDict(value=PROVIDER_TUB, label="TUB (Braga)"),
    SelectOptionDict(value=PROVIDER_TUBA, label="TUBA (Barcelos)"),
    SelectOptionDict(value=PROVIDER_GUIMABUS, label="Guimabus (Guimarães)"),
    SelectOptionDict(value=PROVIDER_MOBIAVE, label="Mobiave (V.N. Famalicão)"),
    SelectOptionDict(value=PROVIDER_CIM_TAMEGA_SOUSA, label="CIM Tâmega e Sousa"),
    # --- Centro ---
    SelectOptionDict(value=PROVIDER_BUSWAY_COIMBRA, label="Busway (Coimbra)"),
    SelectOptionDict(value=PROVIDER_BUSWAY_CIRA, label="Busway CIRA (Aveiro)"),
    # --- Ilhas ---
    SelectOptionDict(value=PROVIDER_HORARIOS_FUNCHAL, label="Horários do Funchal"),
]


class TransportesPTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Transportes PT."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._provider_id: str = ""
        self._stops: list[str] = []
        self._available_stops: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the provider selection step."""
        if user_input is not None:
            self._provider_id = user_input[CONF_PROVIDER]
            return await self.async_step_stops()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER, default=PROVIDER_CARRIS_METROPOLITANA): SelectSelector(
                        SelectSelectorConfig(
                            options=PROVIDERS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_stops(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle stop selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_ids = user_input.get(CONF_STOPS, [])
            if not stop_ids:
                errors["base"] = "no_stops"
            else:
                self._stops = stop_ids
                return await self.async_step_options()

        # Fetch stops for selection
        if not self._available_stops:
            session = async_get_clientsession(self.hass)
            provider = self._create_flow_provider(session)
            await provider.async_init()

            try:
                if not await provider.async_test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    stops = await provider.async_get_stops()
                    # Sort by municipality then name for easier browsing
                    stops.sort(key=lambda s: (s.municipality or "", s.name))
                    self._available_stops = [
                        {
                            "value": s.stop_id,
                            "label": f"{s.name} [{s.municipality or ''}] ({s.stop_id})",
                        }
                        for s in stops
                    ]
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="stops",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="stops",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOPS): SelectSelector(
                        SelectSelectorConfig(
                            options=self._available_stops,
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle advanced options step."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Transportes PT ({self._provider_id})",
                data={
                    CONF_PROVIDER: self._provider_id,
                    CONF_STOPS: self._stops,
                    CONF_LINES: user_input.get(CONF_LINES, []),
                    CONF_ENABLE_VEHICLES: user_input.get(CONF_ENABLE_VEHICLES, True),
                },
            )

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LINES, default=[]): TextSelector(
                        TextSelectorConfig(multiline=False)
                    ),
                    vol.Optional(CONF_ENABLE_VEHICLES, default=True): BooleanSelector(),
                }
            ),
        )

    def _create_flow_provider(self, session: aiohttp.ClientSession):
        """Create a provider for the config flow (stop fetching)."""
        if self._provider_id == PROVIDER_CARRIS_METROPOLITANA:
            return CarrisMetropolitanaProvider(session=session)

        from .providers.carris import CarrisProvider
        from .providers.stcp import StcpProvider
        from .providers.metro_porto import MetroPortoProvider
        from .providers.cp import CpProvider
        from .providers.metro_lisboa import MetroLisboaProvider
        from .providers.fertagus import FertagusProvider
        from .providers.transtejo import TranstejoProvider
        from .providers.mts import MtsProvider
        from .providers.tcb import TcbProvider
        from .providers.tub import TubProvider
        from .providers.horarios_funchal import HorariosFunchalProvider
        from .providers.mobicascais import MobiCascaisProvider
        from .providers.cim_tamega_sousa import CimTsProvider
        from .providers.busway_coimbra import BuswayCoimbraProvider
        from .providers.busway_cira import BuswayCiraProvider
        from .providers.mobiave import MobiaveProvider
        from .providers.tuba import TubaProvider
        from .providers.guimabus import GuimabusProvider

        providers_map = {
            PROVIDER_CARRIS: CarrisProvider,
            PROVIDER_STCP: StcpProvider,
            PROVIDER_METRO_PORTO: MetroPortoProvider,
            PROVIDER_CP: CpProvider,
            PROVIDER_METRO_LISBOA: MetroLisboaProvider,
            PROVIDER_FERTAGUS: FertagusProvider,
            PROVIDER_TRANSTEJO: TranstejoProvider,
            PROVIDER_MTS: MtsProvider,
            PROVIDER_TCB: TcbProvider,
            PROVIDER_TUB: TubProvider,
            PROVIDER_HORARIOS_FUNCHAL: HorariosFunchalProvider,
            PROVIDER_MOBICASCAIS: MobiCascaisProvider,
            PROVIDER_CIM_TAMEGA_SOUSA: CimTsProvider,
            PROVIDER_BUSWAY_COIMBRA: BuswayCoimbraProvider,
            PROVIDER_BUSWAY_CIRA: BuswayCiraProvider,
            PROVIDER_MOBIAVE: MobiaveProvider,
            PROVIDER_TUBA: TubaProvider,
            PROVIDER_GUIMABUS: GuimabusProvider,
        }

        provider_cls = providers_map.get(self._provider_id)
        if provider_cls is None:
            raise ValueError(f"Unknown provider: {self._provider_id}")
        return provider_cls(session=session)
