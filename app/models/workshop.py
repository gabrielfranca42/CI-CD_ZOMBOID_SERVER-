import os
from typing import Dict, Optional
from .mod import Mod

class Workshop:
    def __init__(self, workshop_dir: str):
        self.workshop_dir = workshop_dir
        self.mods: Dict[str, Mod] = {}

    def scan(self) -> Dict[str, Mod]:
        """Indexes all mods installed in the Steam Workshop directory with Build 42 version priority."""
        self.mods.clear()
        if not os.path.exists(self.workshop_dir):
            return self.mods

        # Priority weights: 42 > common > legacy
        priority_map = {"42": 3, "common": 2, "legacy": 1}
        mod_priorities: Dict[str, int] = {}

        for ws_id in os.listdir(self.workshop_dir):
            ws_path = os.path.join(self.workshop_dir, ws_id)
            if not os.path.isdir(ws_path):
                continue

            for root, dirs, files in os.walk(ws_path):
                if "mod.info" in files:
                    mod_info_path = os.path.join(root, "mod.info")
                    mod = Mod.from_mod_info(mod_info_path, workshop_id=ws_id)
                    if mod and mod.id:
                        prio = priority_map.get(mod.target_version, 1)
                        # Overwrite if higher priority or first encounter
                        if mod.id not in self.mods or prio >= mod_priorities.get(mod.id, 0):
                            self.mods[mod.id] = mod
                            mod_priorities[mod.id] = prio

        return self.mods

    def get_mod(self, mod_id: str) -> Optional[Mod]:
        return self.mods.get(mod_id)
