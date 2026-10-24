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
        # Always include known hard crashers
        to_remove.update({"amclub", "autotsartrailers", "tsarslib", "melos_tiles_for_miles_pack", "simonMDsTiles"})

        if not to_remove:
            TerminalView.show_message("Nenhum mod reprovado encontrado na modlist ativa.")
            return 0

        TerminalView.show_step(f"Removendo {len(to_remove)} mods reprovados da lista ativa...")
        for mid in to_remove:
            TerminalView.show_error(f"Mod Reprovado: {mid}")

        removed_count = self.mod_list.remove_mods(to_remove)
        TerminalView.show_message(f"Higienização concluída: {removed_count} mods removidos de default.txt.")

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

    def sanitize(self, isolate_heavy_tiles: bool = True, isolate_broken_anim_ports: bool = True) -> int:
        """Removes conflicting, corrupt, and memory-exploding entries from default.txt."""
        return self.purge_rejected_mods(delete_files=False)

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
            return True
        else:
            TerminalView.show_error(f"REPROVADO: Mod '{candidate_id}' quebrou o pipeline.")
            for err in result.errors:
                TerminalView.show_error(err)
            return False
