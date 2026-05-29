# Contribuir para o Transportes PT

Obrigado por considerares contribuir! Este guia explica o processo para manter a qualidade do projeto.

## Código de Conduta

Ao participar neste projeto, concordas em manter um ambiente respeitoso e inclusivo. Comportamento abusivo, discriminatório ou assediante não será tolerado.

## Como contribuir

### Reportar bugs

1. Verifica se o bug já foi reportado em [Issues](https://github.com/marcelomartins/hass-transportes-pt/issues)
2. Usa o template **Bug Report** ao criar uma issue
3. Inclui: versão do HA, versão da integração, logs relevantes, passos para reproduzir

### Sugerir funcionalidades

1. Abre uma issue com o template **Feature Request**
2. Descreve o caso de uso e o comportamento esperado
3. Aguarda feedback antes de começar a implementação

### Adicionar um operador de transportes

1. Abre uma issue descrevendo o operador e a fonte de dados (GTFS URL, API, etc.)
2. Após aprovação, cria um PR seguindo a secção [Desenvolvimento](#desenvolvimento)

## Git Flow

### Branches

| Branch | Propósito |
|--------|-----------|
| `main` | Produção estável. Protegida — só aceita PRs com aprovação |
| `develop` | Integração de funcionalidades. PRs de features vão para aqui |
| `feature/*` | Novas funcionalidades (ex: `feature/add-metro-mondego`) |
| `fix/*` | Correções de bugs (ex: `fix/stcp-url-resolution`) |
| `release/*` | Preparação de release (bump de versão, changelog) |
| `hotfix/*` | Correções urgentes em produção |

### Workflow

```
feature/add-operator-x
       │
       ▼
    develop  ←──  fix/broken-parser
       │
       ▼
  release/0.2.0
       │
       ▼
     main  ←──  hotfix/critical-fix
```

1. **Feature**: `develop` → cria branch `feature/nome` → PR para `develop`
2. **Fix**: `develop` → cria branch `fix/nome` → PR para `develop`
3. **Release**: `develop` → cria branch `release/x.y.z` → merge em `main` + tag → merge back em `develop`
4. **Hotfix**: `main` → cria branch `hotfix/nome` → PR para `main` + merge em `develop`

### Convenção de commits

Usa [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add CP comboios provider
fix: resolve STCP CKAN URL fallback
docs: update README with new operators
test: add GTFS parser edge cases
refactor: extract shared HTTP logic
ci: add coverage reporting
chore: bump gtfs-realtime-bindings
```

### Regras de proteção de branches

#### `main`
- ✅ Requer PR com pelo menos 1 aprovação
- ✅ Requer que CI passe (lint + tests + typecheck)
- ✅ Requer branches atualizadas antes de merge
- ✅ Requer commits assinados
- ✅ Não permite push direto
- ✅ Não permite force push
- ✅ Requer review de CODEOWNERS

#### `develop`
- ✅ Requer PR (auto-merge permitido após CI verde)
- ✅ Requer que CI passe
- ✅ Não permite force push

## Desenvolvimento

### Setup local

```bash
# Clone
git clone https://github.com/marcelomartins/hass-transportes-pt.git
cd hass-transportes-pt

# Cria ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instala dependências
pip install -e ".[dev]"

# Instala pre-commit hooks
pre-commit install
```

### Estrutura do projeto

```
custom_components/transportes_pt/
├── providers/          # Um ficheiro por operador
│   ├── __init__.py     # ABC TransitProvider + dataclasses
│   ├── gtfs_base.py    # Base class para operadores GTFS
│   ├── gtfs_utils.py   # Parser de GTFS Static
│   └── carris.py       # Exemplo de provider
├── __init__.py         # Setup da integração
├── config_flow.py      # UI de configuração
├── coordinator.py      # Data coordinator
├── sensor.py           # Sensores de chegadas
├── binary_sensor.py    # Alertas de serviço
└── device_tracker.py   # Rastreamento GPS
```

### Adicionar um novo operador GTFS

1. Cria `providers/novo_operador.py`:

```python
from .gtfs_base import GtfsProvider

class NovoOperadorProvider(GtfsProvider):
    @property
    def provider_id(self) -> str:
        return "novo_operador"

    @property
    def name(self) -> str:
        return "Novo Operador"

    @property
    def gtfs_url(self) -> str:
        return "https://example.com/gtfs.zip"
```

2. Adiciona a constante em `const.py`
3. Adiciona ao factory em `__init__.py`
4. Adiciona ao dropdown em `config_flow.py`
5. Escreve testes em `tests/test_novo_operador.py`

### Correr testes

```bash
# Todos os testes
pytest tests/ -v

# Com coverage
pytest tests/ -v --cov=custom_components/transportes_pt --cov-report=term-missing

# Apenas um ficheiro
pytest tests/test_gtfs_providers.py -v

# Lint
ruff check .
ruff format --check .

# Type check
mypy custom_components/transportes_pt
```

### Requisitos para PR

- [ ] Testes passam localmente (`pytest tests/ -v`)
- [ ] Lint sem erros (`ruff check .`)
- [ ] Formatação correta (`ruff format --check .`)
- [ ] Type check sem erros (`mypy custom_components/transportes_pt`)
- [ ] Testes adicionados para nova funcionalidade
- [ ] Documentação atualizada (README se necessário)
- [ ] Commit messages seguem Conventional Commits
- [ ] Branch atualizada com `develop`

## Release process

1. Cria branch `release/x.y.z` a partir de `develop`
2. Bump versão em `manifest.json` e `pyproject.toml`
3. Atualiza `CHANGELOG.md`
4. PR para `main`
5. Após merge, cria tag `vx.y.z` e GitHub Release
6. Merge `main` de volta em `develop`

## Licença

Ao contribuir, concordas que as tuas contribuições serão licenciadas sob a licença MIT do projeto.
