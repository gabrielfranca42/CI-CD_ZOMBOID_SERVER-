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
    incompatible: List[str] = field(default_factory=list)
    version_min: Optional[str] = None
    version_max: Optional[str] = None
    mod_version: Optional[str] = None
    target_version: str = "common"
    map_folders: List[str] = field(default_factory=list)
    depthmap_count: int = 0
    depthmap_size_mb: float = 0.0
    fbx_count: int = 0
    is_active: bool = False

    @classmethod
    def from_mod_info(cls, mod_info_path: str, workshop_id: Optional[str] = None) -> Optional["Mod"]:
        """Parses a mod.info file with Build 42 metadata, dependencies, and map assets."""
        if not os.path.exists(mod_info_path):
            return None

        mod_id = None
        name = None
        require: List[str] = []
        pack: List[str] = []
        incompatible: List[str] = []
        version_min = None
        version_max = None
        mod_version = None
        mod_folder = os.path.dirname(mod_info_path)

        norm_path = mod_info_path.replace("\\", "/")
        if "/42/" in norm_path or "/42." in norm_path:
            target_version = "42"
        elif "/common/" in norm_path:
            target_version = "common"
        else:
            target_version = "legacy"

        try:
            with open(mod_info_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("id="):
                        mod_id = line.split("id=", 1)[1].strip()
                    elif line.startswith("name="):
                        name = line.split("name=", 1)[1].strip()
                    elif line.startswith("require="):
                        reqs = line.split("require=", 1)[1].strip()
                        if reqs:
                            # Support comma and semicolon delimiters
                            raw_items = [r.strip().lstrip(r"\/") for sep in [",", ";"] for r in reqs.split(sep) if r.strip()]
                            for item in raw_items:
                                if item and item not in require:
                                    require.append(item)
                    elif line.startswith("pack="):
                        packs = line.split("pack=", 1)[1].strip()
                        if packs:
                            raw_packs = [p.strip() for sep in [",", ";"] for p in packs.split(sep) if p.strip()]
                            for p in raw_packs:
                                if p and p not in pack:
                                    pack.append(p)
                    elif line.startswith("incompatible="):
                        incomps = line.split("incompatible=", 1)[1].strip()
                        if incomps:
                            raw_incomps = [inc.strip().lstrip(r"\/") for sep in [",", ";"] for inc in incomps.split(sep) if inc.strip()]
                            for inc in raw_incomps:
                                if inc and inc not in incompatible:
                                    incompatible.append(inc)
                    elif line.startswith("versionMin="):
                        version_min = line.split("versionMin=", 1)[1].strip()
                    elif line.startswith("versionMax="):
                        version_max = line.split("versionMax=", 1)[1].strip()
                    elif line.startswith("modversion="):
                        mod_version = line.split("modversion=", 1)[1].strip()
        except Exception:
            return None

        if not mod_id:
            return None

        if not name:
            name = mod_id

        # Scan for map directories (media/maps/<MapName>)
        map_folders: List[str] = []
        maps_dir = os.path.join(mod_folder, "media", "maps")
        if os.path.isdir(maps_dir):
            try:
                for entry in os.listdir(maps_dir):
                    sub = os.path.join(maps_dir, entry)
                    if os.path.isdir(sub) and not entry.startswith("."):
                        map_folders.append(entry)
            except Exception:
                pass

        # Scan depthmaps (2D tiles) and FBX (3D skeletal animations)
        depthmap_count = 0
        total_depth_bytes = 0
        fbx_count = 0

        scan_dirs = [mod_folder]
        parent = os.path.dirname(mod_folder)
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
            incompatible=incompatible,
            version_min=version_min,
            version_max=version_max,
            mod_version=mod_version,
            target_version=target_version,
            map_folders=map_folders,
            depthmap_count=depthmap_count,
            depthmap_size_mb=depthmap_size_mb,
            fbx_count=fbx_count
        )
