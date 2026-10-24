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
        """Loads the active mod IDs from server.ini (Mods= line)."""
        if not os.path.exists(self.server_ini_path):
            return []

        mods = []
        try:
            with open(self.server_ini_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("Mods="):
                        content = line.split("Mods=", 1)[1].strip()
                        if content:
                            mods = [m.strip() for m in content.split(";") if m.strip()]
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

    def load_host_memory(self) -> int:
        """Returns the memory configured in host.ini in MB (default 2048 if missing)."""
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
        """Updates host.ini memory setting."""
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

    def save_server_mods(self, mods: List[str], workshop_items: List[str]):
        """Saves updated Mods= and WorkshopItems= lists to server.ini with backup."""
        if not os.path.exists(self.server_ini_path):
            return

        # Create backup
        shutil.copy2(self.server_ini_path, self.server_ini_path + ".bak")

        mods_line = "Mods=" + ";".join(mods) + "\n"
        ws_line = "WorkshopItems=" + ";".join(workshop_items) + "\n"

        output_lines = []
        with open(self.server_ini_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("Mods="):
                    output_lines.append(mods_line)
                elif line.startswith("WorkshopItems="):
                    output_lines.append(ws_line)
                else:
                    output_lines.append(line)

        with open(self.server_ini_path, "w", encoding="utf-8") as f:
            f.writelines(output_lines)
