import os
from typing import Dict
from .mod import Mod

class Workshop:
    def __init__(self, workshop_dir: str):
        self.workshop_dir = workshop_dir
        self.mods: Dict[str, Mod] = {}

    def scan(self) -> Dict[str, Mod]:
        """Indexes all mods installed in the Steam Workshop directory."""
        self.mods.clear()
        if not os.path.exists(self.workshop_dir):
            return self.mods

        for ws_id in os.listdir(self.workshop_dir):
            ws_path = os.path.join(self.workshop_dir, ws_id)
            if not os.path.isdir(ws_path):
                continue

            for root, dirs, files in os.walk(ws_path):
                if "mod.info" in files:
                    mod_info_path = os.path.join(root, "mod.info")
                    mod = Mod.from_mod_info(mod_info_path, workshop_id=ws_id)
                    if mod and mod.id:
                        self.mods[mod.id] = mod

        return self.mods

    def get_mod(self, mod_id: str) -> Mod:
        return self.mods.get(mod_id)
