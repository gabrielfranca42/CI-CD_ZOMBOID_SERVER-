# Project Zomboid Mod CI/CD Quality Gate Report

- **Game Version:** 42.21.0 4a0e9546ec
revision=4a0e9546ec pzbullet=1.0.0.28
- **System RAM:** 15.95 GB (Free: 7.98 GB)
- **Active Mods:** 146
- **Installed Mods:** 174
- **DepthMaps:** 164 (8.32 MB) -> ~0.96 GB VRAM
- **Runtime Log Evidence:** `SUCESSO (Arranque e sessão confirmados em console.txt)`
- **Mods VFS Loaded:** 149
- **Mods Lua Confirmed:** 17
- **Mods Silent (no Lua evidence):** 132

## Status Summary
- **Singleplayer:** `APROVADO (Confirmado pelo Log do Jogo)`
- **Multiplayer:** `REPROVADO / INVIÁVEL NO MOMENTO`
- **Pipeline Decision:** `APPROVED`

## Multiplayer Analysis
- Capacidade de Hardware: Hostear servidor + jogar no mesmo PC de 15.95 GB RAM com mais de 100 mods causará falta de memória física a menos que a paginação do Windows seja expandida.

## Warnings
- [AVISO DE SOBREPOSIÇÃO - VFE DUPLICADO]
   Versões legadas ativas: ['VFExpansion3']
   Versões Redux B42 ativas: ['VFExpansionReduxb42', 'VFExpansion3Reduxb42', 'VFExpansion2Reduxb42']
   Diagnóstico: O carregador Java do PZ absorve registros duplicados de munição via try/catch sem derrubar o jogo, mas recomenda-se manter apenas o Redux para evitar duplicidade de itens no spawn.
- [AVISO DE SOBRESCRITA VFS - CraftEngineParts]
   Você ativou 4 variantes: ['CraftEnginePartsCheap', 'CraftEnginePartsCheapest', 'CraftEngineParts', 'CraftEnginePartsModerate']
   Diagnóstico: O sistema de arquivos virtual (VFS) do PZ não crasha com variantes múltiplas; a última variante na ordem de carregamento sobrescreve as tabelas de receitas e drop.
- [MODS DUPLICADOS] 'LightOnBelt' e 'FixedLightOnBeltAF' estão ativos simultaneamente. Mantenha apenas o Fixed.
- [DEPENDÊNCIA AUSENTE] Mod 'BobrMinigun' requer 'SWMG', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'VFExpansion3' requer 'VFExpansion1', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'errorMagnifier' requer 'ChuckleberryFinnAlertSystem,', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod '67CommandoMobileFortressB42' requer 'PROJECTRVInterior42,67commando', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'AMGeneralTankerFunctionality' requer '78amgeneralM35A2,\78amgeneralM49A2C,\78amgeneralM50A3', que não está ativo.
- [ALERTA DE MEMÓRIA GRÁFICA] 164 DepthMaps ativos. Consumo de VRAM alto (~0.96 GB).
- [ANIMAÇÕES E MODELOS 3D (.FBX)] 2263 modelos/esqueletos ativos no total.
   Mods com mais modelos: Brita's Armor, KATTAJ1, VFE Redux, Fluffy Hair.
   Status: Aprovado pelo teste de hardware (consumo estimado ~1.1 GB absorvido na memória).
- [EVIDÊNCIA DE LOG] Sessão executada com sucesso (24/10/2026 20:54:00): Jogo inicializou (149 mods carregados pelo VFS, 17/149 com execução Lua confirmada, 8826 sobrescritas VFS absorvidas, 8 avisos recuperados pelo Java, saída limpa).
   Mods com execução Lua confirmada: 17/149
- [ATENÇÃO - MODS SEM EXECUÇÃO LUA DETECTADA] 132 mod(s) foram carregados pelo VFS mas não apresentaram evidência de execução Lua no console.txt. Isso pode significar: (1) mods puramente de assets/texturas que não possuem scripts Lua, (2) mods cujos scripts Lua rodaram silenciosamente sem gerar saída no console, ou (3) mods com falha silenciosa de carregamento. Mods silenciosos: ['PROJECTRVInterior42', '1VCESTANDARD', 'CaptainJuezo1_WIP_B42', '50%metalweight', 'damnlib', '62daimlerFerret', '67commando', '67CommandoMobileFortressB42', '78amgeneralM35A2', '78amgeneralM35A2extra']
- [ERROS DE SCRIPT/RECEITA DETECTADOS] 64 erro(s) de carregamento de receitas/scripts. Esses itens ou receitas não funcionarão no jogo. Primeiros erros: ["ERROR: General      f:0 at FluidContainerScript.load           > Sanitizing container name 'Large Bucket', name may not contain whitespaces.", "ERROR: General      f:0 at Recipe.Load                         > Could not assign [key]: 'Result' : 'CJ_SKS_Sawn'.", "ERROR: General      f:0 at Recipe.Load                         > Could not assign [key]: 'Sound' : 'Sawing'."]
- [REGISTROS DUPLICADOS ABSORVIDOS] 8 registros duplicados foram absorvidos pelo Java try/catch. Esses não causam crash mas indicam sobreposição de conteúdo entre mods.
- [ERROS DE RECEITA/SCRIPT NO LOG] 64 erro(s) detectados. Itens ou receitas afetadas podem não funcionar no jogo.
