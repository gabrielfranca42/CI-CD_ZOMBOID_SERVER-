# Project Zomboid Build 42 - Mod CI/CD Quality Gate & Server Auditor

Pipeline automatizado de **Integração Contínua (CI/CD)**, **Auditoria de Integridade de Mods**, **Gerenciamento de Downloads via SteamCMD** e **Quality Gate** desenvolvido especificamente para a **Build 42** do Project Zomboid (suporte a singleplayer e servidores dedicados/co-op multiplayer).

---

## 📋 Sumário
1. [Visão Geral e Arquitetura](#-visão-geral-e-arquitetura)
2. [Especificações Técnicas da Build 42](#-especificações-técnicas-da-build-42)
   - [Nova Estrutura de Mods da Oficina (42.*, common/ e raiz)](#nova-estrutura-de-mods-da-oficina-42-common-e-raiz)
   - [Tags Oficiais do mod.info](#tags-oficiais-do-modinfo)
   - [Renderização Chunk-Based e DepthMaps (VRAM)](#renderização-chunk-based-e-depthmaps-vram)
   - [Motor de Animações Jassimp e Modelos 3D (.FBX)](#motor-de-animações-jassimp-e-modelos-3d-fbx)
   - [Arquitetura de Servidor Multiplayer (Headless vs Co-op Host)](#arquitetura-de-servidor-multiplayer-headless-vs-co-op-host)
   - [Camadas de Mapas (Map= e Precedência de Células)](#camadas-de-mapas-map-e-precedência-de-células)
3. [Mecanismos do CI/CD e Sincronização](#-mecanismos-do-cicd-e-sincronização)
   - [Manifesto JSON de Mods do Servidor (`data/server_mods_manifest.json`)](#manifesto-json-de-mods-do-servidor)
   - [Download e Validação via SteamCMD sem Depender da Steam Desktop](#download-e-validação-via-steamcmd)
   - [Implantação Automática em Mods Locais (`C:\Users\User\Zomboid\mods\`)](#implantação-automática-em-mods-locais)
   - [Arquitetura Zero-Steam Boot (Carregamento Offline Definitivo)](#arquitetura-zero-steam-boot)
4. [Catálogo de Bugs Conhecidos do Project Zomboid e Steam](#-catálogo-de-bugs-conhecidos-do-project-zomboid-e-steam)
   - [Bug 1: Steam DLL Secondary Drive Mismatch (Staging Folder Not Found)](#bug-1-steam-dll-secondary-drive-mismatch-staging-folder-not-found)
   - [Bug 2: Loop Infinito em `download 0/0` ("Descarregado: X de 117")](#bug-2-loop-infinito-em-download-00-descarregado-x-de-117)
   - [Bug 3: Crash com NullPointerException em `GameServerWorkshopItems.java`](#bug-3-crash-com-nullpointerexception-em-gameserverworkshopitemsjava)
   - [Bug 4: Resolução Relativa de Diretório de Workshop no Servidor PZ](#bug-4-resolução-relativa-de-diretório-de-workshop-no-servidor-pz)
   - [Bug 5: Colisão de Pastas entre Pacotes e Mods Standalone](#bug-5-colisão-de-pastas-entre-pacotes-e-mods-standalone)
   - [Bug 6: Crash Fatal de Memória no Jassimp B42 (`arena.cpp` / Bad Allocation)](#bug-6-crash-fatal-de-memória-no-jassimp-b42-arenacpp--bad-allocation)
5. [Algoritmos e Mecanismos de Qualidade](#-algoritmos-e-mecanismos-de-qualidade)
   - [Validador de Sintaxe Lua sem Falsos Positivos](#validador-de-sintaxe-lua-sem-falsos-positivos)
   - [Validador de Scripts de Itens/Receitas (.txt)](#validador-de-scripts-de-itensreceitas-txt)
   - [Ordenação Topológica de Carregamento (Algoritmo de Kahn)](#ordenação-topológica-de-carregamento-algoritmo-de-kahn)
   - [Modelo Preditivo de Hardware (Commit Limit do Windows)](#modelo-preditivo-de-hardware-commit-limit-do-windows)
   - [Inspetor de Logs com Verificação de Execução Per-Mod](#inspetor-de-logs-com-verificação-de-execução-per-mod)
6. [Instruções de Uso (CLI e Scripts)](#-instruções-de-uso-cli-e-scripts)
7. [Suíte de Testes Automatizados (50 Testes)](#-suíte-de-testes-automatizados-50-testes)
8. [Sistema de Relatórios Individuais de Falha (`failure_logs/`)](#-sistema-de-relatórios-individuais-de-falha-failure_logs)

---

## 🏛 Visão Geral e Arquitetura

O sistema adota o padrão arquitetural **MVC (Model-View-Controller)** para desacoplamento total entre análise de arquivos, lógica de regras, automação de rede e apresentação no terminal:

```
d:\PROJETOS\zomboid\
├── app\
│   ├── controllers\
│   │   ├── audit_controller.py         # Orquestração da auditoria Singleplayer
│   │   ├── gatekeeper_controller.py    # Admissão, sanitização e purga de mods SP
│   │   └── server_controller.py        # Orquestração da pipeline do servidor MP e Zero-Steam
│   ├── models\
│   │   ├── audit_result.py             # Dataclass de resultados SP com métricas de runtime
│   │   ├── build_validator.py          # Scanner estático de sintaxe Lua e scripts PZ
│   │   ├── log_inspector.py            # Inspetor de logs com detecção per-mod e de loops
│   │   ├── mod.py                      # Parser de mod.info e ativos da B42
│   │   ├── mod_list.py                 # Leitor/escritor do default.txt (SP)
│   │   ├── mod_manifest.py             # Gerenciador do manifesto JSON e implantação local B42
│   │   ├── rules.py                    # Regras de conflito e memória SP
│   │   ├── server_audit_result.py      # Dataclass de resultados MP com classificação em cores
│   │   ├── server_config.py            # Gerenciador de servertest.ini, host.ini e Zero-Steam Boot
│   │   ├── server_rules.py             # Regras de servidor e compilação
│   │   ├── steam_downloader.py         # Wrapper SteamCMD com download em lote e auto-deploy
│   │   ├── system_specs.py             # Detector de hardware via Win32 API
│   │   └── workshop.py                 # Indexador com priorização de versões B42
│   └── views\
│       ├── failure_log_view.py         # Gerador de relatórios individuais de falha (.txt por mod)
│       ├── report_view.py              # Exportador Markdown (audit_report.md)
│       ├── server_terminal_view.py     # Apresentação do servidor com painel de cores
│       └── terminal_view.py            # Apresentação do auditor SP no terminal
├── data\
│   └── server_mods_manifest.json       # Manifesto estruturado de mods do servidor
├── tests\                              # Suíte completa de testes unitários automatizados (50 testes)
├── main.py                             # Entry point CLI (argparse)
├── run_pipeline.ps1                    # Menu interativo PowerShell
└── run_pipeline.bat                    # Atalho Batch
```

---

## 🔬 Especificações Técnicas da Build 42

### Nova Estrutura de Mods da Oficina (42.*, common/ e raiz)
Na Build 42, a The Indie Stone reformulou o layout de diretórios dos mods da Oficina Steam:
* Os arquivos `mod.info` e subpastas de código agora residem em pastas versionadas:
  * `Contents/mods/<NomeMod>/42/mod.info` (nativa Build 42)
  * `Contents/mods/<NomeMod>/42.0/`, `42.15/`, `42.20/` (sub-versões específicas da B42)
  * `Contents/mods/<NomeMod>/common/mod.info` (compatível com múltiplas versões)
* O `ModManifestManager.find_best_mod_folder()` implementa priorização hierárquica automática:
  $$\text{Prioridade: } 42.\text{X (maior versão)} > 42 > \text{common} > \text{raiz}$$

### Tags Oficiais do `mod.info`
O parser `Mod.from_mod_info` suporta as novas tags oficiais introduzidas na B42:
* `versionMin=` e `versionMax=`: Faixa semântica de compatibilidade do jogo (ex.: `versionMin=42.0.0`).
* `modversion=`: Versão de lançamento do mod.
* `incompatible=`: Lista delimitada por vírgula ou ponto-e-vírgula de mods conflitantes. O engine avalia essas declarações e bloqueia merges de mods declaradamente incompatíveis.
* Múltiplas linhas `require=` e `pack=`: Suporte a declarações em várias linhas ou múltiplos separadores.

### Renderização Chunk-Based e DepthMaps (VRAM)
A Build 42 substituiu a renderização 2D isométrica tradicional por um pipeline com **mapas de profundidade por chunk** e geometria 3D:
* Cada DepthMap de atlas é descomprimido no buffer de textura da GPU.
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

## ⚡ Mecanismos do CI/CD e Sincronização

### Manifesto JSON de Mods do Servidor
O pipeline introduz o arquivo `data/server_mods_manifest.json`, que mantém o estado canônico de todos os mods aprovados para o servidor:
```json
{
  "app_id": "108600",
  "mods": {
    "RCMilitaryTentsMod": {
      "mod_id": "RCMilitaryTentsMod",
      "workshop_id": "3718884098",
      "name": "[B42] Military Tents",
      "version": "42",
      "synced": true,
      "local_path": "C:\\Users\\User\\Zomboid\\mods\\RCMilitaryTentsMod"
    }
  }
}
```
* **Mapeamento Biunívoco:** Mapeia `mod_id` interno para o `workshop_id` numérico da Steam.
* **Sincronização Bidirecional:** Atualizado automaticamente a partir do `servertest.ini` e do catálogo local da Oficina.

### Download e Validação via SteamCMD
Em vez de depender do cliente da Steam (que sofre com bugs de caminhos e drivers secundários), o pipeline utiliza o executável oficial de linha de comando da Valve (`C:\steamcmd\steamcmd.exe`):
* Autenticação anônima isolada (`+login anonymous +workshop_download_item 108600 <ID> +quit`).
* Executa fora do contexto do jogo, contornando travas de DLL.
* Valida a integridade do pacote baixado antes de registrar nas configurações.

### Implantação Automática em Mods Locais
Sempre que um mod é baixado via SteamCMD ou sincronizado pelo manifesto, o sistema executa a **implantação física imediata** em:
`C:\Users\<User>\Zomboid\mods\<NomeMod>\`
* Extrai a pasta de versão correta (priorizando B42) para que o arquivo `mod.info` resida na raiz do diretório do mod local.
* Trata pacotes com múltiplos mods internos, desmembrando e implantando cada um individualmente.
* Garante compatibilidade 100% com o motor do jogo sem necessidade de subscrição ativa no cliente.

### Arquitetura Zero-Steam Boot
A descoberta definitiva do projeto para estabilidade do servidor Co-op:
* O Project Zomboid possui dois campos de mods no `servertest.ini`:
  1. **`Mods=`**: Diz ao jogo quais mods carregar no motor (itens, scripts, veículos, mapas).
  2. **`WorkshopItems=`**: Diz ao servidor para tentar baixar/atualizar itens pela API da Steam no boot.
* **O Problema:** Como a Steam tenta verificar staging em disco secundário, o servidor trava no carregamento em `WorkshopItems=`.
* **A Solução Zero-Steam:** Com todos os mods já baixados e implantados pelo CI/CD em `C:\Users\<User>\Zomboid\mods\`, o pipeline **limpa a diretiva `WorkshopItems=`** (deixando-a vazia) e mantém todos os 133 mods em `Mods=`.
* **Resultado:** O servidor inicializa **100% via disco local**, sem qualquer consulta à API da Steam no boot, reduzindo o tempo de carregamento de minutos para segundos e eliminando 100% dos travamentos.

---

## 🐛 Catálogo de Bugs Conhecidos do Project Zomboid e Steam

Esta seção documenta em nível de engenharia reversa os bugs estruturais identificados durante a execução do servidor e como o nosso CI/CD os contorna.

### Bug 1: Steam DLL Secondary Drive Mismatch (Staging Folder Not Found)
* **Cenário:** Steam instalada no drive `C:\Program Files (x86)\Steam` e o Project Zomboid instalado em disco secundário (`D:\SteamLibrary\steamapps\common\ProjectZomboid`).
* **Sintoma nos Logs (`console.txt`):**
  ```log
  LOG : General f:0> SERVER: src\clientdll\contentupdatecontext.cpp (2086) : Staging library folder not found
  LOG : General f:0> SERVER: src\clientdll\contentupdatecontext.cpp (2087) : Install library folder not found
  ```
* **Mecanismo da Falha:** A DLL da Valve (`steam_api64.dll`) carregada pelo processo escravo Java do servidor não consegue correlacionar os caminhos entre discos diferentes no Windows quando invocada via API de servidor dedicado. Ela tenta alocar a pasta de staging no disco C: e falha silenciosamente.
* **Solução:** **Zero-Steam Boot** (limpeza de `WorkshopItems=`). Com isso, a chamada para a DLL de download da Steam nunca é executada.

---

### Bug 2: Loop Infinito em `download 0/0` ("Descarregado: X de 117")
* **Sintoma nos Logs (`coop-console.txt`):**
  ```log
  LOG : General f:0 st:12.261.911> Workshop: GetItemState()=None ID=3120702374
  LOG : General f:0 st:12.261.911> Workshop: item state CheckItemState -> DownloadPending ID=3120702374
  LOG : General f:0 st:12.261.945> Workshop: DownloadPending GetItemState()=NeedsUpdate|DownloadPending ID=3120702374
  LOG : General f:0 st:12.261.945> Workshop: download 0/0 ID=3120702374
  LOG : General f:0 st:12.262.046> Workshop: DownloadPending GetItemState()=NeedsUpdate|DownloadPending ID=3120702374
  LOG : General f:0 st:12.262.046> Workshop: download 0/0 ID=3120702374
  ```
* **Mecanismo da Falha:**
  1. O servidor consulta `GetItemState(ID)` para um item listado em `WorkshopItems=`.
  2. Devido ao Bug 1, a Steam relata `GetItemState()=None` mesmo com o mod completamente presente em `D:\SteamLibrary\steamapps\workshop\content\108600\<ID>`.
  3. O PZ solicita o download via Steam API e entra no estado `DownloadPending`.
  4. A Steam não consegue baixar devido à falha de staging, mas **não emite o callback de erro (`onItemNotDownloaded`)**.
  5. A classe Java `GameServerWorkshopItems.java` do PZ realiza polling em `GetItemState()` a cada 100ms. Como nenhum callback chega, o servidor fica preso para sempre em loop infinito, exibindo `download 0/0` e travando a interface em contagens como `34 de 118`, `55 de 118` ou `77 de 117`.
* **Solução:** O CI/CD pré-baixa os itens via SteamCMD e os implanta localmente, desativando a checagem no `servertest.ini`.

---

### Bug 3: Crash com NullPointerException em `GameServerWorkshopItems.java`
* **Sintoma nos Logs:**
  ```log
  ERROR: General f:0 st:1.234.567> Exception in thread "GameServerWorkshopItems" java.lang.NullPointerException
      at zombie.network.GameServerWorkshopItems.deleteDirectory(GameServerWorkshopItems.java:248)
      at zombie.network.GameServerWorkshopItems.onItemNotDownloaded(GameServerWorkshopItems.java:189)
  ```
* **Mecanismo da Falha:** Quando a Steam retorna explicitamente `k_EResultFail` (`result=2`), o servidor tenta limpar a pasta temporária do mod chamando `deleteDirectory(folder)`. Quando a pasta não foi instanciada no contexto da Steam, a variável do caminho é `null`, causando `NullPointerException` imediato e derrubando o servidor antes de inicializar o mapa.
* **Solução:** O Gatekeeper remove itens problemáticos de `WorkshopItems=` antes do boot.

---

### Bug 4: Resolução Relativa de Diretório de Workshop no Servidor PZ
* **Sintoma nos Logs:**
  ```log
  LOG : General f:0> Workshop: not removing install folder because it does not exist:
  "D:\SteamLibrary\steamapps\common\ProjectZomboid\steamapps\workshop\content\108600\3309896124"
  ```
* **Mecanismo da Falha:** O engine Java do PZ resolve o caminho da Workshop **relativo ao diretório de instalação do executável** (`steamapps\common\ProjectZomboid\steamapps\...`) em vez de resolver relativo à raiz da biblioteca da Steam (`steamapps\workshop\...`). Isso causa descompasso de arquivos e falha de detecção de mods já instalados.
* **Solução:** Implantação direta na pasta local do usuário (`C:\Users\<User>\Zomboid\mods\`), cujo caminho é absoluto e independente da biblioteca Steam.

---

### Bug 5: Colisão de Pastas entre Pacotes e Mods Standalone
* **Cenário:** Mod packs de armas/veículos (ex.: pacote VFE `3611718925`) que contêm subpastas como `VFE`, `VFEP93` e `VFES`, coexistindo com uploads standalone de outros autores na Oficina (ex.: `3761077099`) que utilizam o mesmo nome de pasta de destino `VFE`.
* **Mecanismo da Falha:** Em cópias ingênuas baseadas no nome da pasta (`entry.name`), o mod standalone sobrescrevia a pasta do mod pack no destino local, apagando variantes necessárias para o servidor.
* **Solução:** `ModManifestManager.deploy_workshop_item_to_local_mods` lê o `mod.info` e utiliza prioritariamente o `id=` do mod (ex.: `VFExpansionReduxb42` vs `VFExpansion1`), garantindo coexistência sem sobrescrita.

---

### Bug 6: Crash Fatal de Memória no Jassimp B42 (`arena.cpp` / Bad Allocation)
* **Cenário:** Mods de veículos da B41 que contêm modelos `.fbx` com nós malformados ou armações não adaptadas ao novo esqueleto humanoide da B42 (ex.: `amclub`, `autotsartrailers`, `tsarslib`).
* **Sintoma nos Logs:**
  ```log
  FATAL: Jassimp.aiImportFile: bad allocation
  Crash in arena.cpp: Out of memory in dynamic array allocation
  ```
* **Mecanismo da Falha:** O motor nativo em C++ Jassimp tenta alocar buffers contíguos de memória para animações com pesos de vértices inválidos, esgotando o heap nativo da JVM.
* **Solução:** O `ServerRules` e `Gatekeeper` possuem regras estritas com bloqueio preventivo (Severidade 🔴 VERMELHO) para todas as variantes conhecidas dessas bibliotecas.

---

## ⚙️ Algoritmos e Mecanismos de Qualidade

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

### Ordenação Topológica de Carregamento (Algoritmo de Kahn)
Implementado em `RulesEngine.compute_recommended_load_order`:
* Constrói um grafo direcionado onde cada dependência `require=` deve ser processada antes do nó dependente.
* Produz uma ordem de carregamento em que bibliotecas e frameworks (ex.: bibliotecas de armas, tiles base) ficam no topo do `default.txt` e do `Mods=`.

### Modelo Preditivo de Hardware (Commit Limit do Windows)
* Consulta a API nativa Win32 (`GlobalMemoryStatusEx`) para obter RAM física, arquivo de paginação e o limite total de commit do sistema operacional.
* Calcula a demanda de memória:
  $$\text{Commit Requerido} = \text{Java Heap (Xmx)} + \text{VRAM Estimada} + \text{FBX Cache} + \text{Overhead do Windows}$$
* **Proteção de Dependências:** Se o hardware estiver sob estresse, o sistema nunca purga pacotes de tiles se houver mapas ativos que dependam deles.

### Inspetor de Logs com Verificação de Execução Per-Mod
O módulo `LogInspector` rastreia a execução real no `console.txt`:
1. **Rastreamento VFS:** Confirma se o engine montou os arquivos do mod no Virtual File System.
2. **Atribuição de Execução Lua:** Detecta se scripts do mod realmente executaram via padrões de colchetes `[ModName]`, prefixos `ModName:` e confirmações `Mod Loaded:`.
3. **Classificação de Status:**
   * `EXECUTANDO`: VFS carregado + Lua executada + sem erros de script.
   * `PARCIAL`: VFS carregado + erros de receita/script.
   * `SILENCIOSO`: VFS carregado mas sem saída Lua (possível falha silenciosa).

---

## 🚀 Instruções de Uso (CLI e Scripts)

### Executando pelo Menu Interativo
Execute no terminal PowerShell:
```powershell
.\run_pipeline.ps1
```

O menu oferece 14 opções organizadas por fluxo:
* **[1] a [4]:** Pipeline Singleplayer (Auditoria, Higienização, Purga e Teste de Mod).
* **[5] a [8]:** Pipeline Multiplayer (Auditoria por Cores, Higienização Vermelhos/Amarelos, Teste de Admissão).
* **[9] a [14]:** Gerenciamento Avançado:
  * `[9]` Remover mod por ID (SP, MP ou ambos).
  * `[10]` Baixar e validar mod/dependência via SteamCMD.
  * `[11]` Reordenar modlist automaticamente (ordem topológica).
  * `[12]` Sincronizar todos os Workshop IDs via SteamCMD.
  * `[13]` Baixar e implantar mods via Manifesto JSON (`data/server_mods_manifest.json`).
  * `[14]` **Ativar Zero-Steam Boot (Limpa WorkshopItems= e inicia direto sem Steam).**

---

### Comandos Diretos da CLI (`main.py`)

#### Gerenciamento de Servidor e Zero-Steam
```bash
# Ativa o Zero-Steam Boot (mantém Mods= e limpa WorkshopItems=)
py main.py zero-steam

# Implanta todos os mods da Workshop na pasta local do usuário
py main.py deploy-local --clean-workshop-items

# Sincroniza e baixa todos os mods listados no manifesto JSON
py main.py sync-manifest

# Pré-sincroniza todos os Workshop IDs do servertest.ini via SteamCMD
py main.py server-sync
```

#### Pipeline Singleplayer
```bash
# Executa auditoria completa de mods e hardware no Singleplayer
py main.py audit

# Higieniza a modlist (remove conflitos e preserva dependências)
py main.py sanitize

# Testa se um novo mod pode ser adicionado com segurança
py main.py test-mod <ID_DO_MOD>

# Reordena a modlist em ordem topológica ideal
py main.py reorder
```

#### Pipeline Multiplayer (Servidor)
```bash
# Audita integridade do servidor, compilação de scripts e classificação por cores
py main.py server-audit

# Higieniza o servidor removendo mods VERMELHOS (graves/crash)
py main.py server-sanitize --level red --memory 4096

# Higieniza removendo mods VERMELHOS e AMARELOS
py main.py server-sanitize --level yellow --memory 4096

# Testa compilação e compatibilidade de um mod antes de entrar no servidor
py main.py server-test-mod <ID_DO_MOD>

# Baixa e valida um mod via SteamCMD com implantação automática local
py main.py install-mod <ID_OU_WORKSHOP_ID> --mode mp
```

---

## 🧪 Suíte de Testes Automatizados (50 Testes)

O projeto possui suíte de testes unitários abrangente utilizando `unittest`:

| Módulo de Teste | Qtd | Cobertura Principal |
| :--- | :---: | :--- |
| `tests/test_build_validator.py` | 7 | Cadeias de `elseif`, loops `do/while/for`, blocos `repeat..until`, scripts PZ quebrados e strings com chaves |
| `tests/test_log_inspector.py` | 13 | Carregamento VFS per-mod, execução Lua via colchetes/prefixo, mods silenciosos, IDs com caminho, sobrescritas VFS, erros de registro e receitas |
| `tests/test_failure_log_view.py` | 5 | Geração de logs individuais em .txt (`VERMELHO_FALHA_*.txt` e `AMARELO_FALHA_*.txt`), prefixo de cor, sanitização e categorias de falha |
| `tests/test_steam_downloader.py` | 6 | Detecção de executável `steamcmd.exe`, resolução numérica de Workshop ID, remoção em SP/MP e ativação do Zero-Steam Boot |
| `tests/test_mod_manifest.py` | 2 | Priorização de subpastas B42 (`42.15` vs `common`), extração de `id=` do `mod.info` e implantação local de pacotes |
| `tests/test_mod_and_workshop.py` | 4 | Parsing de tags B42 (`versionMin`, `incompatible`, `map_folders`) e priorização de versão `42/` |
| `tests/test_server_config.py` | 4 | Limpeza de barras invertidas em `Mods=`, sincronização de `Map=` com `Muldraugh, KY` no final e formato de ponto-e-vírgula |
| `tests/test_rules_and_load_order.py` | 5 | Ordenação topológica (Kahn), regras de `incompatible=`, proteção de packs de tiles exigidos por mapas |
| `tests/test_server_rules.py` | 4 | Detecção de pastas de mapas ausentes em `Map=`, integridade de crashers e cálculo de memória headless |

### Executando os Testes
```bash
py -m unittest discover tests -v
```
*Resultado esperado:*
```
Ran 50 tests in 0.105s - OK ✅
```

---

## 📋 Sistema de Relatórios Individuais de Falha (`failure_logs/`)

Quando a pipeline detecta problemas, ela gera arquivos `.txt` dedicados por mod na pasta `failure_logs/` (ignorada pelo git):

* **Singleplayer:** `failure_logs/<COR>_FALHA_SP_<MOD_ID>.txt`
* **Multiplayer:** `failure_logs/<COR>_FALHA_MP_<MOD_ID>.txt`

Exemplos gerados:
* `VERMELHO_FALHA_MP_LGExtendedPlumbing.txt`
* `AMARELO_FALHA_MP_FenceSheets.txt`
* `VERMELHO_FALHA_SP_LightOnBelt.txt`

Cada relatório detalha:
1. **Identificação Completa:** Nome do mod, ID interno, Workshop ID e severidade.
2. **Categoria de Reprovação:**
   - 🔴 **CRASH / INCOMPATÍVEL:** Causa crash fatal na engine (ex.: FBX antigo no Jassimp B42).
   - 🟠 **NÃO CARREGA:** Registrado pelo VFS mas seus scripts Lua nunca foram executados.
   - 🔴 **FALHA DE COMPILAÇÃO:** Erros de sintaxe Lua ou chaves desbalanceadas em scripts.
   - 🟡 **ERRO DE CONFIGURAÇÃO:** Workshop ID ausente, dependência desativada ou ordem invertida.
   - 🟡 **CONFLITO ENTRE MODS:** Incompatibilidade declarada via `incompatible=`.
   - 🔴 **ESTOURO DE HARDWARE:** Esgota commit de memória ou VRAM do sistema.
3. **Causa Raiz & Trecho de Erro:** Diagnóstico técnico exato extraído do código ou dos logs.
4. **Guia de Resolução:** Passos práticos para resolver o problema.
5. **Classificação de Responsabilidade:** Distinção explícita entre *"Erro de Configuração (Seu)"* e *"Mod Quebrado (Autor)"*.
