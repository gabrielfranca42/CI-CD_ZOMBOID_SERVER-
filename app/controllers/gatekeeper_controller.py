import os
from typing import Set
from app.models.system_specs import SystemSpecs
from app.models.workshop import Workshop
from app.models.mod_list import ModList
from app.models.rules import RulesEngine
from app.views.terminal_view import TerminalView

class GatekeeperController:
    """Manages mod admission, sanitization, and quality gate enforcement."""

    def __init__(self):
        self.specs = SystemSpecs.detect()
        default_txt_path = os.path.join(self.specs.user_zomboid_dir, "mods", "default.txt")
        self.mod_list = ModList(default_txt_path)
        self.workshop = Workshop(self.specs.workshop_dir)
        self.rules_engine = RulesEngine(self.specs)

    def purge_rejected_mods(self, delete_files: bool = False) -> int:
        """Dynamically audits active mods and removes all rejected mods from default.txt and optionally from disk."""
        TerminalView.show_step("Executando auditoria dinâmica de admissão e teste de hardware...")
        self.workshop.scan()
        active = self.mod_list.load()
        result = self.rules_engine.evaluate(active, self.workshop)

        to_remove = set(result.rejected_mod_ids)
        # Always include known hard crashers on B42
        to_remove.update({"amclub", "autotsartrailers", "tsarslib"})

        # Never remove tile packs if active maps depend on them
        active_remaining = [m for m in active if m not in to_remove]
        for mid in list(to_remove):
            dependents = [
                m for m in active_remaining
                if self.workshop.get_mod(m) and mid in self.workshop.get_mod(m).require
            ]
            if dependents:
                TerminalView.show_message(f"Preservando mod '{mid}' pois é dependência de: {dependents}")
                to_remove.remove(mid)

        if not to_remove:
            TerminalView.show_message("Nenhum mod reprovado encontrado na modlist ativa.")
            # Optimize load order even if nothing removed
            ordered = RulesEngine.compute_recommended_load_order(active, self.workshop)
            if ordered != active:
                self.mod_list.save_ordered_mods(ordered)
                TerminalView.show_message("Ordem de carregamento otimizada (frameworks e bibliotecas no topo).")
            return 0

        TerminalView.show_step(f"Removendo {len(to_remove)} mods reprovados da lista ativa...")
        for mid in to_remove:
            TerminalView.show_error(f"Mod Reprovado: {mid}")

        removed_count = self.mod_list.remove_mods(to_remove)
        TerminalView.show_message(f"Higienização concluída: {removed_count} mods removidos de default.txt.")

        # Optimize load order of remaining mods
        remaining = self.mod_list.load()
        ordered = RulesEngine.compute_recommended_load_order(remaining, self.workshop)
        if ordered != remaining:
            self.mod_list.save_ordered_mods(ordered)
            TerminalView.show_message("Ordem de carregamento otimizada com sucesso.")

        if delete_files:
            import shutil
            TerminalView.show_step("Apagando fisicamente os arquivos dos mods reprovados do disco...")
            for mid in to_remove:
                mod = self.workshop.get_mod(mid)
                if mod and mod.mod_folder and os.path.exists(mod.mod_folder):
                    try:
                        # If workshop mod, target workshop item folder if it belongs exclusively
                        ws_item_path = os.path.join(self.specs.workshop_dir, mod.workshop_id) if mod.workshop_id else mod.mod_folder
                        if os.path.exists(ws_item_path):
                            shutil.rmtree(ws_item_path, ignore_errors=True)
                            TerminalView.show_message(f"DELETADO DO DISCO: {ws_item_path} ({mid})")
                        else:
                            shutil.rmtree(mod.mod_folder, ignore_errors=True)
                            TerminalView.show_message(f"DELETADO DO DISCO: {mod.mod_folder} ({mid})")
                    except Exception as e:
                        TerminalView.show_error(f"Falha ao apagar arquivos de {mid}: {e}")

        return removed_count

    def remove_mod_by_id(self, mod_id: str, delete_files: bool = False) -> bool:
        """Removes a specific mod by ID from default.txt, reorders remaining, and optionally deletes from disk."""
        active = self.mod_list.load()
        if mod_id not in active:
            TerminalView.show_message(f"Mod '{mod_id}' não está ativo no Singleplayer.")
            return False

        self.workshop.scan()
        dependents = [
            m for m in active if m != mod_id and self.workshop.get_mod(m) and mod_id in self.workshop.get_mod(m).require
        ]
        if dependents:
            TerminalView.show_message(f"AVISO: Os seguintes mods ativos dependem de '{mod_id}': {dependents}")

        self.mod_list.remove_mods({mod_id})
        TerminalView.show_message(f"Mod '{mod_id}' removido com sucesso de default.txt.")

        # Reorder remaining mods
        remaining = self.mod_list.load()
        ordered = RulesEngine.compute_recommended_load_order(remaining, self.workshop)
        if ordered != remaining:
            self.mod_list.save_ordered_mods(ordered)
            TerminalView.show_message("Ordem de carregamento reajustada automaticamente.")

        if delete_files:
            mod = self.workshop.get_mod(mod_id)
            if mod and mod.mod_folder and os.path.exists(mod.mod_folder):
                import shutil
                target = os.path.join(self.specs.workshop_dir, mod.workshop_id) if mod.workshop_id else mod.mod_folder
                try:
                    shutil.rmtree(target, ignore_errors=True)
                    TerminalView.show_message(f"DELETADO DO DISCO: {target}")
                except Exception as e:
                    TerminalView.show_error(f"Falha ao apagar arquivos de {mod_id}: {e}")

        return True

    def sanitize(self, isolate_heavy_tiles: bool = True, isolate_broken_anim_ports: bool = True,
                 level: str = "red", delete_files: bool = False) -> int:
        """Removes conflicting, corrupt, and memory-exploding entries from default.txt."""
        return self.purge_rejected_mods(delete_files=delete_files)

    def admit_candidate_mod(self, candidate_id: str) -> bool:
        """Evaluates if a new mod can be admitted into the active mod list."""
        self.workshop.scan()
        active = self.mod_list.load()

        if candidate_id in active:
            TerminalView.show_message(f"Mod '{candidate_id}' já está ativo na lista.")
            return True

        TerminalView.show_step(f"Testando admissão do mod '{candidate_id}'...")
        simulated_active = active + [candidate_id]
        result = self.rules_engine.evaluate(simulated_active, self.workshop)

        if result.is_green:
            TerminalView.show_message(f"APROVADO: Mod '{candidate_id}' passou em todos os testes.")
            # Add to default.txt in optimal order
            new_active = active + [candidate_id]
            ordered = RulesEngine.compute_recommended_load_order(new_active, self.workshop)
            self.mod_list.save_ordered_mods(ordered)
            TerminalView.show_message(f"Mod '{candidate_id}' adicionado e posicionado na ordem correta em default.txt.")
            return True
        else:
            TerminalView.show_error(f"REPROVADO: Mod '{candidate_id}' quebrou o pipeline.")
            for err in result.errors:
                TerminalView.show_error(err)
            return False

    def install_and_admit_mod(self, mod_or_req: str) -> bool:
        """Downloads a missing mod via SteamCMD and immediately validates it in real time before admission."""
        from app.models.steam_downloader import SteamDownloader
        user_mods = os.path.join(self.specs.user_zomboid_dir, "mods")
        TerminalView.show_step(f"Iniciando download e validação em tempo real de '{mod_or_req}' via SteamCMD...")
        success, mod_id, diags = SteamDownloader.install_and_validate(
            mod_or_req, self.workshop, self.specs.workshop_dir, user_mods_dir=user_mods
        )
        for d in diags:
            if "🔴" in d:
                TerminalView.show_error(d)
            elif "✅" in d:
                TerminalView.show_message(d)
            else:
                TerminalView.show_step(d)

        if not success:
            TerminalView.show_error(f"FALHA: Mod '{mod_or_req}' foi rejeitado ou não pôde ser instalado.")
            return False

        return self.admit_candidate_mod(mod_id)

    def reorder_mods(self) -> bool:
        """Automatically optimizes load order so frameworks and libraries are loaded before dependent mods."""
        self.workshop.scan()
        active = self.mod_list.load()
        ordered = RulesEngine.compute_recommended_load_order(active, self.workshop)
        if ordered != active:
            self.mod_list.save_ordered_mods(ordered)
            TerminalView.show_message("✅ SUCESSO: Ordem de carregamento reordenada e salva em default.txt.")
            return True
        else:
            TerminalView.show_message("A modlist já está na ordem topológica ideal.")
            return False

