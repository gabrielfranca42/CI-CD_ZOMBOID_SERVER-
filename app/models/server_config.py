import os
import shutil
from typing import List, Dict, Optional, Tuple

class ServerConfig:
    """Manages Project Zomboid dedicated/coop server configuration (servertest.ini and host.ini)."""

    def __init__(self, server_ini_path: str, host_ini_path: str):
        self.server_ini_path = server_ini_path
        self.host_ini_path = host_ini_path

    @classmethod
    def default(cls, user_zomboid_dir: str = r"C:\Users\User\Zomboid", server_name: str = "servertest") -> "ServerConfig":
        server_ini = os.path.join(user_zomboid_dir, "Server", f"{server_name}.ini")
        host_ini = os.path.join(user_zomboid_dir, "Lua", "host.ini")
        return cls(server_ini, host_ini)

    def load_mods(self) -> List[str]:
        """Loads the active mod IDs from server.ini (Mods= line), stripping leading backslashes."""
        if not os.path.exists(self.server_ini_path):
            return []

        mods = []
        try:
            with open(self.server_ini_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("Mods="):
                        content = line.split("Mods=", 1)[1].strip()
                        if content:
                            raw_mods = [m.strip().lstrip(r"\/") for m in content.split(";") if m.strip()]
                            for m in raw_mods:
                                if m and m not in mods:
                                    mods.append(m)
                        break
        except Exception:
            pass
        return mods

    def load_workshop_items(self) -> List[str]:
        """Loads Workshop IDs configured in server.ini (WorkshopItems= line)."""
        if not os.path.exists(self.server_ini_path):
            return []

        items = []
        try:
            with open(self.server_ini_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("WorkshopItems="):
                        content = line.split("WorkshopItems=", 1)[1].strip()
                        if content:
                            items = [w.strip() for w in content.split(";") if w.strip()]
                        break
        except Exception:
            pass
        return items

    def load_maps(self) -> List[str]:
        """Loads configured map folders from server.ini (Map= line).

        Project Zomboid requires custom map folders to precede 'Muldraugh, KY'.
        """
        if not os.path.exists(self.server_ini_path):
            return ["Muldraugh, KY"]

        maps = []
        try:
            with open(self.server_ini_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("Map="):
                        content = line.split("Map=", 1)[1].strip()
                        if content:
                            maps = [m.strip() for m in content.split(";") if m.strip()]
                        break
        except Exception:
            pass

        if not maps:
            maps = ["Muldraugh, KY"]
        elif "Muldraugh, KY" not in maps:
            maps.append("Muldraugh, KY")

        return maps

    def load_host_memory(self) -> int:
        """Returns the memory configured in host.ini in MB (default 2048 if missing).

        Note: host.ini controls the in-game 'Host' menu (co-op). Standalone dedicated
        servers (StartServer64.bat) configure JVM memory via -Xms and -Xmx in ProjectZomboid64.json.
        """
        if not os.path.exists(self.host_ini_path):
            return 2048

        try:
            with open(self.host_ini_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("memory="):
                        return int(line.split("memory=", 1)[1].strip())
        except Exception:
            pass
        return 2048

    def set_host_memory(self, memory_mb: int):
        """Updates host.ini memory setting for co-op host sessions."""
        if not os.path.exists(self.host_ini_path):
            os.makedirs(os.path.dirname(self.host_ini_path), exist_ok=True)
            with open(self.host_ini_path, "w", encoding="utf-8") as f:
                f.write(f"servername=servertest\nusername=admin\nmemory={memory_mb}\n")
            return

        lines = []
        found = False
        with open(self.host_ini_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("memory="):
                    lines.append(f"memory={memory_mb}\n")
                    found = True
                else:
                    lines.append(line)
        if not found:
            lines.append(f"memory={memory_mb}\n")

        with open(self.host_ini_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def apply_zero_steam_boot(self) -> Tuple[int, int]:
        """Clears WorkshopItems= line while preserving all Mods= and Map= entries for instant offline loading.

        Returns:
            (mods_count: int, previous_workshop_items_count: int)
        """
        current_mods = self.load_mods()
        current_ws = self.load_workshop_items()
        current_maps = self.load_maps()
        self.save_server_mods(current_mods, workshop_items=[], maps=current_maps)
        return len(current_mods), len(current_ws)

    def save_server_mods(self, mods: List[str], workshop_items: List[str], maps: Optional[List[str]] = None):
        """Saves updated Mods=, WorkshopItems=, and Map= lists to server.ini with backup."""
        if not os.path.exists(self.server_ini_path):
            return

        # Create backup
        shutil.copy2(self.server_ini_path, self.server_ini_path + ".bak")

        # Ensure PZ standard trailing semicolon
        mods_str = ";".join(mods)
        mods_line = f"Mods={mods_str};\n" if mods else "Mods=\n"

        ws_str = ";".join(workshop_items)
        ws_line = f"WorkshopItems={ws_str};\n" if workshop_items else "WorkshopItems=\n"

        map_line = None
        if maps is not None:
            # Ensure Muldraugh, KY is last
            clean_maps = [m for m in maps if m != "Muldraugh, KY"]
            clean_maps.append("Muldraugh, KY")
            map_str = ";".join(clean_maps)
            map_line = f"Map={map_str};\n"

        output_lines = []
        map_written = False
        with open(self.server_ini_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("Mods="):
                    output_lines.append(mods_line)
                elif line.startswith("WorkshopItems="):
                    output_lines.append(ws_line)
                elif line.startswith("Map="):
                    if map_line is not None:
                        output_lines.append(map_line)
                        map_written = True
                    else:
                        output_lines.append(line)
                else:
                    output_lines.append(line)

        if map_line is not None and not map_written:
            output_lines.append(map_line)

        with open(self.server_ini_path, "w", encoding="utf-8") as f:
            f.writelines(output_lines)
