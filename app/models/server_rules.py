import os
from typing import List, Dict, Set, Tuple
from .mod import Mod
from .workshop import Workshop
from .system_specs import SystemSpecs
from .server_config import ServerConfig
from .server_audit_result import ServerAuditResult
from .build_validator import BuildValidator

class ServerRulesEngine:
    """Validates dedicated/coop server integrity, mod build/compilation, Steam Workshop sync, and hardware load."""

    # Mods que causam CRASH GARANTIDO no servidor (VERMELHO)
    CRASH_MODS = {
        "amclub": "Autotsar Motorclub possui esqueletos FBX incompatíveis com a B42 (bad allocation no Jassimp nativo).",
        "autotsartrailers": "Autotsar Trailers incompatível com a física do servidor B42.",
        "tsarslib": "Tsar's common library legado da Build 41."
    }

    def __init__(self, specs: SystemSpecs):
        self.specs = specs

    def evaluate(self, server_config: ServerConfig, workshop: Workshop) -> ServerAuditResult:
        active_server_mods = server_config.load_mods()
        configured_ws_items = set(server_config.load_workshop_items())
        configured_maps = set(server_config.load_maps())
        host_memory_mb = server_config.load_host_memory()

        result = ServerAuditResult(
            total_server_mods=len(active_server_mods),
            total_workshop_items=len(configured_ws_items),
            host_memory_mb=host_memory_mb,
            client_memory_gb=4.0,
            available_commit_gb=self.specs.commit_limit_gb
        )

        active_set = set(active_server_mods)
        rejected: List[Tuple[str, str, str]] = []  # (id, name, reason)

        # Track which mods are categorized to avoid double-counting
        categorized_ids: Set[str] = set()

        # ─── REGRA 1: Crashers Conhecidos → VERMELHO ───
        for bad_id, reason in self.CRASH_MODS.items():
            if bad_id in active_set:
                mod = workshop.get_mod(bad_id)
                name = mod.name if mod else bad_id
                rejected.append((bad_id, name, reason))
                result.red_mods.append((bad_id, name, f"🔴 CRASH GARANTIDO: {reason}"))
                result.errors.append(f"[MOD CRÍTICO REJEITADO NO SERVIDOR] {name} ({bad_id}): {reason}")
                categorized_ids.add(bad_id)

        # ─── REGRA 2: Conflitos Mutuamente Exclusivos e Incompatible Tags → VERMELHO ───
        vfe_legacy = [m for m in active_server_mods if m in ["VFExpansion1", "VFExpansion2", "VFExpansion3"]]
        vfe_redux = [m for m in active_server_mods if "VFExpansionRedux" in m or "Reduxb42" in m]
        if vfe_legacy and vfe_redux:
            for bad_m in vfe_legacy:
                mod = workshop.get_mod(bad_m)
                name = mod.name if mod else bad_m
                reason = "Versão legada de VFE em conflito com VFE Redux B42."
                rejected.append((bad_m, name, reason))
                if bad_m not in categorized_ids:
                    result.red_mods.append((bad_m, name, f"🔴 CONFLITO: {reason}"))
                    categorized_ids.add(bad_m)
            result.errors.append(f"[CONFLITO VFE NO SERVIDOR] Versões legadas ativas: {vfe_legacy}. Remova-as para manter apenas o Redux.")

        cep_variants = [m for m in active_server_mods if m.startswith("CraftEngineParts")]
        if len(cep_variants) > 1:
            for bad_m in cep_variants[1:]:
                mod = workshop.get_mod(bad_m)
                name = mod.name if mod else bad_m
                reason = "Múltiplas variantes conflitantes de CraftEngineParts."
                rejected.append((bad_m, name, reason))
                if bad_m not in categorized_ids:
                    result.red_mods.append((bad_m, name, f"🔴 CONFLITO: {reason}"))
                    categorized_ids.add(bad_m)
            result.errors.append(f"[CONFLITO NO SERVIDOR] Variantes duplicadas de CraftEngineParts: {cep_variants}.")

        # Check native incompatible tags on server mods
        for mid in active_server_mods:
            mod = workshop.get_mod(mid)
            if mod:
                for inc in mod.incompatible:
                    clean_inc = inc.lstrip(r"\/").strip()
                    if clean_inc in active_set and clean_inc != mid:
                        result.errors.append(
                            f"[CONFLITO NO SERVIDOR (incompatible=)] Mod '{mod.name}' ({mid}) declara conflito com '{clean_inc}'."
                        )

        # ─── REGRA 3: Sincronização Workshop IDs → AMARELO ───
        missing_mappings = []
        for mid in active_server_mods:
            mod = workshop.get_mod(mid)
            if mod and mod.workshop_id:
                if mod.workshop_id not in configured_ws_items:
                    missing_mappings.append(f"{mod.name} ({mid}) -> Workshop ID: {mod.workshop_id}")
                    if mid not in categorized_ids:
                        result.yellow_mods.append((mid, mod.name, f"🟡 Workshop ID ausente no servertest.ini (não será baixado por outros jogadores)."))

        result.missing_workshop_mappings = missing_mappings
        if missing_mappings:
            result.errors.append(
                f"[SINCRONIZAÇÃO WORKSHOP INCOMPLETA NO SERVIDOR]\n"
                f"   Existem {len(missing_mappings)} mods ativos sem seus IDs da Oficina na linha 'WorkshopItems='!\n"
                f"   O servidor não conseguirá carregar esses mods e abortará com NormalTermination."
            )

        # ─── REGRA 3.5: Sincronização de Mapas (Map=) → AMARELO ───
        missing_maps = []
        for mid in active_server_mods:
            mod = workshop.get_mod(mid)
            if mod and mod.map_folders:
                for mf in mod.map_folders:
                    if mf not in configured_maps:
                        missing_maps.append(f"{mod.name} ({mid}) -> Pasta de Mapa: {mf}")
                        if mid not in categorized_ids:
                            result.yellow_mods.append((mid, mod.name, f"🟡 Pasta de mapa '{mf}' ausente na linha Map= do servertest.ini."))

        result.missing_map_mappings = missing_maps
        if missing_maps:
            result.warnings.append(
                f"[SINCRONIZAÇÃO DE MAPAS PENDENTE NO SERVIDOR]\n"
                f"   Detectadas {len(missing_maps)} pastas de mapa não incluídas na linha 'Map=' do servertest.ini:\n"
                + "\n".join([f"     * {mm}" for mm in missing_maps])
                + "\n   Execute a sincronização do servidor para adicioná-las antes de 'Muldraugh, KY'."
            )

        # ─── REGRA 4: Compilação e Build de Cada Mod ───
        total_depthmaps = 0
        total_depthmap_mb = 0.0

        for mid in active_server_mods:
            mod = workshop.get_mod(mid)
            if not mod:
                result.warnings.append(f"[MOD NÃO ENCONTRADO NO DISCO] '{mid}' está no servertest.ini mas não foi encontrado na pasta da Oficina.")
                if mid not in categorized_ids:
                    result.yellow_mods.append((mid, mid, "🟡 Mod não encontrado no disco local (pode estar faltando)."))
                    categorized_ids.add(mid)
                continue

            total_depthmaps += mod.depthmap_count
            total_depthmap_mb += mod.depthmap_size_mb

            # Compile/syntax check
            build_errors = BuildValidator.compile_check_mod(mod)
            if build_errors:
                result.build_failures.append((mod.id, mod.name, build_errors))

                # Classificar severidade do erro de compilação
                has_critical = any(
                    keyword in err.lower()
                    for err in build_errors
                    for keyword in ["desbalanceamento", "bytes nulos", "unexpected symbol", "syntax error", "eof", "malformed"]
                )

                if has_critical:
                    # VERMELHO: erro que impede o servidor de carregar o mod
                    if mid not in categorized_ids:
                        result.red_mods.append((mod.id, mod.name, f"🔴 FALHA DE COMPILAÇÃO: {build_errors[0]}"))
                        categorized_ids.add(mid)
                    rejected.append((mod.id, mod.name, f"Falha de compilação crítica: {build_errors[0]}"))
                else:
                    # AMARELO: alerta de build, pode funcionar mas é suspeito
                    if mid not in categorized_ids:
                        result.yellow_mods.append((mod.id, mod.name, f"🟡 ALERTA DE BUILD: {build_errors[0]}"))
                        categorized_ids.add(mid)

        if result.build_failures:
            for b_id, b_name, b_errs in result.build_failures:
                result.errors.append(f"[FALHA DE BUILD/COMPILAÇÃO] {b_name} ({b_id}):\n" + "\n".join([f"     * {e}" for e in b_errs[:3]]))

        # ─── REGRA 5: Teste de Capacidade de Hardware (Headless vs Co-op) ───
        client_mem_gb = 4.0
        server_mem_gb = round(host_memory_mb / 1024, 2)
        windows_gb = 4.5
        client_vram_gb = round(max((total_depthmap_mb * 4.0) / 1024, (total_depthmaps * 6) / 1024), 2)

        # Dedicated headless server only consumes server_mem_gb;
        # Co-op host playing on same PC consumes client + server + windows + GPU textures
        total_req_gb = round(client_mem_gb + server_mem_gb + windows_gb + client_vram_gb, 2)
        result.total_required_commit_gb = total_req_gb

        if total_req_gb > self.specs.commit_limit_gb:
            result.hardware_test_passed = False
            diff = round(total_req_gb - self.specs.commit_limit_gb, 2)
            result.errors.append(
                f"[TESTE DE HARDWARE DO SERVIDOR REPROVADO - ESTOURO DE MEMÓRIA VIRTUAL]\n"
                f"   Demanda Estimada (Cliente {client_mem_gb}GB + Servidor {server_mem_gb}GB + Texturas VRAM {client_vram_gb}GB + Windows {windows_gb}GB): {total_req_gb} GB\n"
                f"   Limite Real de Commit do PC: {self.specs.commit_limit_gb} GB\n"
                f"   Déficit: Faltam ~{diff} GB de memória virtual! Reduza a memória do servidor para 2048 MB ou aumente o arquivo de paginação do Windows."
            )

        # ─── REGRA 6: Classificar Mods Aprovados (VERDE) ───
        for mid in active_server_mods:
            if mid not in categorized_ids:
                mod = workshop.get_mod(mid)
                name = mod.name if mod else mid
                result.green_mods.append((mid, name))
                categorized_ids.add(mid)

        result.rejected_mod_ids = rejected
        result.server_status = "APROVADO" if result.is_green else "REPROVADO / CRASH GARANTIDO"

        return result
