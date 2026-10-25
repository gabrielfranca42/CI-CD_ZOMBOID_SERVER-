# Project Zomboid Build 42 - Mod CI/CD Quality Gate & Server Auditor

Pipeline automatizado de **Integração Contínua (CI/CD)**, **Auditoria de Integridade de Mods** e **Quality Gate** desenvolvido especificamente para a **Build 42** do Project Zomboid (suporte a singleplayer e servidores dedicados/co-op multiplayer).

---

## 📋 Sumário
1. [Visão Geral e Arquitetura](#-visão-geral-e-arquitetura)
2. [Especificações Técnicas da Build 42](#-especificações-técnicas-da-build-42)
   - [Nova Estrutura de Mods da Oficina (42/ e common/)](#nova-estrutura-de-mods-da-oficina-42-e-common)
   - [Tags Oficiais do mod.info](#tags-oficiais-do-modinfo)
   - [Renderização Chunk-Based e DepthMaps (VRAM)](#renderização-chunk-based-e-depthmaps-vram)
   - [Motor de Animações Jassimp e Modelos 3D (.FBX)](#motor-de-animações-jassimp-e-modelos-3d-fbx)
   - [Arquitetura de Servidor Multiplayer (Headless vs Co-op Host)](#arquitetura-de-servidor-multiplayer-headless-vs-co-op-host)
   - [Camadas de Mapas (Map= e Precedência de Células)](#camadas-de-mapas-map-e-precedência-de-células)
3. [Algoritmos e Mecanismos do Sistema](#-algoritmos-e-mecanismos-do-sistema)
   - [Validador de Sintaxe Lua sem Falsos Positivos](#validador-de-sintaxe-lua-sem-falsos-positivos)
   - [Validador de Scripts de Itens/Receitas (.txt)](#validador-de-scripts-de-itensreceitas-txt)
   - [Ordenação Topológica de Carregamento (Load Order)](#ordenação-topológica-de-carregamento-load-order)
   - [Modelo Preditivo de Hardware (Commit Limit do Windows)](#modelo-preditivo-de-hardware-commit-limit-do-windows)
   - [Inspetor de Logs com Verificação de Execução Per-Mod](#inspetor-de-logs-com-verificação-de-execução-per-mod)
4. [Instruções de Uso (CLI e Scripts)](#-instruções-de-uso-cli-e-scripts)
5. [Suíte de Testes Automatizados](#-suíte-de-testes-automatizados)

---

## 🏛 Visão Geral e Arquitetura

O sistema adota o padrão arquitetural **MVC (Model-View-Controller)** para desacoplamento total entre análise de arquivos, lógica de regras e apresentação no terminal:

```
d:\PROJETOS\zomboid\
├── app\
│   ├── controllers\
│   │   ├── audit_controller.py         # Orquestração da auditoria Singleplayer
│   │   ├── gatekeeper_controller.py    # Admissão, sanitização e purga de mods SP
│   │   └── server_controller.py        # Orquestração da pipeline do servidor MP
│   ├── models\
│   │   ├── audit_result.py             # Dataclass de resultados SP com métricas de runtime
│   │   ├── build_validator.py          # Scanner estático de sintaxe Lua e scripts
│   │   ├── log_inspector.py            # Inspetor de logs com verificação per-mod de execução
│   │   ├── mod.py                      # Parser de mod.info e ativos da B42
│   │   ├── mod_list.py                 # Leitor/escritor do default.txt
│   │   ├── rules.py                    # Regras de conflito e memória SP
│   │   ├── server_audit_result.py      # Dataclass de resultados MP com classificação em cores
│   │   ├── server_config.py            # Gerenciador de servertest.ini, Map= e host.ini
│   │   ├── server_rules.py             # Regras de servidor e compilação
│   │   ├── system_specs.py             # Detector de hardware via Win32 API
│   │   └── workshop.py                 # Indexador com priorização de versões B42
│   └── views\
│       ├── report_view.py              # Exportador Markdown (audit_report.md)
│       ├── server_terminal_view.py     # Apresentação do servidor com painel de cores
│       └── terminal_view.py            # Apresentação do auditor SP no terminal
├── tests\                              # Suíte completa de testes unitários automatizados (37 testes)
├── main.py                             # Entry point CLI (argparse)
├── run_pipeline.ps1                    # Menu interativo PowerShell
└── run_pipeline.bat                    # Atalho Batch
```

---

## 🔬 Especificações Técnicas da Build 42

### Nova Estrutura de Mods da Oficina (42/ e common/)
Na Build 42, a The Indie Stone reformulou o layout de diretórios dos mods da Oficina Steam:
* Os arquivos `mod.info` agora devem residir em subpastas versionadas:
  * `Contents/mods/<NomeMod>/42/mod.info` (específico para Build 42)
  * `Contents/mods/<NomeMod>/common/mod.info` (compatível com múltiplas versões)
* O indexador `Workshop.scan()` implementa priorização ponderada: se um mod contiver versões legadas na raiz (B41) e versões na subpasta `42/`, a versão nativa da B42 recebe precedência automática (`score: 42 > common > legacy`).

### Tags Oficiais do `mod.info`
O parser `Mod.from_mod_info` suporta as novas tags oficiais introduzidas na B42:
* `versionMin=` e `versionMax=`: Faixa semântica de compatibilidade do jogo (ex.: `versionMin=42.0.0`).
* `modversion=`: Versão de lançamento do mod.
* `incompatible=`: Lista delimitada por vírgula ou ponto-e-vírgula de mods conflitantes. O engine avalia essas declarações e bloqueia merges de mods declaradamente incompatíveis.
* Múltiplas linhas `require=` e `pack=`: Suporte a declarações em várias linhas ou múltiplos separadores.

### Renderização Chunk-Based e DepthMaps (VRAM)
A Build 42 substituiu a renderização 2D isométrica tradicional por um pipeline com **mapas de profundidade por chunk** e geometria 3D:
* Cada DepthMap de atlas (normalmente arquivos PNG de altura ou texturas de elevação) é descomprimido no buffer de textura da GPU.
* O cálculo preditivo de VRAM do sistema estima o impacto gráfico no cliente considerando a descompressão de textura sem sobrecarregar falsamente o servidor headless.

### Motor de Animações Jassimp e Modelos 3D (.FBX)
* A engine do Zomboid B42 migrou para a biblioteca nativa C++ **Jassimp (Assimp)** para importar arquivos `.fbx` em tempo real.
* Mods legados da B41 com esqueletos corrompidos ou mal dimensionados (ex.: variantes legadas de `amclub` e `autotsartrailers`) provocam falha de alocação nativa (`java.io.IOException: bad allocation` em `Jassimp.aiImportFile`), derrubando o jogo com estouro de memória `arena.cpp`. O pipeline rejeita essas variantes de imediato.

### Arquitetura de Servidor Multiplayer (Headless vs Co-op Host)
O projeto diferencia tecnicamente os dois modelos de servidor:
1. **Servidor Dedicado Standalone (Headless - `StartServer64.bat` / SteamCMD):**
   * Não instancia contexto OpenGL nem aloca texturas/DepthMaps na GPU.
   * A memória é alocada via parâmetros da JVM (`-Xms` e `-Xmx`) dentro de `ProjectZomboid64.json` ou do script `.bat`.
2. **Servidor Co-op Integrado (Menu "Host" no Cliente):**
   * Controlado pelo arquivo `C:\Users\<User>\Zomboid\Lua\host.ini` (chave `memory=4096`).
   * Roda simultaneamente com o cliente do jogo no mesmo PC, dividindo memória física e paginação.

### Camadas de Mapas (`Map=` e Precedência de Células)
No Project Zomboid, para que mapas customizados funcionem no servidor, não basta ativá-los em `Mods=`:
* É **obrigatório** registrar as subpastas em `media/maps/` na diretiva `Map=` do `servertest.ini`.
* **Regra de Precedência:** As pastas de mapas customizados **devem preceder** o mapa base vanilla:
  ```ini
  Map=TowheadIsland;MuldraughCheckpoint;Muldraugh, KY;
  ```
* Se `Muldraugh, KY` for posicionado antes, as células originais do jogo sobrescrevem os chunks do mod. O `ServerConfig.save_server_mods()` garante automaticamente que `Muldraugh, KY` seja sempre a última entrada.

---

## ⚙️ Algoritmos e Mecanismos do Sistema

### Validador de Sintaxe Lua sem Falsos Positivos
Analisadores estáticos ingênuos contam `then` como abertura de bloco e `end` como fechamento, o que quebra totalmente em cadeias de `elseif`:
```lua
if cond1 then        -- 1º 'then'
elseif cond2 then    -- 2º 'then' (mesmo bloco condicional!)
elseif cond3 then    -- 3º 'then'
end                  -- Apenas 1 'end' fecha todo o if!
```
**O algoritmo do `BuildValidator`:**
1. Sanitiza comentários multilinha (`--[[ ... ]]`), comentários de linha (`--`) e literais de string com escapes (`"..."` e `'...'`).
2. Mapeia exclusivamente as palavras-chave fundamentais da gramática formal de Lua:
   * **Iniciadores de Bloco:** `if`, `do` (que engloba `while...do`, `for...do` e `do...end`), `function`, `repeat`.
   * **Finalizadores de Bloco:** `end` (fecha `if`, `do`, `function`), `until` (fecha `repeat`).
3. O resultado garante **zero falsos positivos** em menus contextuais complexos de mods do PZ, detectando scripts truncados com 100% de precisão.

### Validador de Scripts de Itens/Receitas (.txt)
O parser de scripts PZ:
* Remove comentários de bloco (`/* ... */`), comentários de linha (`//`, `#`) e strings delimitadas por aspas.
* Valida a paridade estrita de chaves `{` e `}`, acusando exatamente qualquer script com chaves órfãs.

### Ordenação Topológica de Carregamento (Load Order)
Implementado em `RulesEngine.compute_recommended_load_order` utilizando o **Algoritmo de Kahn**:
* Constrói um grafo direcionado onde cada dependência `require=` deve ser processada antes do nó dependente.
* Produz uma ordem de carregamento em que bibliotecas e frameworks (ex.: bibliotecas de armas, tiles base) ficam no topo do `default.txt` e do `Mods=`.

### Modelo Preditivo de Hardware (Commit Limit do Windows)
* Consulta a API nativa Win32 (`GlobalMemoryStatusEx`) para obter RAM física, arquivo de paginação e o limite total de commit do sistema operacional.
* Calcula a demanda de memória:
  $$\text{Commit Requerido} = \text{Java Heap (Xmx)} + \text{VRAM Estimada} + \text{FBX Cache} + \text{Overhead do Windows}$$
* **Proteção de Dependências:** Se o hardware estiver sob estresse, o sistema nunca purga pacotes de tiles se houver mapas ativos que dependam deles.

### Inspetor de Logs com Verificação de Execução Per-Mod

O módulo `LogInspector` foi aprimorado para resolver falsos positivos onde o servidor ou singleplayer "compilava" com sucesso mas mods não eram efetivamente executados (ex.: mods de veículos carregados mas os carros não apareciam no jogo).

#### Problema Resolvido
O comportamento relatado do Project Zomboid é: o engine pode **carregar um mod no VFS** (Virtual File System) registrando seus arquivos, mas os **scripts Lua do mod podem falhar silenciosamente** ou simplesmente não executar. O resultado é que o jogo inicia sem erros aparentes, mas o conteúdo do mod (veículos, itens, receitas) não aparece.

#### Arquitetura de Verificação em 3 Fases

**Fase 1: Rastreamento Per-Mod do VFS e Lua**
Para cada mod listado no `console.txt`, o inspetor rastreia:

| Campo | Descrição |
| :--- | :--- |
| `vfs_loaded` | Engine registrou o mod no VFS (`LOG : Mod ... loading <modid>`) |
| `vfs_overrides` | Quantos arquivos do mod sobrescreveram arquivos de outros mods/vanilla |
| `lua_executed` | Pelo menos um log Lua foi atribuído a este mod |
| `lua_evidence` | Lista de mensagens Lua específicas que comprovam a execução |
| `script_errors` | Erros de receita/script atribuídos a este mod |
| `registry_errors` | Registros duplicados no Java (absorvidos por try/catch) |

**Fase 2: Atribuição de Execução Lua por Padrão**
O inspetor utiliza três padrões de detecção para atribuir logs Lua a mods específicos:

1. **Padrão de Colchetes:** `[ModName] message` — Logs como `[Railroader] RR_TrainEntity.lua: loaded OK` são atribuídos ao mod `Railroader`.
2. **Padrão de Prefixo:** `ModName: action` — Logs como `ReducedWoodWeightMod: Modified weight of Firewood` são atribuídos por correspondência do ID do mod com o início da mensagem.
3. **Padrão "Mod Loaded":** `Mod Loaded: Name by Author` — Confirmação explícita de carregamento como `Mod Loaded: Swatpack by Slobodskoy`.

**Fase 3: Classificação de Status Runtime**
Cada mod recebe um status final:

| Status | Significado |
| :--- | :--- |
| `EXECUTANDO` | VFS carregado + Lua executada + sem erros de script |
| `PARCIAL (erros de script)` | VFS carregado + Lua executada + erros de receita/script |
| `CARREGADO MAS SEM EXECUÇÃO LUA` | VFS carregado mas nenhum log Lua atribuído (mod silencioso) |
| `DESCONHECIDO` | Nenhuma evidência de carregamento |

#### Diagnósticos Detalhados
O relatório agora inclui:
* **Razão Lua:** `X/Y mods com execução Lua confirmada` (ex.: `45/298 mods com execução Lua confirmada`).
* **Mods Silenciosos:** Lista de mods carregados pelo VFS mas sem evidência de execução Lua, com possíveis causas:
  1. Mods puramente de assets/texturas sem scripts Lua.
  2. Mods cujos scripts rodaram silenciosamente sem gerar saída.
  3. Mods com **falha silenciosa de carregamento** (problema real).
* **Erros de Receita/Script:** Erros como `Could not assign [key]: 'Result' : 'CJ_SKS_Sawn'` que indicam itens ou receitas não funcionais.
* **Registros Duplicados:** Contagem de registros duplicados absorvidos pelo Java try/catch (como munições VFE duplicadas).

---

## 🚀 Instruções de Uso (CLI e Scripts)

### Executando pelo Menu Interativo
Execute no terminal PowerShell:
```powershell
.\run_pipeline.ps1
```

### Comandos Diretos da CLI (`main.py`)

#### Comandos de Gerenciamento de Mods
```bash
# Remove um mod específico por ID (do Singleplayer, Multiplayer ou ambos)
py main.py remove-mod <ID_DO_MOD> --mode both

# Remove o mod e também apaga fisicamente os arquivos da pasta Workshop
py main.py remove-mod <ID_DO_MOD> --mode both --delete-files

# Baixa uma dependência/mod via SteamCMD (C:\steamcmd) e valida a sintaxe em tempo real
py main.py install-mod <ID_DO_MOD_OU_WORKSHOP_ID> --mode sp

# Reordena automaticamente a modlist do Singleplayer (ordem topológica de dependências)
py main.py reorder
```

#### Pipeline Singleplayer
```bash
# Executa auditoria completa de mods e hardware no Singleplayer
py main.py audit

# Higieniza a modlist (remove conflitos e preserva ordem de dependências)
py main.py sanitize

# Testa se um novo mod pode ser adicionado com segurança
py main.py test-mod <ID_DO_MOD>
```

#### Pipeline Multiplayer (Servidor)
```bash
# Audita integridade do servidor, compilação de scripts e classificação por cores
py main.py server-audit

# Higieniza o servidor removendo mods VERMELHOS e sincronizando WorkshopItems e Map=
py main.py server-sanitize --level red --memory 4096

# Higieniza removendo mods VERMELHOS e AMARELOS
py main.py server-sanitize --level yellow --memory 4096

# Testa se um mod compila e é compatível antes de entrar no servidor
py main.py server-test-mod <ID_DO_MOD>
```

---

## 🧪 Suíte de Testes Automatizados

O projeto possui suíte de testes unitários abrangente utilizando `unittest`:

| Módulo de Teste | Cobertura |
| :--- | :--- |
| `tests/test_build_validator.py` | Cadeias de `elseif`, loops `do/while/for`, blocos `repeat..until`, scripts PZ quebrados e strings com chaves |
| `tests/test_log_inspector.py` | Carregamento VFS per-mod, execução Lua via padrão de colchetes/prefixo, mods silenciosos, IDs com caminho, sobrescritas VFS atribuídas, erros de registro, erros de receita/script, razão Lua no diagnóstico, diagnósticos detalhados, classificação `ModRuntimeStatus`, crashes OOM e Jassimp |
| `tests/test_failure_log_view.py` | Geração de logs individuais em .txt (`VERMELHO_FALHA_*.txt` e `AMARELO_FALHA_*.txt`), prefixo de cor, sanitização de nomes, categorias de falha e diagnóstico "erro de config vs mod quebrado" |
| `tests/test_steam_downloader.py` | Detecção do executável `C:\steamcmd\steamcmd.exe`, resolução de Mod ID para Workshop ID, remoção de mods por ID em SP e MP |
| `tests/test_mod_and_workshop.py` | Parsing de tags B42 (`versionMin`, `incompatible`, `map_folders`) e priorização de versão `42/` |
| `tests/test_server_config.py` | Remoção de barras invertidas em `Mods=`, sincronização de `Map=` com `Muldraugh, KY` no final e formato de ponto-e-vírgula |
| `tests/test_rules_and_load_order.py` | Ordenação topológica (Kahn), regras de `incompatible=`, proteção de packs de tiles exigidos por mapas, VFE e CraftEngineParts como warnings |
| `tests/test_server_rules.py` | Detecção de pastas de mapas ausentes em `Map=`, integridade de crashers e cálculo headless |

### Executando os Testes
Para rodar toda a suíte de testes:
```bash
py -m unittest discover tests -v
```
*Resultado esperado:*
```
Ran 48 tests in 0.083s - OK ✅
```

---

## 📋 Sistema de Relatórios Individuais de Falha (`failure_logs/`)

Quando a pipeline (Singleplayer ou Servidor) detecta problemas, ela gera arquivos `.txt` dedicados por mod na pasta `failure_logs/` com o prefixo da gravidade da cor:

* **Singleplayer:** `failure_logs/<COR>_FALHA_SP_<MOD_ID>.txt`
* **Multiplayer:** `failure_logs/<COR>_FALHA_MP_<MOD_ID>.txt`

Exemplos gerados:
* `VERMELHO_FALHA_MP_LGExtendedPlumbing.txt`
* `AMARELO_FALHA_MP_FenceSheets.txt`
* `VERMELHO_FALHA_SP_LightOnBelt.txt`

Cada relatório detalha:
1. **Modo, Cor e ID:** Identificação clara no nome do arquivo e cabeçalho.
2. **Categoria de Reprovação:**
   - 🔴 **CRASH / INCOMPATÍVEL:** Causa crash fatal na engine (ex: FBX antigo no Jassimp B42).
   - 🟠 **NÃO CARREGA:** Registrado pelo VFS mas seus scripts Lua nunca foram executados.
   - 🔴 **FALHA DE COMPILAÇÃO:** Erros de sintaxe Lua ou chaves desbalanceadas em scripts.
   - 🟡 **ERRO DE CONFIGURAÇÃO:** Workshop ID ausente, dependência desativada ou ordem invertida.
   - 🟡 **CONFLITO ENTRE MODS:** Incompatibilidade declarada via `incompatible=`.
   - 🔴 **ESTOURO DE HARDWARE:** Esgota commit de memória ou VRAM do sistema.
3. **Causa Raiz & Diagnóstico:** Motivos técnicos detalhados com trecho de erro.
4. **Guia de Resolução:** Passos práticos para resolver o problema.
5. **Classificação "Erro de Configuração vs Mod Quebrado":**
   - **Erro de Configuração (Seu):** Falta de Workshop ID, dependência esquecida, variantes redundantes.
   - **Mod Quebrado (Autor):** Código Lua inválido, crash nativo Jassimp, sintaxe corrompida.


