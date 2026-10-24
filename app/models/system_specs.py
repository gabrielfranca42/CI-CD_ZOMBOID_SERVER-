import os
import ctypes
from dataclasses import dataclass

@dataclass
class SystemSpecs:
    total_ram_gb: float
    free_ram_gb: float
    total_pagefile_gb: float
    free_pagefile_gb: float
    commit_limit_gb: float
    game_version: str
    workshop_dir: str
    user_zomboid_dir: str
    game_dir: str

    @classmethod
    def detect(cls) -> "SystemSpecs":
        workshop_dir = r"D:\SteamLibrary\steamapps\workshop\content\108600"
        user_zomboid_dir = r"C:\Users\User\Zomboid"
        game_dir = r"D:\SteamLibrary\steamapps\common\ProjectZomboid"
        game_version = "Build 42.21.0"

        # Check version.txt if available
        ver_file = os.path.join(user_zomboid_dir, "version.txt")
        if os.path.exists(ver_file):
            try:
                with open(ver_file, "r") as f:
                    content = f.read().strip()
                    if content:
                        game_version = content
            except Exception:
                pass

        total_ram_gb = 16.0
        free_ram_gb = 8.0
        total_pagefile_gb = 3.0
        free_pagefile_gb = 2.0
        commit_limit_gb = 19.0

        if os.name == "nt":
            try:
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                total_ram_gb = round(stat.ullTotalPhys / (1024 ** 3), 2)
                free_ram_gb = round(stat.ullAvailPhys / (1024 ** 3), 2)
                total_pagefile_gb = round((stat.ullTotalPageFile - stat.ullTotalPhys) / (1024 ** 3), 2)
                free_pagefile_gb = round(stat.ullAvailPageFile / (1024 ** 3), 2)
                commit_limit_gb = round(stat.ullTotalPageFile / (1024 ** 3), 2)
            except Exception:
                pass

        return cls(
            total_ram_gb=total_ram_gb,
            free_ram_gb=free_ram_gb,
            total_pagefile_gb=max(0.0, total_pagefile_gb),
            free_pagefile_gb=free_pagefile_gb,
            commit_limit_gb=commit_limit_gb,
            game_version=game_version,
            workshop_dir=workshop_dir,
            user_zomboid_dir=user_zomboid_dir,
            game_dir=game_dir
        )
