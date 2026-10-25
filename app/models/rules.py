import os
from typing import List, Dict, Set
from .mod import Mod
from .mod_list import ModList
from .workshop import Workshop
from .system_specs import SystemSpecs
from .audit_result import AuditResult
from .log_inspector import LogInspector

class RulesEngine:
    """CI/CD Rules Engine: Validates mod integrity, conflicts, assets, 3D animations, and memory limits."""

    def __init__(self, specs: SystemSpecs):
        self.specs = specs

    @staticmethod
    def compute_recommended_load_order(active_mod_ids: List[str], workshop: Workshop) -> List[str]:
        """Calculates topological load order so prerequisite frameworks/libraries load before dependents."""
        active_set = set(active_mod_ids)
        # Build adjacency graph: prerequisite -> set of dependents
        graph: Dict[str, Set[str]] = {mid: set() for mid in active_mod_ids}
        in_degree: Dict[str, int] = {mid: 0 for mid in active_mod_ids}

        for mid in active_mod_ids:
            mod = workshop.get_mod(mid)
            if not mod:
                continue
            for req in mod.require:
                clean_req = req.lstrip(r"\/").strip()
                if clean_req in active_set and clean_req != mid:
                    # clean_req must precede mid
                    graph[clean_req].add(mid)
                    in_degree[mid] += 1

        # Kahn's algorithm
        queue = [mid for mid in active_mod_ids if in_degree[mid] == 0]
        ordered: List[str] = []

        while queue:
            node = queue.pop(0)
            ordered.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Fallback if circular dependency: append any remaining
        for mid in active_mod_ids:
            if mid not in ordered:
                ordered.append(mid)

        return ordered

    def evaluate(self, active_mod_ids: List[str], workshop: Workshop) -> AuditResult:
        result = AuditResult(
            total_active_mods=len(active_mod_ids),
            total_workshop_mods=len(workshop.mods)
        )

        active_set = set(active_mod_ids)
        rejected_mods: Set[str] = set()

        # Rule 1: Known incompatible B41 animation ports that crash Jassimp in B42
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

        # Rule 2: VFE legacy vs Redux B42 (Handled gracefully by PZ Java registry try/catch)
        vfe_legacy = [m for m in active_mod_ids if m in ["VFExpansion1", "VFExpansion2", "VFExpansion3"]]
        vfe_redux = [m for m in active_mod_ids if "VFExpansionRedux" in m or "Reduxb42" in m]
        if vfe_legacy and vfe_redux:
            result.warnings.append(
                f"[AVISO DE SOBREPOSIÇÃO - VFE DUPLICADO]\n"
                f"   Versões legadas ativas: {vfe_legacy}\n"
                f"   Versões Redux B42 ativas: {vfe_redux}\n"
                f"   Diagnóstico: O carregador Java do PZ absorve registros duplicados de munição via try/catch sem derrubar o jogo, "
                f"mas recomenda-se manter apenas o Redux para evitar duplicidade de itens no spawn."
            )

        # Rule 3: Multiple CraftEngineParts variants (Handled by PZ VFS file overrides)
        cep_variants = [m for m in active_mod_ids if m.startswith("CraftEngineParts")]
        if len(cep_variants) > 1:
            result.warnings.append(
                f"[AVISO DE SOBRESCRITA VFS - CraftEngineParts]\n"
                f"   Você ativou {len(cep_variants)} variantes: {cep_variants}\n"
                f"   Diagnóstico: O sistema de arquivos virtual (VFS) do PZ não crasha com variantes múltiplas; "
                f"a última variante na ordem de carregamento sobrescreve as tabelas de receitas e drop."
            )

        # Rule 4: Duplicate LightOnBelt
        if "LightOnBelt" in active_set and "FixedLightOnBeltAF" in active_set:
            rejected_mods.add("LightOnBelt")
            result.warnings.append(
                "[MODS DUPLICADOS] 'LightOnBelt' e 'FixedLightOnBeltAF' estão ativos simultaneamente. Mantenha apenas o Fixed."
            )

        # Rule 5: Native incompatible= check and missing dependencies check
        for mod_id in active_mod_ids:
            mod = workshop.get_mod(mod_id)
            if not mod:
                continue

            # Check native incompatible tags
            for inc in mod.incompatible:
                clean_inc = inc.lstrip(r"\/").strip()
                if clean_inc in active_set and clean_inc != mod_id:
                    result.errors.append(
                        f"[CONFLITO DECLARADO (incompatible=)] Mod '{mod_id}' declara incompatibilidade direta com '{clean_inc}'."
                    )

            # Check require tags
            for req in mod.require:
                clean_req = req.lstrip(r"\/").strip()
                if clean_req not in active_set:
                    # Check if requirement is a Workshop ID rather than Mod ID
                    is_ws_match = any(
                        workshop.get_mod(m) and workshop.get_mod(m).workshop_id == clean_req
                        for m in active_mod_ids
                    )
                    if not is_ws_match:
                        result.warnings.append(f"[DEPENDÊNCIA AUSENTE] Mod '{mod_id}' requer '{clean_req}', que não está ativo.")

        # Rule 6: Check Load Order (Topological sequence)
        recommended_order = self.compute_recommended_load_order(active_mod_ids, workshop)
        order_mismatches = []
        for i, mid in enumerate(active_mod_ids):
            mod = workshop.get_mod(mid)
            if not mod:
                continue
            for req in mod.require:
                clean_req = req.lstrip(r"\/").strip()
                if clean_req in active_set and clean_req in active_mod_ids:
                    req_index = active_mod_ids.index(clean_req)
                    if req_index > i:
                        order_mismatches.append(f"'{clean_req}' (dependência) está posicionado APÓS '{mid}'")

        if order_mismatches:
            result.warnings.append(
                f"[ORDEM DE CARREGAMENTO SUBLÓTIMA] Detectadas {len(order_mismatches)} inconsistências de ordem:\n"
                + "\n".join([f"     * {om}" for om in order_mismatches[:4]])
                + "\n     Dica: Frameworks e packs de tiles devem ser carregados antes dos mods que os exigem."
            )

        # Rule 7: Asset, Depthmaps and 3D FBX Animation Memory Budget
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

        # Realistic VRAM calculation: decompression ratio on disk vs texture memory
        # Depth maps in B42 are 8/16-bit heightmaps; multiply actual disk size by decompression factor (~4x), capped per map
        est_native_vram_gb = round(max((total_depthmap_mb * 4.0) / 1024, (total_depthmaps * 6) / 1024), 2)
        est_fbx_gb = round((total_fbx * 0.5) / 1024, 2)

        result.total_depthmaps = total_depthmaps
        result.total_depthmap_mb = round(total_depthmap_mb, 2)
        result.est_native_vram_gb = est_native_vram_gb
        result.total_fbx_animations = total_fbx
        result.heavy_tiles = heavy_tiles
        result.heavy_anim_mods = heavy_anims

        # Rule 8: HARDWARE CAPACITY PREDICTIVE TEST
        java_heap_gb = 4.0
        windows_overhead_gb = 4.5
        total_required_commit_gb = round(java_heap_gb + est_native_vram_gb + est_fbx_gb + windows_overhead_gb, 2)
        available_commit_gb = self.specs.commit_limit_gb

        result.required_memory_gb = total_required_commit_gb
        result.available_commit_gb = available_commit_gb

        if total_required_commit_gb > available_commit_gb:
            result.hardware_test_passed = False
            deficit = round(total_required_commit_gb - available_commit_gb, 2)

            # Identify candidates for rejection, but PROTECT tilepacks needed by active maps!
            for mod_tuple in heavy_tiles:
                m_id, m_name, m_cnt, m_mb = mod_tuple
                if m_cnt > 20:
                    # Check if any active mod requires this tile pack
                    dependents = [
                        m for m in active_mod_ids
                        if workshop.get_mod(m) and m_id in workshop.get_mod(m).require
                    ]
                    if not dependents:
                        rejected_mods.add(m_id)
                    else:
                        result.warnings.append(
                            f"[TILEPACK PESADO PROTEGIDO] '{m_name}' ({m_id}) consome {m_mb} MB mas é exigido por: {dependents}."
                        )

            result.errors.append(
                f"[TESTE DE HARDWARE FALHOU - ESTOURO DE MEMÓRIA VIRTUAL (CRASH DE WINDOWS PREVISTO)]\n"
                f"   Demanda Estimada do Jogo + Windows: ~{total_required_commit_gb} GB\n"
                f"   Limite Máximo de Commit (RAM + Pagefile): {available_commit_gb} GB (RAM Física: {self.specs.total_ram_gb} GB)\n"
                f"   Déficit de Memória: Faltam ~{deficit} GB no arquivo de paginação!\n"
                f"   Causa raiz: {total_depthmaps} DepthMaps ativos consumindo ~{est_native_vram_gb} GB em memória gráfica/nativa.\n"
                f"   Maiores consumidores identificados:\n" +
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

        # Rule 9: SP Status Verdict (Grounded in Real Game Runtime Logs with Per-Mod Execution Verification)
        log_res = LogInspector.inspect(self.specs.user_zomboid_dir)
        result.log_verified = log_res.has_logs
        result.log_diagnostic = log_res.diagnostic_summary
        result.log_detailed_diagnostics = log_res.detailed_diagnostics
        result.mods_vfs_loaded = log_res.total_vfs_loaded
        result.mods_lua_confirmed = log_res.total_lua_confirmed
        result.mods_silent = log_res.total_silent_mods
        result.mods_without_lua = log_res.mods_without_lua_execution[:20]

        if log_res.has_logs and log_res.boot_successful:
            result.log_status = "SUCESSO (Arranque e sessão confirmados em console.txt)"

            if log_res.fatal_crash and not log_res.clean_exit:
                result.errors.append(f"[CRASH REAL REGISTRADO EM LOG] {log_res.crash_reason}")
                result.sp_status = "REPROVADO / CRASH DETECTADO EM LOG"
            elif len(result.errors) == 0:
                result.sp_status = "APROVADO (Confirmado pelo Log do Jogo)"
                lua_ratio = f"{log_res.total_lua_confirmed}/{log_res.total_vfs_loaded}"
                result.warnings.append(
                    f"[EVIDÊNCIA DE LOG] {log_res.diagnostic_summary}\n"
                    f"   Mods com execução Lua confirmada: {lua_ratio}"
                )
            else:
                result.sp_status = "REPROVADO / FALHAS CRÍTICAS PENDENTES"

            # Add detailed per-mod runtime diagnostics as warnings
            for diag in log_res.detailed_diagnostics:
                result.warnings.append(diag)

            # Report script/recipe errors from logs
            if log_res.script_errors:
                result.warnings.append(
                    f"[ERROS DE RECEITA/SCRIPT NO LOG] {len(log_res.script_errors)} erro(s) detectados. "
                    f"Itens ou receitas afetadas podem não funcionar no jogo."
                )

        elif log_res.fatal_crash:
            result.log_status = f"CRASH REGISTRADO ({log_res.crash_reason})"
            result.errors.append(f"[CRASH REAL REGISTRADO EM LOG] {log_res.crash_reason}")
            result.sp_status = "REPROVADO / CRASH DETECTADO EM LOG"
        else:
            result.log_status = "SEM LOG RECENTE DE EXECUÇÃO"
            result.sp_status = "APROVADO" if len(result.errors) == 0 else "REPROVADO / CRASH GARANTIDO"

        # Rule 10: MP Status Verdict
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
