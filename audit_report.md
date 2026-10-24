# Project Zomboid Mod CI/CD Quality Gate Report

- **Game Version:** 42.21.0 4a0e9546ec
revision=4a0e9546ec pzbullet=1.0.0.28
- **System RAM:** 15.95 GB (Free: 8.0 GB)
- **Active Mods:** 147
- **Installed Mods:** 174
- **DepthMaps:** 164 (8.32 MB) -> ~2.56 GB VRAM

## Status Summary
- **Singleplayer:** `APROVADO`
- **Multiplayer:** `REPROVADO / INVIÁVEL NO MOMENTO`
- **Pipeline Decision:** `APPROVED`

## Multiplayer Analysis
- Nenhum servidor dedicado configurado em C:\Users\User\Zomboid\Server.
- Capacidade de Hardware: Hostear servidor + jogar no mesmo PC de 15.95 GB RAM com mais de 100 mods causará falta de memória física a menos que a paginação do Windows seja expandida.

## Warnings
- [DEPENDÊNCIA AUSENTE] Mod 'Towhead-Island-FOB' requer 'melos_tiles_for_miles_pack', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'Towhead-Island-FOB' requer 'simonMDsTiles', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'Muldraugh-Checkpoint' requer 'melos_tiles_for_miles_pack', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'Muldraugh-Checkpoint' requer 'simonMDsTiles', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'BobrMinigun' requer 'SWMG', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'RickGrimesClass' requer 'SWMG', que não está ativo.
- [DEPENDÊNCIA AUSENTE] Mod 'RickGrimesClass' requer 'GunsOfMarz', que não está ativo.
- [ALERTA DE MEMÓRIA GRÁFICA] 164 DepthMaps ativos. Consumo de VRAM alto (~2.56 GB).
- [ANIMAÇÕES E MODELOS 3D (.FBX)] 2250 modelos/esqueletos ativos no total.
   Mods com mais modelos: Brita's Armor, KATTAJ1, VFE Redux, Fluffy Hair.
   Status: Aprovado pelo teste de hardware (consumo estimado ~1.1 GB absorvido na memória).
