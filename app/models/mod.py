import os
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Mod:
    id: str
    name: str
    mod_folder: str
    workshop_id: Optional[str] = None
    require: List[str] = field(default_factory=list)
    pack: List[str] = field(default_factory=list)
    depthmap_count: int = 0
    depthmap_size_mb: float = 0.0
    fbx_count: int = 0
    is_active: bool = False

    @classmethod
    def from_mod_info(cls, mod_info_path: str, workshop_id: Optional[str] = None) -> Optional["Mod"]:
        """Parses a mod.info file and scans for depthmaps and FBX 3D animations."""
        if not os.path.exists(mod_info_path):
            return None

        mod_id = None
        name = None
        require = []
        pack = []
        mod_folder = os.path.dirname(mod_info_path)

        try:
            with open(mod_info_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("id="):
                        mod_id = line.split("id=", 1)[1].strip()
                    elif line.startswith("name="):
                        name = line.split("name=", 1)[1].strip()
                    elif line.startswith("require="):
                        reqs = line.split("require=", 1)[1].strip()
                        if reqs:
                            require = [r.strip().lstrip(r"\/") for r in reqs.split(",") if r.strip()]
                    elif line.startswith("pack="):
                        packs = line.split("pack=", 1)[1].strip()
                        if packs:
                            pack = [p.strip() for p in packs.split(",") if p.strip()]
        except Exception:
            return None

        if not mod_id:
            return None

        if not name:
            name = mod_id

        # Scan depthmaps (2D tiles) and FBX (3D skeletal animations)
        depthmap_count = 0
        total_depth_bytes = 0
        fbx_count = 0

        # Define search directories: mod_folder itself, plus parent directories up to workshop item root if applicable
        scan_dirs = [mod_folder]
        parent = os.path.dirname(mod_folder)
        # If mod_folder is inside a subfolder like '42' or 'mods/<modname>', check common assets in parent/grandparent
        for _ in range(2):
            if parent and os.path.isdir(parent) and ("steamapps" in parent.lower() or "workshop" in parent.lower() or "mods" in parent.lower()):
                common_dir = os.path.join(parent, "common")
                if os.path.isdir(common_dir) and common_dir not in scan_dirs:
                    scan_dirs.append(common_dir)
                parent = os.path.dirname(parent)

        scanned_files = set()
        for sdir in scan_dirs:
            if not os.path.exists(sdir):
                continue
            for root, _, files in os.walk(sdir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path in scanned_files:
                        continue
                    scanned_files.add(file_path)

                    f_lower = file.lower()
                    if f_lower.endswith(".png") and ("depth" in f_lower or "depthmap" in root.lower()):
                        depthmap_count += 1
                        try:
                            total_depth_bytes += os.path.getsize(file_path)
                        except Exception:
                            pass
                    elif f_lower.endswith(".fbx"):
                        fbx_count += 1

        depthmap_size_mb = round(total_depth_bytes / (1024 * 1024), 2)

        return cls(
            id=mod_id,
            name=name,
            mod_folder=mod_folder,
            workshop_id=workshop_id,
            require=require,
            pack=pack,
            depthmap_count=depthmap_count,
            depthmap_size_mb=depthmap_size_mb,
            fbx_count=fbx_count
        )
