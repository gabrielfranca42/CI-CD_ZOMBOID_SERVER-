import os
from typing import Set, List
from app.models.system_specs import SystemSpecs
from app.models.workshop import Workshop
from app.models.server_config import ServerConfig
from app.models.server_rules import ServerRulesEngine
from app.models.server_audit_result import ServerAuditResult
from app.models.build_validator import BuildValidator
from app.views.server_terminal_view import ServerTerminalView
from app.views.terminal_view import TerminalView

class ServerController:
    """Manages Multiplayer Server CI/CD Pipeline, build verification, and mod admission."""

    def __init__(self, server_name: str = "servertest"):
        self.specs = SystemSpecs.detect()
        self.workshop = Workshop(self.specs.workshop_dir)
        self.server_config = ServerConfig.default(self.specs.user_zomboid_dir, server_name=server_name)
        self.rules_engine = ServerRulesEngine(self.specs)

    def audit_server(self) -> ServerAuditResult:
        """Executes full server build verification, conflict check, and hardware capacity testing."""
        TerminalView.show_step("Detectando configurações do servidor e hardware...")
        TerminalView.show_step("Indexando mods da Oficina Steam...")
        self.workshop.scan()

        TerminalView.show_step(f"Carregando configurações do servidor ({self.server_config.server_ini_path})...")
        TerminalView.show_step("Executando testes de compilação, sintaxe Lua e regras do servidor...")
        result = self.rules_engine.evaluate(self.server_config, self.workshop)

        ServerTerminalView.show_report(self.specs, result)
        
        # Failure Logs (.txt individual per broken mod)
        from app.views.failure_log_view import FailureLogGenerator
        logs_dir = os.path.join(os.getcwd(), "failure_logs")
        generated_logs = FailureLogGenerator.generate_mp_logs(result, logs_dir)
        if generated_logs:
            TerminalView.show_message(f"Logs de falha individuais (.txt) gerados em: {logs_dir} ({len(generated_logs)} arquivo(s))")

        return result

    def sanitize_and_sync_server(self, target_memory_mb: int = 2048, level: str = "red") -> int:
        """Removes server mods by severity level, syncs Steam Workshop IDs, and tunes host memory.

        Args:
            target_memory_mb: Target server memory allocation in MB.
            level: Sanitization level.
                   'red'    → Remove only RED mods (crash/compilation failures).
                   'yellow' → Remove RED + YELLOW mods (crash + alerts).
                   'all'    → Same as 'yellow'.
        """
        TerminalView.show_step("Iniciando auditoria para saneamento do servidor...")
        self.workshop.scan()
        current_mods = self.server_config.load_mods()
        result = self.rules_engine.evaluate(self.server_config, self.workshop)

        # Build set of IDs to remove based on selected level
        to_remove = set()

        # Always remove RED mods (crash/grave)
        for mid, mname, reason in result.red_mods:
            to_remove.add(mid)

        red_count = len(to_remove)
        yellow_count = 0

        # Optionally also remove YELLOW mods (alerts)
        if level in ("yellow", "all"):
            for mid, mname, reason in result.yellow_mods:
                to_remove.add(mid)
            yellow_count = len(to_remove) - red_count

        sanitized_mods = [m for m in current_mods if m not in to_remove]
        removed_count = len(current_mods) - len(sanitized_mods)

        # Build synchronized WorkshopItems list
        synced_ws_items = []
        for mid in sanitized_mods:
            mod = self.workshop.get_mod(mid)
            if mod and mod.workshop_id:
                if mod.workshop_id not in synced_ws_items:
                    synced_ws_items.append(mod.workshop_id)

        # Build synchronized Map list
        current_configured_maps = self.server_config.load_maps()
        synced_maps = [m for m in current_configured_maps if m != "Muldraugh, KY"]
        for mid in sanitized_mods:
            mod = self.workshop.get_mod(mid)
            if mod and mod.map_folders:
                for mf in mod.map_folders:
                    if mf not in synced_maps:
                        synced_maps.append(mf)
        synced_maps.append("Muldraugh, KY")

        # Save to server.ini
        self.server_config.save_server_mods(sanitized_mods, synced_ws_items, maps=synced_maps)

        # Tune host memory
        self.server_config.set_host_memory(target_memory_mb)

        # Report
        print("\n" + "="*75)
        print("  RELATÓRIO DE HIGIENIZAÇÃO DO SERVIDOR")
        print("="*75)

        level_label = {
            "red": "Apenas VERMELHOS (graves/crash)",
            "yellow": "VERMELHOS + AMARELOS (graves + alertas)",
            "all": "VERMELHOS + AMARELOS (graves + alertas)"
        }.get(level, level)

        print(f"  Nível de Higienização: {level_label}")
        print(f"  🔴 Mods vermelhos removidos: {red_count}")
        if level in ("yellow", "all"):
            print(f"  🟡 Mods amarelos removidos:  {yellow_count}")
        print(f"  Total removidos:             {removed_count}")
        print(f"  Mods ativos restantes:       {len(sanitized_mods)}")
        print(f"  Workshop IDs sincronizados:  {len(synced_ws_items)}")
        print(f"  Mapas sincronizados:         {len(synced_maps)} ({', '.join(synced_maps)})")
        print(f"  Memória do Servidor (Host):  {target_memory_mb} MB")

        if to_remove:
            print(f"\n  Mods removidos:")
            for mid in to_remove:
                mod = self.workshop.get_mod(mid)
                name = mod.name if mod else mid
                # Show which category it was
                is_red = any(r[0] == mid for r in result.red_mods)
                color = "🔴" if is_red else "🟡"
                print(f"    {color} {name} ({mid})")

        print(f"\n  Arquivo atualizado: {self.server_config.server_ini_path}")
        print("="*75 + "\n")

        return removed_count

    def admit_candidate_mod_mp(self, candidate_id: str) -> bool:
        """Tests whether a new candidate mod compiles, builds, and fits server hardware budgets."""
        self.workshop.scan()
        mod = self.workshop.get_mod(candidate_id)

        if not mod:
            print("\n" + "="*70)
            print("❌ MOD REJEITADO PELA PIPELINE DO SERVIDOR:")
            print(f"   Nome: Desconhecido")
            print(f"   ID:   {candidate_id}")
            print(f"   Motivo da Reprovação: Mod não encontrado na Oficina Steam local.")
            print("="*70 + "\n")
            return False

        TerminalView.show_step(f"Iniciando verificação de build e compilação do mod '{mod.name}' ({mod.id})...")

        # Step 1: Compile and build check
        build_errors = BuildValidator.compile_check_mod(mod)
        if build_errors:
            # Classify severity
            has_critical = any(
                keyword in err.lower()
                for err in build_errors
                for keyword in ["unexpected symbol", "expected", "syntax error", "eof", "malformed", "module"]
            )

            severity = "🔴 VERMELHO (GRAVE)" if has_critical else "🟡 AMARELO (ALERTA)"

            print("\n" + "="*70)
            print(f"❌ MOD REJEITADO PELA PIPELINE DO SERVIDOR (FALHA DE COMPILAÇÃO):")
            print(f"   Nome:       {mod.name}")
            print(f"   ID:         {mod.id}")
            print(f"   Severidade: {severity}")
            print("   Erros de Compilação/Sintaxe Encontrados:")
            for err in build_errors:
                print(f"     - {err}")
            print("="*70 + "\n")
            return False

        # Step 2: Check server simulation
        current_mods = self.server_config.load_mods()
        if candidate_id in current_mods:
            TerminalView.show_message(f"O mod '{mod.name}' ({mod.id}) já está ativo no servidor.")
            return True

        TerminalView.show_step(f"Simulando admissão do mod '{mod.name}' no servidor...")
        simulated_mods = current_mods + [candidate_id]

        # Temporary simulation
        client_mem_gb = 4.0
        server_mem_gb = round(self.server_config.load_host_memory() / 1024, 2)
        windows_gb = 4.5
        est_depthmaps_gb = round((mod.depthmap_count * 16) / 1024, 2)

        total_req_gb = round(client_mem_gb + server_mem_gb + windows_gb + est_depthmaps_gb, 2)

        if total_req_gb > self.specs.commit_limit_gb:
            print("\n" + "="*70)
            print("❌ MOD REJEITADO PELA PIPELINE DO SERVIDOR (ESTOURO DE HARDWARE):")
            print(f"   Nome: {mod.name}")
            print(f"   ID:   {mod.id}")
            print(f"   Severidade: 🔴 VERMELHO (ESTOURO)")
            print(f"   Motivo da Reprovação: O mod demanda ~{est_depthmaps_gb} GB adicionais de VRAM/Texturas.")
            print(f"   Carga Total: {total_req_gb} GB excede o Limite de Commit de {self.specs.commit_limit_gb} GB da máquina.")
            print("="*70 + "\n")
            return False

        print("\n" + "="*70)
        print("✅ MOD APROVADO PELA PIPELINE DO SERVIDOR:")
        print(f"   Nome: {mod.name}")
        print(f"   ID:   {mod.id}")
        print(f"   Workshop ID: {mod.workshop_id or 'Local'}")
        print(f"   Classificação: 🟢 VERDE (APROVADO)")
        print(f"   Status de Compilação: Build verificado sem erros de sintaxe.")
        print(f"   Impacto de Hardware: Compatível com o servidor atual.")
        print("="*70 + "\n")
        return True

    def remove_mod_by_id(self, mod_id: str, delete_files: bool = False) -> bool:
        """Removes a specific mod by ID from servertest.ini (Mods, WorkshopItems, Map) and optionally from disk."""
        current_mods = self.server_config.load_mods()
        if mod_id not in current_mods:
            print(f"Mod '{mod_id}' não está ativo nas configurações do servidor.")
            return False

        sanitized_mods = [m for m in current_mods if m != mod_id]
        
        # Sync workshop items
        self.workshop.scan()
        synced_ws_items = []
        for mid in sanitized_mods:
            m = self.workshop.get_mod(mid)
            if m and m.workshop_id and m.workshop_id not in synced_ws_items:
                synced_ws_items.append(m.workshop_id)

        # Sync maps
        removed_mod = self.workshop.get_mod(mod_id)
        current_maps = self.server_config.load_maps()
        synced_maps = [m for m in current_maps if not (removed_mod and m in removed_mod.map_folders)]

        self.server_config.save_server_mods(sanitized_mods, synced_ws_items, maps=synced_maps)
        print(f"Mod '{mod_id}' removido com sucesso de {self.server_config.server_ini_path}.")

        if delete_files and removed_mod and removed_mod.mod_folder and os.path.exists(removed_mod.mod_folder):
            import shutil
            target = os.path.join(self.specs.workshop_dir, removed_mod.workshop_id) if removed_mod.workshop_id else removed_mod.mod_folder
            try:
                shutil.rmtree(target, ignore_errors=True)
                print(f"DELETADO DO DISCO: {target}")
            except Exception as e:
                print(f"Falha ao apagar arquivos de {mod_id}: {e}")

        return True

    def install_and_admit_mod_mp(self, mod_or_req: str) -> bool:
        """Downloads a mod via SteamCMD and performs build validation before admitting into the server."""
        from app.models.steam_downloader import SteamDownloader
        user_mods = os.path.join(self.specs.user_zomboid_dir, "mods")
        print(f"--> Iniciando download e validação em tempo real de '{mod_or_req}' via SteamCMD...")
        success, mod_id, diags = SteamDownloader.install_and_validate(
            mod_or_req, self.workshop, self.specs.workshop_dir, user_mods_dir=user_mods
        )
        for d in diags:
            print(f"  {d}")

        if not success:
            print(f"❌ FALHA: Mod '{mod_or_req}' foi rejeitado ou não pôde ser instalado no servidor.")
            return False

        return self.admit_candidate_mod_mp(mod_id)

    def sync_workshop_steamcmd(self) -> bool:
        """Pre-downloads and synchronizes all server WorkshopItems via SteamCMD to bypass Steam client runtime bugs."""
        from app.models.steam_downloader import SteamDownloader
        items = self.server_config.load_workshop_items()
        if not items:
            print("Nenhum Workshop ID configurado em servertest.ini.")
            return True

        print("\n" + "="*75)
        print("  SINCRONIZAÇÃO WORKSHOP PRÉ-BOOT VIA STEAMCMD (CI/CD)")
        print("="*75)
        print(f"  Total de itens da Workshop a sincronizar: {len(items)}")
        print(f"  Diretório de destino: {self.specs.workshop_dir}\n")

        user_mods_dir = os.path.join(self.specs.user_zomboid_dir, "mods")
        res = SteamDownloader.sync_workshop_items(
            items, self.specs.workshop_dir, auto_deploy=True, user_mods_dir=user_mods_dir
        )

        if "error" in res:
            print(f"❌ {res['error']}")
            return False

        print(f"  Já presentes no disco:       {len(res['already_present'])}")
        print(f"  Baixados com sucesso:        {len(res['success'])}")
        print(f"  Implantados em mods locais:  {len(res.get('deployed', []))}")
        if res['failed']:
            print(f"  🔴 Falharam no download ({len(res['failed'])}):")
            for fid, fmsg in res['failed']:
                print(f"     - Workshop ID {fid}: {fmsg}")
        else:
            print(f"  ✅ Todos os mods da Workshop estão sincronizados e implantados localmente!")

        print("\n" + "="*75 + "\n")
        return len(res['failed']) == 0

    def sync_from_json_manifest(self, copy_to_local_mods: bool = True, apply_zero_steam: bool = True) -> bool:
        """Loads data/server_mods_manifest.json and downloads/deploys all mods via SteamCMD, automatically activating Zero-Steam Boot."""
        from app.models.mod_manifest import ModManifestManager
        print("\n" + "="*75)
        print("  DOWNLOAD AUTOMATIZADO VIA MANIFESTO JSON (CI/CD)")
        print("="*75)
        
        # Ensure manifest is updated
        ModManifestManager.generate_or_update_from_server(self.server_config, self.workshop)
        manifest_file = ModManifestManager.get_manifest_path()
        print(f"  Manifesto JSON: {manifest_file}")
        
        user_mods_dir = os.path.join(self.specs.user_zomboid_dir, "mods")
        res = ModManifestManager.download_all_from_manifest(
            workshop_dir=self.specs.workshop_dir,
            copy_to_local_mods=copy_to_local_mods,
            user_zomboid_mods_dir=user_mods_dir
        )

        if "error" in res:
            print(f"❌ {res['error']}")
            return False

        print(f"  Total de mods no manifesto: {res['total']}")
        print(f"  Já presentes:                {len(res['already_present'])}")
        print(f"  Baixados com sucesso:        {len(res['downloaded'])}")
        if copy_to_local_mods:
            print(f"  Implantados em mods locais:  {user_mods_dir}")

        if res['failed']:
            print(f"  🔴 Falharam ({len(res['failed'])}):")
            for mid, wid, msg in res['failed']:
                print(f"     - Mod {mid} ({wid}): {msg}")
        else:
            print("  ✅ Todos os mods do manifesto foram baixados e implantados com sucesso!")

        if apply_zero_steam and len(res['failed']) == 0:
            self.apply_zero_steam_boot()

        print("="*75 + "\n")
        return len(res['failed']) == 0

    def deploy_all_mods_to_local(self, clean_workshop_items: bool = True) -> bool:
        """Deploys all workshop mods on disk directly into C:\\Users\\User\\Zomboid\\mods\\ and optionally clears WorkshopItems."""
        from app.models.mod_manifest import ModManifestManager
        user_mods_dir = os.path.join(self.specs.user_zomboid_dir, "mods")
        print("\n" + "="*75)
        print("  IMPLANTAÇÃO TOTAL DE MODS LOCAIS (ZERO-STEAM BOOT)")
        print("="*75)
        print(f"  Origem Workshop:   {self.specs.workshop_dir}")
        print(f"  Destino Mods:      {user_mods_dir}")

        res = ModManifestManager.deploy_all_workshop_to_local_mods(self.specs.workshop_dir, user_mods_dir)
        print(f"  Itens Workshop processados: {res['total_items']}")
        print(f"  Pastas de mods implantadas: {len(res['deployed_mods'])}")

        if clean_workshop_items:
            self.apply_zero_steam_boot()

        print("="*75 + "\n")
        return True

    def apply_zero_steam_boot(self) -> bool:
        """Applies Zero-Steam Boot: retains all 133 mods in Mods= and empties WorkshopItems= to prevent in-game Steam download hangs."""
        mods_count, prev_ws = self.server_config.apply_zero_steam_boot()
        print("\n" + "-"*70)
        print("  🚀 ZERO-STEAM BOOT ATIVADO AUTOMATICAMENTE (CI/CD):")
        print(f"     * Mods mantidos e ativos em 'Mods=':          {mods_count}")
        print(f"     * Workshop IDs limpos de 'WorkshopItems=':    {prev_ws} -> 0")
        print("     * O servidor agora carrega 100% via disco local sem passar pela Steam!")
        print("     * Nunca mais trava em contagens ('Descarregado: X de 117').")
        print("-"*70)
        return True

