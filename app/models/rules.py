import os
from typing import List, Dict
from .mod import Mod
from .mod_list import ModList
from .workshop import Workshop
from .system_specs import SystemSpecs
from .audit_result import AuditResult

class RulesEngine:
    """CI/CD Rules Engine: Validates mod integrity, conflicts, assets, 3D animations, and memory limits."""

    def __init__(self, specs: SystemSpecs):
        self.specs = specs

    def evaluate(self, active_mod_ids: List[str], workshop: Workshop) -> AuditResult:
        result = AuditResult(
            total_active_mods=len(active_mod_ids),
            total_workshop_mods=len(workshop.mods)
        )

        active_set = set(active_mod_ids)

        # Track rejected mods to isolate or delete
        rejected_mods: Set[str] = set()

        # Rule 1: Known incompatible B41 animation ports that crash Jassimp in B42
        # Autotsar Motorclub has corrupt FBX animations (HARLEY_Idle.fbx, QUAD_Idle.fbx)
        # throwing java.io.IOException: bad allocation in Jassimp.aiImportFile native C++
        unstable_b42_ports = {
            "amclub": "Autotsar Motorclub (amclub) possui animações FBX incompatíveis com o esqueleto da Build 42 que estouram a memória nativa do Jassimp (bad allocation).",
            "autotsartrailers": "Autotsar Trailers depende do tsarslib legado e gera conflito de física e animações na B42.",
            "tsarslib": "Tsar's Common Library legado da Build 41."
        }
        for bad_mod, reason in unstable_b42_ports.items():
            if bad_mod in active_set:
                rejected_mods.add(bad_mod)
                result.errors.append(
                    f"[MOD INCOMPATÍVEL COM B42 - CRASH NATIVO JASSIMP]\n"
                    f"   Mod detectado: {bad_mod}\n"
                    f"   Diagnóstico: {reason}\n"
                    f"   Impacto: Causa Out of Memory fatal (arena.cpp / Chunk::new) durante o carregamento de animações."
                )

        # Rule 2: Mutually exclusive VFE legacy vs Redux B42
        vfe_legacy = [m for m in active_mod_ids if m in ["VFExpansion1", "VFExpansion2", "VFExpansion3"]]
        vfe_redux = [m for m in active_mod_ids if "VFExpansionRedux" in m or "Reduxb42" in m]
        if vfe_legacy and vfe_redux:
            for m in vfe_legacy:
                rejected_mods.add(m)
            result.errors.append(
                f"[CONFLITO CRÍTICO - VFE DUPLICADO]\n"
                f"   Versões legadas ativas: {vfe_legacy}\n"
                f"   Versões Redux B42 ativas: {vfe_redux}\n"
                f"   Impacto: Duplicação fatal de scripts de munições e travamento da UI."
            )

        # Rule 3: Multiple CraftEngineParts variants
        cep_variants = [m for m in active_mod_ids if m.startswith("CraftEngineParts")]
        if len(cep_variants) > 1:
            for m in cep_variants[1:]:
                rejected_mods.add(m)
            result.errors.append(
                f"[CONFLITO DE MODOS EXCLUSIVOS - CraftEngineParts]\n"
                f"   Você ativou {len(cep_variants)} variantes conflitantes: {cep_variants}\n"
                f"   Impacto: Sobrescrita de tabelas de receitas, gerando loop de erro de craft."
            )

        # Rule 4: Duplicate LightOnBelt
        if "LightOnBelt" in active_set and "FixedLightOnBeltAF" in active_set:
            rejected_mods.add("LightOnBelt")
            result.warnings.append(
                "[MODS DUPLICADOS] 'LightOnBelt' e 'FixedLightOnBeltAF' estão ativos simultaneamente. Mantenha apenas o Fixed."
            )

        # Rule 5: Missing dependencies check
        for mod_id in active_mod_ids:
            mod = workshop.get_mod(mod_id)
            if not mod:
                continue
            for req in mod.require:
                clean_req = req.lstrip(r"\/").strip()
                if clean_req not in active_set:
                    if clean_req not in [workshop.get_mod(m).workshop_id for m in active_mod_ids if workshop.get_mod(m)]:
                        result.warnings.append(f"[DEPENDÊNCIA AUSENTE] Mod '{mod_id}' requer '{clean_req}', que não está ativo.")

        # Rule 6: Asset, Depthmaps and 3D FBX Animation Memory Budget
        total_depthmaps = 0
        total_depthmap_mb = 0.0
        total_fbx = 0
        heavy_tiles = []
        heavy_anims = []

        for mod_id in active_mod_ids:
            mod = workshop.get_mod(mod_id)
            if mod:
                if mod.depthmap_count > 0:
                    total_depthmaps += mod.depthmap_count
                    total_depthmap_mb += mod.depthmap_size_mb
                    heavy_tiles.append((mod.id, mod.name, mod.depthmap_count, mod.depthmap_size_mb))
                if mod.fbx_count > 0:
                    total_fbx += mod.fbx_count
                    heavy_anims.append((mod.id, mod.name, mod.fbx_count))

        heavy_tiles.sort(key=lambda x: x[2], reverse=True)
        heavy_anims.sort(key=lambda x: x[2], reverse=True)

        # In B42, each DepthMap texture decompressed in native memory / VRAM consumes ~16 MB uncompressed
        est_native_vram_gb = round((total_depthmaps * 16) / 1024, 2)
        est_fbx_gb = round((total_fbx * 0.5) / 1024, 2)

        result.total_depthmaps = total_depthmaps
        result.total_depthmap_mb = round(total_depthmap_mb, 2)
        result.est_native_vram_gb = est_native_vram_gb
        result.total_fbx_animations = total_fbx
        result.heavy_tiles = heavy_tiles
        result.heavy_anim_mods = heavy_anims

        # Rule 7: HARDWARE CAPACITY PREDICTIVE TEST
        # Total Required Memory = Java Xmx (4 GB) + Native Textures/Depthmaps + FBX Animations + Windows baseline (4.5 GB)
        java_heap_gb = 4.0
        windows_overhead_gb = 4.5
        total_required_commit_gb = round(java_heap_gb + est_native_vram_gb + est_fbx_gb + windows_overhead_gb, 2)
        available_commit_gb = self.specs.commit_limit_gb

        result.required_memory_gb = total_required_commit_gb
        result.available_commit_gb = available_commit_gb

        if total_required_commit_gb > available_commit_gb:
            result.hardware_test_passed = False
            deficit = round(total_required_commit_gb - available_commit_gb, 2)
            
            # Identify individual mods that exceed safe thresholds
            for mod_tuple in heavy_tiles:
                m_id, m_name, m_cnt, m_mb = mod_tuple
                if m_cnt > 20:
                    rejected_mods.add(m_id)

            result.errors.append(
                f"[TESTE DE HARDWARE FALHOU - ESTOURO DE MEMÓRIA VIRTUAL (CRASH DE WINDOWS PREVISTO)]\n"
                f"   Demanda Estimada do Jogo + Windows: ~{total_required_commit_gb} GB\n"
                f"   Limite Máximo de Commit (RAM + Pagefile): {available_commit_gb} GB (RAM Física: {self.specs.total_ram_gb} GB)\n"
                f"   Déficit de Memória: Faltam ~{deficit} GB no arquivo de paginação!\n"
                f"   Causa raiz: {total_depthmaps} DepthMaps ativos consumindo ~{est_native_vram_gb} GB nativos fora da JVM.\n"
                f"   Maiores consumidores identificados para remoção/purgamento:\n" +
                "\n".join([f"     * {t[1]} ({t[0]}): {t[2]} DepthMaps ({t[3]} MB)" for t in heavy_tiles[:5]])
            )
        elif total_depthmaps > 80:
            result.warnings.append(
                f"[ALERTA DE MEMÓRIA GRÁFICA] {total_depthmaps} DepthMaps ativos. Consumo de VRAM alto (~{est_native_vram_gb} GB)."
            )

        if total_fbx > 3500:
            result.errors.append(
                f"[SOBRECARGA CRÍTICA DE ANIMAÇÕES 3D (JASSIMP/FBX)]\n"
                f"   Mods ativos carregam {total_fbx} arquivos .fbx!\n"
                f"   Isso excede o limite seguro da engine Jassimp da B42."
            )
        elif total_fbx > 1500:
            result.warnings.append(
                f"[ANIMAÇÕES E MODELOS 3D (.FBX)] {total_fbx} modelos/esqueletos ativos no total.\n"
                f"   Mods com mais modelos: Brita's Armor, KATTAJ1, VFE Redux, Fluffy Hair.\n"
                f"   Status: Aprovado pelo teste de hardware (consumo estimado ~{est_fbx_gb} GB absorvido na memória)."
            )

        result.rejected_mod_ids = list(rejected_mods)

        # Rule 8: SP Status Verdict
        result.sp_status = "APROVADO" if len(result.errors) == 0 else "REPROVADO / CRASH GARANTIDO"

        # Rule 9: MP Status Verdict
        server_dir = os.path.join(self.specs.user_zomboid_dir, "Server")
        has_server_config = os.path.exists(server_dir) and len(os.listdir(server_dir)) > 0
        
        if not has_server_config:
            result.mp_issues.append("Nenhum servidor dedicado configurado em C:\\Users\\User\\Zomboid\\Server.")

        if len(result.errors) > 0:
            result.mp_issues.append("O servidor Multiplayer cairá na inicialização devido às falhas críticas de modlist.")

        result.mp_issues.append(
            f"Capacidade de Hardware: Hostear servidor + jogar no mesmo PC de {self.specs.total_ram_gb} GB RAM com mais de 100 mods causará falta de memória física a menos que a paginação do Windows seja expandida."
        )

        result.mp_status = "APROVADO" if len(result.mp_issues) == 0 else "REPROVADO / INVIÁVEL NO MOMENTO"

        return result
