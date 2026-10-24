import os
import re
import shutil
from typing import List, Set

class ModList:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.active_mod_ids: List[str] = []

    def load(self) -> List[str]:
        """Loads and parses active mod IDs from default.txt or mods.txt."""
        self.active_mod_ids = []
        if not os.path.exists(self.file_path):
            return self.active_mod_ids

        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = re.search(r'mod\s*=\s*([^,;\r\n]+)', line)
                if m:
                    mod_id = m.group(1).strip()
                    if mod_id and mod_id not in self.active_mod_ids:
                        self.active_mod_ids.append(mod_id)

        return self.active_mod_ids

    def backup(self) -> str:
        """Creates a .bak backup of the mod list."""
        if not os.path.exists(self.file_path):
            return ""
        backup_path = self.file_path + ".bak"
        shutil.copy2(self.file_path, backup_path)
        return backup_path

    def remove_mods(self, mod_ids_to_remove: Set[str]) -> int:
        """Safely removes specified mod IDs from the file while preserving structure."""
        if not os.path.exists(self.file_path):
            return 0

        self.backup()
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        new_lines = []
        removed = 0
        for line in lines:
            m = re.search(r'mod\s*=\s*([^,;\r\n]+)', line)
            if m:
                mid = m.group(1).strip()
                if mid in mod_ids_to_remove:
                    removed += 1
                    continue
            new_lines.append(line)

        with open(self.file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        self.load() # reload active
        return removed
