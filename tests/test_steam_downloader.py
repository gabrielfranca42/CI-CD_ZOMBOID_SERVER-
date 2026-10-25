import unittest
import os
import shutil
import tempfile
from app.models.steam_downloader import SteamDownloader
from app.models.workshop import Workshop
from app.models.mod import Mod
from app.models.server_config import ServerConfig
from app.models.mod_list import ModList
from app.controllers.gatekeeper_controller import GatekeeperController
from app.controllers.server_controller import ServerController


class TestSteamDownloader(unittest.TestCase):

    def test_steamcmd_path_detection(self):
        path = SteamDownloader.get_steamcmd_path()
        # SteamCMD is present on user's system at C:\steamcmd\steamcmd.exe
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))

    def test_resolve_workshop_id_numeric(self):
        res = SteamDownloader.resolve_workshop_id("3783094058")
        self.assertEqual(res, "3783094058")

    def test_resolve_workshop_id_known_mapping(self):
        res = SteamDownloader.resolve_workshop_id("TchernoLib")
        self.assertEqual(res, "2872282653")

    def test_resolve_workshop_id_local_workshop(self):
        ws = Workshop("/fake/path")
        mod = Mod(id="custom_mod", name="Custom Mod", workshop_id="999888777", mod_folder="/fake/folder")
        ws.mods["custom_mod"] = mod

        res = SteamDownloader.resolve_workshop_id("custom_mod", workshop=ws)
        self.assertEqual(res, "999888777")

    def test_gatekeeper_remove_mod_by_id(self):
        temp_dir = tempfile.mkdtemp()
        try:
            default_txt = os.path.join(temp_dir, "default.txt")
            with open(default_txt, "w", encoding="utf-8") as f:
                f.write("mod=mod_a\nmod=mod_b\nmod=mod_c\n")

            mod_list = ModList(default_txt)
            self.assertEqual(len(mod_list.load()), 3)

            mod_list.remove_mods({"mod_b"})
            remaining = mod_list.load()
            self.assertEqual(remaining, ["mod_a", "mod_c"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_server_remove_mod_by_id(self):
        temp_dir = tempfile.mkdtemp()
        try:
            ini_path = os.path.join(temp_dir, "servertest.ini")
            host_ini = os.path.join(temp_dir, "servertest_host.ini")
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write("Mods=mod_a;mod_b;mod_c\nWorkshopItems=111;222;333\nMap=Muldraugh, KY\n")
            with open(host_ini, "w", encoding="utf-8") as f:
                f.write("Memory=2048\n")

            cfg = ServerConfig(ini_path, host_ini)
            mods = cfg.load_mods()
            self.assertIn("mod_b", mods)

            # Remove mod_b
            sanitized = [m for m in mods if m != "mod_b"]
            cfg.save_server_mods(sanitized, ["111", "333"])

            updated_mods = cfg.load_mods()
            self.assertNotIn("mod_b", updated_mods)
            self.assertEqual(updated_mods, ["mod_a", "mod_c"])

            # Test Zero-Steam Boot
            mods_count, prev_ws = cfg.apply_zero_steam_boot()
            self.assertEqual(mods_count, 2)
            self.assertEqual(prev_ws, 2)
            self.assertEqual(cfg.load_workshop_items(), [])
            self.assertEqual(cfg.load_mods(), ["mod_a", "mod_c"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
