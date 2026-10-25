import os
import shutil
import subprocess
import re
import urllib.request
import urllib.parse
from typing import Optional, Tuple, List, Dict, Any
from app.models.workshop import Workshop
from app.models.mod import Mod
from app.models.build_validator import BuildValidator


class SteamDownloader:
    """Manages mod downloads via SteamCMD and performs real-time validation."""

    PZ_APP_ID = "108600"

    # Known Mod ID -> Workshop ID cache for common frameworks/dependencies
    KNOWN_MAPPINGS: Dict[str, str] = {
        "tsarslib": "2392709985",
        "autotsartrailers": "2282429356",
        "TchernoLib": "2872282653",
        "PROJECTRVInterior42": "3127814420",
        "67commando": "2478768005",
        "78amgeneralM35A2": "2811383142",
        "78amgeneralM49A2C": "2811383142",
        "78amgeneralM50A3": "2811383142",
        "ChuckleberryFinnAlertSystem": "2914101037",
        "modoptions": "2169435997",
    }

    @classmethod
    def get_steamcmd_path(cls) -> Optional[str]:
        """Locates the SteamCMD executable."""
        candidates = [
            r"C:\steamcmd\steamcmd.exe",
            os.environ.get("STEAMCMD_PATH", ""),
            shutil.which("steamcmd") or "",
            shutil.which("steamcmd.exe") or "",
            r"C:\Program Files (x86)\SteamCMD\steamcmd.exe",
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return None

    @classmethod
    def resolve_workshop_id(cls, mod_or_req: str, workshop: Optional[Workshop] = None) -> Optional[str]:
        """Resolves a mod requirement (ID, clean name, or numeric ID) to a Steam Workshop ID."""
        clean = mod_or_req.lstrip(r"\/").strip()

        # If already numeric
        if clean.isdigit() and len(clean) >= 6:
            return clean

        # Check in local workshop if already indexed
        if workshop:
            mod = workshop.get_mod(clean)
            if mod and mod.workshop_id:
                return mod.workshop_id

        # Check known mappings
        if clean in cls.KNOWN_MAPPINGS:
            return cls.KNOWN_MAPPINGS[clean]

        # Web search on Steam Workshop for Project Zomboid
        try:
            query = urllib.parse.quote(clean)
            url = f"https://steamcommunity.com/workshop/browse/?appid={cls.PZ_APP_ID}&searchtext={query}&browsesort=textsearch&section=readytouseitems"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Match first sharedfile ID
            matches = re.findall(r'id=\"publishedfile_(\d+)\"', html) or re.findall(r'filedetails/\?id=(\d+)', html)
            if matches:
                # Cache for future use
                cls.KNOWN_MAPPINGS[clean] = matches[0]
                return matches[0]
        except Exception:
            pass

        return None

    @classmethod
    def download_workshop_item(cls, workshop_id: str, target_workshop_dir: str,
                               auto_deploy: bool = True,
                               user_mods_dir: Optional[str] = None) -> Tuple[bool, str]:
        """Invokes SteamCMD to download a workshop item and copies it into target_workshop_dir,
        automatically deploying to local mods if auto_deploy is True."""
        steamcmd = cls.get_steamcmd_path()
        if not steamcmd:
            return False, "SteamCMD não encontrado em C:\\steamcmd\\steamcmd.exe ou no PATH do sistema."

        try:
            cmd = [
                steamcmd,
                "+login", "anonymous",
                "+workshop_download_item", cls.PZ_APP_ID, str(workshop_id),
                "+quit"
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180
            )

            # Locate downloaded content
            steamcmd_dir = os.path.dirname(steamcmd)
            src_item_dir = os.path.join(steamcmd_dir, "steamapps", "workshop", "content", cls.PZ_APP_ID, str(workshop_id))
            dest_item_dir = os.path.join(target_workshop_dir, str(workshop_id))

            # Check if download succeeded and folder exists
            if not os.path.exists(src_item_dir):
                # Check target directly in case force_install or shared dir
                if not os.path.exists(dest_item_dir):
                    return False, f"SteamCMD terminou mas pasta {src_item_dir} não foi encontrada. Saída: {result.stdout[-300:]}"
            else:
                # Copy or sync to target_workshop_dir
                if os.path.abspath(src_item_dir).lower() != os.path.abspath(dest_item_dir).lower():
                    os.makedirs(target_workshop_dir, exist_ok=True)
                    if os.path.exists(dest_item_dir):
                        shutil.rmtree(dest_item_dir, ignore_errors=True)
                    shutil.copytree(src_item_dir, dest_item_dir)

            # Automatic local mod implantation
            deployed_msg = ""
            if auto_deploy:
                local_dir = user_mods_dir or os.path.join(os.path.expanduser("~"), "Zomboid", "mods")
                try:
                    from app.models.mod_manifest import ModManifestManager
                    deployed = ModManifestManager.deploy_workshop_item_to_local_mods(dest_item_dir, local_dir)
                    if deployed:
                        deployed_msg = f" | Implantado em mods locais: {', '.join(deployed)}"
                except Exception as e:
                    deployed_msg = f" | Falha na implantação local: {e}"

            return True, f"Download e instalação concluídos com sucesso: {dest_item_dir}{deployed_msg}"

        except subprocess.TimeoutExpired:
            return False, f"Timeout ao baixar Workshop ID {workshop_id} via SteamCMD (excedeu 180s)."
        except Exception as e:
            return False, f"Erro ao executar SteamCMD: {e}"

    @classmethod
    def install_and_validate(cls, mod_or_req: str, workshop: Workshop,
                             target_workshop_dir: str,
                             user_mods_dir: Optional[str] = None) -> Tuple[bool, str, List[str]]:
        """Downloads a missing mod via SteamCMD and immediately validates it in real time.

        Returns:
            (is_valid: bool, mod_id: str, diagnostics: List[str])
        """
        diagnostics = []

        # Step 1: Resolve Workshop ID
        ws_id = cls.resolve_workshop_id(mod_or_req, workshop)
        if not ws_id:
            return False, mod_or_req, [f"Não foi possível resolver o Workshop ID para '{mod_or_req}'."]

        diagnostics.append(f"Workshop ID identificado: {ws_id}")

        # Step 2: Download via SteamCMD (with automatic local mod deployment)
        local_dir = user_mods_dir or os.path.join(os.path.expanduser("~"), "Zomboid", "mods")
        success, msg = cls.download_workshop_item(ws_id, target_workshop_dir, auto_deploy=True, user_mods_dir=local_dir)
        diagnostics.append(msg)
        if not success:
            return False, mod_or_req, diagnostics

        # Step 3: Rescan Workshop
        workshop.scan()

        # Step 4: Find the Mod object
        found_mod: Optional[Mod] = None
        for m in workshop.mods.values():
            if m.workshop_id == ws_id or m.id == mod_or_req:
                found_mod = m
                break

        if not found_mod:
            return False, mod_or_req, diagnostics + ["Mod baixado mas nenhum 'mod.info' válido foi detectado no pacote."]

        diagnostics.append(f"Mod indexado: '{found_mod.name}' (ID: {found_mod.id}) | Versão: {found_mod.target_version}")

        # Step 5: Real-time Build & Syntax Validation
        build_errors = BuildValidator.validate_mod(found_mod)
        if build_errors:
            diagnostics.append(f"🔴 FALHA DE COMPILAÇÃO ({len(build_errors)} erros):")
            diagnostics.extend([f"   * {e}" for e in build_errors[:5]])
            return False, found_mod.id, diagnostics

        # Step 6: Check B42 compatibility & known crashers
        if found_mod.id in ("amclub", "autotsartrailers", "tsarslib"):
            diagnostics.append(f"🔴 CRASH CONHECIDO NA B42: O mod '{found_mod.id}' causa crash fatal no motor Jassimp.")
            return False, found_mod.id, diagnostics

        # Step 7: Automatic deployment verified
        dest_item_dir = os.path.join(target_workshop_dir, str(ws_id))
        from app.models.mod_manifest import ModManifestManager
        deployed = ModManifestManager.deploy_workshop_item_to_local_mods(dest_item_dir, local_dir)
        if deployed:
            diagnostics.append(f"📦 IMPLANTAÇÃO LOCAL: Mod(s) '{', '.join(deployed)}' implantado(s) em '{local_dir}'.")

        diagnostics.append("✅ VALIDAÇÃO EM TEMPO REAL: Mod compila com sucesso, sintaxe aprovada e compatível com B42!")
        return True, found_mod.id, diagnostics

    @classmethod
    def sync_workshop_items(cls, workshop_ids: List[str], target_workshop_dir: str,
                            auto_deploy: bool = True,
                            user_mods_dir: Optional[str] = None) -> Dict[str, Any]:
        """Pre-downloads and syncs all workshop items via SteamCMD, automatically deploying them to local mods.

        Returns:
            Dict with 'total', 'success', 'already_present', 'failed', 'deployed'.
        """
        results = {
            "total": len(workshop_ids),
            "success": [],
            "already_present": [],
            "failed": [],
            "deployed": [],
        }
        steamcmd = cls.get_steamcmd_path()
        if not steamcmd:
            results["error"] = "SteamCMD não encontrado em C:\\steamcmd\\steamcmd.exe ou no PATH do sistema."
            return results

        os.makedirs(target_workshop_dir, exist_ok=True)
        local_dir = user_mods_dir or os.path.join(os.path.expanduser("~"), "Zomboid", "mods")

        for idx, ws_id in enumerate(workshop_ids, start=1):
            clean_id = str(ws_id).strip()
            if not clean_id or not clean_id.isdigit():
                continue

            dest_item_dir = os.path.join(target_workshop_dir, clean_id)
            # If already present on disk and has contents
            if os.path.isdir(dest_item_dir) and any(os.scandir(dest_item_dir)):
                results["already_present"].append(clean_id)
            else:
                ok, msg = cls.download_workshop_item(clean_id, target_workshop_dir, auto_deploy=False)
                if ok:
                    results["success"].append(clean_id)
                else:
                    results["failed"].append((clean_id, msg))
                    continue

            # Automatic local deployment for every synced item
            if auto_deploy and os.path.exists(dest_item_dir):
                from app.models.mod_manifest import ModManifestManager
                dep = ModManifestManager.deploy_workshop_item_to_local_mods(dest_item_dir, local_dir)
                results["deployed"].extend(dep)

        return results
