"""Constants for the Transportes PT integration."""

from datetime import timedelta

DOMAIN = "transportes_pt"

# Providers
PROVIDER_CARRIS_METROPOLITANA = "carris_metropolitana"
PROVIDER_CARRIS = "carris"
PROVIDER_STCP = "stcp"
PROVIDER_METRO_PORTO = "metro_porto"
PROVIDER_CP = "cp"
PROVIDER_METRO_LISBOA = "metro_lisboa"
PROVIDER_FERTAGUS = "fertagus"
PROVIDER_TRANSTEJO = "transtejo"
PROVIDER_MTS = "mts"
PROVIDER_TCB = "tcb"
PROVIDER_TUB = "tub"
PROVIDER_HORARIOS_FUNCHAL = "horarios_funchal"
PROVIDER_MOBICASCAIS = "mobicascais"
PROVIDER_CIM_TAMEGA_SOUSA = "cim_tamega_sousa"
PROVIDER_BUSWAY_COIMBRA = "busway_coimbra"
PROVIDER_BUSWAY_CIRA = "busway_cira"
PROVIDER_MOBIAVE = "mobiave"
PROVIDER_TUBA = "tuba"
PROVIDER_GUIMABUS = "guimabus"

# Carris Metropolitana API v2
CARRIS_BASE_URL = "https://api.carrismetropolitana.pt/v2"

# Transtejo Soflusa (WordPress REST API)
TTSL_BASE_URL = "https://ttsl.pt/wp-json/wp/v2"
TTSL_PAGE_ID = 24

# Default polling intervals
DEFAULT_SCAN_INTERVAL_ARRIVALS = timedelta(seconds=30)
DEFAULT_SCAN_INTERVAL_ALERTS = timedelta(minutes=5)
DEFAULT_SCAN_INTERVAL_VEHICLES = timedelta(seconds=15)

# Config keys
CONF_PROVIDER = "provider"
CONF_STOPS = "stops"
CONF_LINES = "lines"
CONF_SCAN_INTERVAL_ARRIVALS = "scan_interval_arrivals"
CONF_SCAN_INTERVAL_ALERTS = "scan_interval_alerts"
CONF_SCAN_INTERVAL_VEHICLES = "scan_interval_vehicles"
CONF_ENABLE_VEHICLES = "enable_vehicles"

# Platforms
PLATFORMS = ["sensor", "binary_sensor", "device_tracker"]
