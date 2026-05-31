# Transportes PT 🚌

[![CI](https://github.com/marcelomartins/hass-transportes-pt/actions/workflows/ci.yml/badge.svg)](https://github.com/marcelomartins/hass-transportes-pt/actions)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Integração custom para [Home Assistant](https://www.home-assistant.io/) com dados em tempo real dos transportes públicos de Portugal.

## Operadores suportados

### Lisboa / AML

| Operador | Tipo | Tempo Real | Fonte |
|----------|------|:----------:|-------|
| Carris Metropolitana | Autocarro | ✅ | REST API |
| Carris (CCFL) | Autocarro + Eléctrico | ✅ | GTFS + GTFS-RT |
| Metro de Lisboa | Metro | ⚡ | GTFS + API (alertas + tempos de espera) |
| Transtejo Soflusa | Ferry | 🕒 | GTFS Static |
| Fertagus | Comboio suburbano | 🕒 | GTFS Static |
| MTS — Metro Sul do Tejo | Metro ligeiro | 🕒 | GTFS Static |
| TCB (Barreiro) | Autocarro | 🕒 | GTFS Static |
| MobiCascais | Autocarro | 🕒 | GTFS Static |

### Porto

| Operador | Tipo | Tempo Real | Fonte |
|----------|------|:----------:|-------|
| STCP | Autocarro | ✅ | GTFS + NGSI/FIWARE |
| Metro do Porto | Metro | ⚡ | GTFS + HTML scraping (alertas) |

### Nacional

| Operador | Tipo | Tempo Real | Fonte |
|----------|------|:----------:|-------|
| CP — Comboios de Portugal | Comboio | 🕒 | GTFS Static |

### Norte

| Operador | Tipo | Tempo Real | Fonte |
|----------|------|:----------:|-------|
| TUB (Braga) | Autocarro | 🕒 | GTFS Static |
| TUBA (Barcelos) | Autocarro | 🕒 | GTFS Static |
| Guimabus (Guimarães) | Autocarro | 🕒 | GTFS Static |
| Mobiave (V.N. Famalicão) | Autocarro | 🕒 | GTFS Static |
| CIM Tâmega e Sousa | Autocarro | 🕒 | GTFS Static |

### Centro

| Operador | Tipo | Tempo Real | Fonte |
|----------|------|:----------:|-------|
| Busway (Coimbra) | Autocarro | 🕒 | GTFS Static |
| Busway CIRA (Aveiro) | Autocarro | 🕒 | GTFS Static |

### Ilhas

| Operador | Tipo | Tempo Real | Fonte |
|----------|------|:----------:|-------|
| Horários do Funchal | Autocarro | 🕒 | GTFS Static |

> ✅ = tempo real (posição GPS e ETAs)  
> ⚡ = tempo real parcial (alertas de serviço e tempos de espera estimados)  
> 🕒 = horário estático (chegadas baseadas no calendário GTFS)

## Funcionalidades

- **Chegadas em tempo real** — minutos até o próximo autocarro, com detalhes de linha e destino
- **Horários GTFS** — se não há tempo real, mostra o horário programado
- **Alertas de serviço** — notificação de perturbações nas tuas linhas/paragens (Metro de Lisboa: estado operacional por linha em tempo real)
- **Tempos de espera Metro de Lisboa** — minutos estimados até o próximo comboio, por estação
- **Rastreamento de veículos** — posição GPS dos autocarros em tempo real (Carris Metropolitana, Carris CCFL, STCP)
- **Config Flow UI** — configuração visual sem editar YAML
- **Multi-operador** — configura várias integrações lado a lado
- **Traduções** — Português e Inglês
- **Blueprints** — automações pré-feitas para notificações

## Instalação

### HACS (recomendado)

1. Abre HACS no teu Home Assistant
2. Vai a **Integrações** → menu ⋮ → **Repositórios personalizados**
3. Adiciona `https://github.com/marcelomartins/hass-transportes-pt` como tipo **Integração**
4. Procura "Transportes PT" e instala
5. Reinicia o Home Assistant

### Manual

1. Copia a pasta `custom_components/transportes_pt` para `config/custom_components/`
2. Reinicia o Home Assistant

## Configuração

1. Vai a **Definições** → **Dispositivos e Serviços** → **Adicionar Integração**
2. Procura "Transportes PT"
3. Seleciona o operador (agrupados por região)
4. Escolhe as paragens que queres monitorizar
5. Configura opções (rastreamento de veículos, filtro de linhas)

> 💡 Podes adicionar múltiplas integrações para monitorizar vários operadores em simultâneo.

## Entidades criadas

| Tipo | Nome | Estado | Atributos |
|------|------|--------|-----------|
| `sensor` | Paragem {id} | Minutos até próxima chegada | linha, destino, próximas 5 chegadas |
| `binary_sensor` | Alertas de Serviço | ON se há alertas ativos | título, descrição, linhas afetadas |
| `device_tracker` | Veículo {id} | GPS position | linha, trip, heading, speed |

## Exemplo de automação

```yaml
automation:
  - alias: "Notificar autocarro a 5 minutos"
    trigger:
      - platform: numeric_state
        entity_id: sensor.paragem_060002
        below: 5
    action:
      - service: notify.mobile_app
        data:
          title: "Autocarro a chegar!"
          message: >
            Linha {{ state_attr('sensor.paragem_060002', 'next_line') }}
            para {{ state_attr('sensor.paragem_060002', 'next_destination') }}
            chega em {{ states('sensor.paragem_060002') }} minutos.
```

## Blueprints incluídos

| Blueprint | Descrição |
|-----------|-----------|
| `notify_bus_arriving` | Notifica quando o autocarro está a X minutos |
| `notify_service_alert` | Notifica quando há um alerta de serviço |
| `notify_significant_delay` | Notifica quando o atraso excede um limiar |

Para importar: **Definições** → **Automações** → **Blueprints** → **Importar Blueprint**

## Serviços

| Serviço | Descrição |
|---------|-----------|
| `transportes_pt.plan_trip` | Planeia uma viagem entre duas paragens (emite evento `transportes_pt_trip_planned`) |

## Arquitetura

```
providers/
├── __init__.py          # TransitProvider ABC + dataclasses
├── gtfs_utils.py        # GTFS Static parser (ZIP/CSV)
├── gtfs_rt_utils.py     # GTFS-RT protobuf parser
├── gtfs_base.py         # GtfsProvider base class
├── carris_metropolitana.py  # REST API (tempo real)
├── carris.py            # GTFS + GTFS-RT
├── stcp.py              # GTFS + NGSI/FIWARE realtime
├── metro_porto.py       # GTFS Static
├── cp.py                # GTFS Static
├── metro_lisboa.py      # GTFS + API (alertas + tempos de espera)
├── fertagus.py          # GTFS Static
├── transtejo.py         # GTFS Static
├── mts.py               # GTFS Static
├── tcb.py               # GTFS Static
├── tub.py               # GTFS Static
├── horarios_funchal.py  # GTFS Static
├── mobicascais.py       # GTFS Static
├── cim_tamega_sousa.py  # GTFS Static
├── busway_coimbra.py    # GTFS Static
├── busway_cira.py       # GTFS Static
├── mobiave.py           # GTFS Static
├── tuba.py              # GTFS Static
└── guimabus.py          # GTFS Static
```

## Desenvolvimento

```bash
# Instalar dependências de desenvolvimento
pip install -e ".[dev]"

# Correr testes
pytest tests/ -v

# Lint
ruff check .

# Type check
mypy custom_components/transportes_pt
```

### Adicionar novo operador

Para adicionar um operador GTFS, cria um ficheiro em `providers/`:

```python
from .gtfs_base import GtfsProvider

class NovoProvider(GtfsProvider):
    @property
    def provider_id(self) -> str:
        return "novo_operador"

    @property
    def name(self) -> str:
        return "Novo Operador"

    @property
    def gtfs_url(self) -> str:
        return "https://exemplo.pt/gtfs.zip"
```

Depois adiciona o provider em `const.py`, `__init__.py` e `config_flow.py`.

## Licença

MIT
