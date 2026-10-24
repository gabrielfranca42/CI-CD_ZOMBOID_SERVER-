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

        # Save to server.ini
        self.server_config.save_server_mods(sanitized_mods, synced_ws_items)

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
        print(f"  Memória do Servidor:         {target_memory_mb} MB")

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
