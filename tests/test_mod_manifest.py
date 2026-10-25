import unittest
import os
import shutil
import tempfile
from app.models.mod_manifest import ModManifestManager


class TestModManifestManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workshop_dir = os.path.join(self.temp_dir, "workshop")
        self.local_mods_dir = os.path.join(self.temp_dir, "local_mods")
        os.makedirs(self.workshop_dir, exist_ok=True)
        os.makedirs(self.local_mods_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_best_mod_folder_prioritizes_b42(self):
        mod_root = os.path.join(self.workshop_dir, "test_item", "mods", "TestMod")
        v_common = os.path.join(mod_root, "common")
        v_b42 = os.path.join(mod_root, "42.15")
        os.makedirs(v_common, exist_ok=True)
        os.makedirs(v_b42, exist_ok=True)

        with open(os.path.join(v_common, "mod.info"), "w", encoding="utf-8") as f:
            f.write("id=TestModCommon\nname=Test Mod Common\n")

        with open(os.path.join(v_b42, "mod.info"), "w", encoding="utf-8") as f:
            f.write("id=TestModB42\nname=Test Mod B42\n")

        best = ModManifestManager.find_best_mod_folder(mod_root)
        self.assertEqual(best, v_b42)

    def test_deploy_workshop_item_to_local_mods(self):
        item_dir = os.path.join(self.workshop_dir, "123456")
        mod_src = os.path.join(item_dir, "mods", "CoolMod", "42")
        os.makedirs(mod_src, exist_ok=True)

        with open(os.path.join(mod_src, "mod.info"), "w", encoding="utf-8") as f:
            f.write("id=CoolModId\nname=Cool Mod\n")

        with open(os.path.join(mod_src, "test.lua"), "w", encoding="utf-8") as f:
            f.write("-- Lua script\n")

        deployed = ModManifestManager.deploy_workshop_item_to_local_mods(item_dir, self.local_mods_dir)
        self.assertIn("CoolModId", deployed)

        dest_folder = os.path.join(self.local_mods_dir, "CoolModId")
        self.assertTrue(os.path.exists(dest_folder))
        self.assertTrue(os.path.exists(os.path.join(dest_folder, "mod.info")))
        self.assertTrue(os.path.exists(os.path.join(dest_folder, "test.lua")))


if __name__ == "__main__":
    unittest.main()
