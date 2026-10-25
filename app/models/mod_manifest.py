import os
import json
from typing import Dict, List, Optional, Any
from app.models.workshop import Workshop
from app.models.server_config import ServerConfig
from app.models.steam_downloader import SteamDownloader


class ModManifestManager:
    """Manages the server_mods_manifest.json file and automated mod downloads."""

    DEFAULT_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                         "data", "server_mods_manifest.json")

    @classmethod
    def get_manifest_path(cls) -> str:
        return cls.DEFAULT_MANIFEST_PATH

    @classmethod
    def load_manifest(cls, path: Optional[str] = None) -> Dict[str, Any]:
        p = path or cls.get_manifest_path()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"app_id": "108600", "mods": {}}

    @classmethod
    def save_manifest(cls, data: Dict[str, Any], path: Optional[str] = None) -> None:
        p = path or cls.get_manifest_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def generate_or_update_from_server(cls, server_config: ServerConfig, workshop: Workshop) -> Dict[str, Any]:
        """Generates or updates server_mods_manifest.json using current server mods and workshop catalog."""
        manifest = cls.load_manifest()
        workshop.scan()
        mods_dict = manifest.get("mods", {})

        current_mods = server_config.load_mods()
        current_ws_items = server_config.load_workshop_items()

        # Map each active mod
        for mod_id in current_mods:
            mod = workshop.get_mod(mod_id)
            ws_id = mod.workshop_id if mod and mod.workshop_id else SteamDownloader.resolve_workshop_id(mod_id, workshop)

            # Check if ws_id was numeric in WorkshopItems
            if not ws_id:
                for candidate in current_ws_items:
                    if candidate.isdigit() and len(candidate) >= 6:
                        ws_id = candidate
                        break

            mods_dict[mod_id] = {
                "mod_id": mod_id,
                "workshop_id": ws_id or "",
                "name": mod.name if mod else mod_id,
                "version": mod.target_version if mod else "42",
                "synced": bool(mod and mod.mod_folder and os.path.exists(mod.mod_folder)),
                "local_path": mod.mod_folder if mod else "",
            }

        manifest["mods"] = mods_dict
        cls.save_manifest(manifest)
        return manifest

    @classmethod
    def add_mod_entry(cls, mod_id: str, workshop_id: str, name: str = "", target_version: str = "42") -> Dict[str, Any]:
        """Adds a single mod entry with download metadata into the JSON manifest."""
        manifest = cls.load_manifest()
        manifest.setdefault("mods", {})[mod_id] = {
            "mod_id": mod_id,
            "workshop_id": str(workshop_id),
            "name": name or mod_id,
            "version": target_version,
            "synced": False,
            "local_path": "",
        }
        cls.save_manifest(manifest)
        return manifest

    @classmethod
    def download_all_from_manifest(cls, workshop_dir: str, copy_to_local_mods: bool = True,
                                   user_zomboid_mods_dir: Optional[str] = None) -> Dict[str, Any]:
        """Downloads all mods defined in the JSON manifest via SteamCMD and optionally copies to user mods."""
        manifest = cls.load_manifest()
        mods = manifest.get("mods", {})
        results = {
            "total": len(mods),
            "downloaded": [],
            "already_present": [],
            "failed": []
        }

        steamcmd = SteamDownloader.get_steamcmd_path()
        if not steamcmd:
            results["error"] = "SteamCMD não encontrado em C:\\steamcmd\\steamcmd.exe"
            return results

        os.makedirs(workshop_dir, exist_ok=True)
        if copy_to_local_mods and user_zomboid_mods_dir:
            os.makedirs(user_zomboid_mods_dir, exist_ok=True)

        for mod_id, info in mods.items():
            ws_id = info.get("workshop_id", "").strip()
            if not ws_id or not ws_id.isdigit():
                continue

            target_ws_item = os.path.join(workshop_dir, ws_id)
            if not (os.path.isdir(target_ws_item) and any(os.scandir(target_ws_item))):
                ok, msg = SteamDownloader.download_workshop_item(ws_id, workshop_dir)
                if not ok:
                    results["failed"].append((mod_id, ws_id, msg))
                    continue
                results["downloaded"].append((mod_id, ws_id))
            else:
                results["already_present"].append((mod_id, ws_id))

            # Mark synced
            info["synced"] = True

            # If copy to local mods is requested, copy the subfolder containing mod.info
            if copy_to_local_mods and user_zomboid_mods_dir and os.path.exists(target_ws_item):
                cls._deploy_to_local_mods(target_ws_item, user_zomboid_mods_dir)

        cls.save_manifest(manifest)
        return results

    @classmethod
    def find_best_mod_folder(cls, mod_dir: str) -> Optional[str]:
        """Finds the best candidate directory containing mod.info prioritizing Build 42 versions."""
        if not os.path.isdir(mod_dir):
            return None

        candidates = []
        if os.path.exists(os.path.join(mod_dir, "mod.info")):
            candidates.append(("root", 0.0, mod_dir))

        try:
            for sub in os.listdir(mod_dir):
                sub_p = os.path.join(mod_dir, sub)
                if os.path.isdir(sub_p) and os.path.exists(os.path.join(sub_p, "mod.info")):
                    if sub == "42":
                        candidates.append(("b42", 42.0, sub_p))
                    elif sub.startswith("42."):
                        try:
                            num = float(sub)
                            candidates.append(("b42_ver", num, sub_p))
                        except Exception:
                            candidates.append(("b42_ver", 42.0, sub_p))
                    elif sub.lower() == "common":
                        candidates.append(("common", 1.0, sub_p))
                    else:
                        candidates.append(("other", 0.5, sub_p))
        except Exception:
            pass

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][2]

    @classmethod
    def _copy_mod_files(cls, src_folder: str, target_dest: str) -> None:
        """Copies all files from src_folder to target_dest safely."""
        import shutil
        os.makedirs(target_dest, exist_ok=True)
        for item in os.listdir(src_folder):
            s = os.path.join(src_folder, item)
            d = os.path.join(target_dest, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

    @classmethod
    def get_mod_id(cls, folder: str) -> Optional[str]:
        """Extracts the id= value from mod.info inside the folder."""
        info = os.path.join(folder, "mod.info")
        if os.path.exists(info):
            try:
                with open(info, "r", encoding="utf-8", errors="ignore") as f:
                    for l in f:
                        if l.startswith("id="):
                            return l.strip().split("=", 1)[1].strip()
            except Exception:
                pass
        return None

    @classmethod
    def deploy_workshop_item_to_local_mods(cls, workshop_item_dir: str, local_mods_dir: str) -> List[str]:
        """Finds mod folders containing mod.info (including all B42 and common subfolders) and deploys them to local mods."""
        if not os.path.isdir(workshop_item_dir):
            return []

        os.makedirs(local_mods_dir, exist_ok=True)
        deployed_mods = []

        mods_sub = os.path.join(workshop_item_dir, "mods")
        search_root = mods_sub if os.path.exists(mods_sub) else workshop_item_dir

        try:
            for entry in os.scandir(search_root):
                if entry.is_dir():
                    best_src = cls.find_best_mod_folder(entry.path)
                    if best_src:
                        mid = cls.get_mod_id(best_src)
                        target_name = mid if mid else entry.name
                        target_dest = os.path.join(local_mods_dir, target_name)
                        cls._copy_mod_files(best_src, target_dest)
                        deployed_mods.append(target_name)
                        if entry.name != target_name:
                            alt_dest = os.path.join(local_mods_dir, entry.name)
                            if not os.path.exists(alt_dest):
                                cls._copy_mod_files(best_src, alt_dest)
        except Exception:
            pass

        # If search_root itself is a single mod directory (rare)
        if not deployed_mods:
            best_root = cls.find_best_mod_folder(search_root)
            if best_root:
                mid = cls.get_mod_id(best_root)
                name = mid if mid else os.path.basename(workshop_item_dir)
                target_dest = os.path.join(local_mods_dir, name)
                cls._copy_mod_files(best_root, target_dest)
                deployed_mods.append(name)

        return deployed_mods

    @classmethod
    def deploy_all_workshop_to_local_mods(cls, workshop_dir: str, local_mods_dir: str) -> Dict[str, Any]:
        """Scans the entire workshop content directory and deploys all mods to the user mods directory."""
        results = {"total_items": 0, "deployed_mods": []}
        if not os.path.isdir(workshop_dir):
            return results

        for item in os.listdir(workshop_dir):
            item_path = os.path.join(workshop_dir, item)
            if os.path.isdir(item_path):
                results["total_items"] += 1
                dep = cls.deploy_workshop_item_to_local_mods(item_path, local_mods_dir)
                results["deployed_mods"].extend(dep)

        return results

    @classmethod
    def _deploy_to_local_mods(cls, workshop_item_dir: str, local_mods_dir: str) -> None:
        """Backwards compatible alias for deploy_workshop_item_to_local_mods."""
        cls.deploy_workshop_item_to_local_mods(workshop_item_dir, local_mods_dir)
