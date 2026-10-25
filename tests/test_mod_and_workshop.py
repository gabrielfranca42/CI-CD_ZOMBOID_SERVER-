import os
import tempfile
import unittest
from app.models.mod import Mod
from app.models.workshop import Workshop

class TestModAndWorkshop(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mod_info_build42_tags_parsing(self):
        """Verifies parsing of versionMin, versionMax, incompatible, and multiple require/pack lines."""
        mod_info_content = """
        name=Advanced Tactical Gear B42
        id=AdvTacticalGear
        description=Custom gear for Build 42.
        versionMin=42.0.0
        versionMax=42.99.0
        modversion=2.5.1
        require=BaseMod,FrameworkB42
        require=ExtraTiles;UtilityLib
        pack=tactical_tiles,gear_textures
        incompatible=LegacyTacticalGear;ConflictingMod
        """
        mod_folder = os.path.join(self.temp_dir.name, "mods", "AdvTacticalGear", "42")
        os.makedirs(mod_folder, exist_ok=True)
        mod_info_file = os.path.join(mod_folder, "mod.info")
        with open(mod_info_file, "w", encoding="utf-8") as f:
            f.write(mod_info_content)

        mod = Mod.from_mod_info(mod_info_file, workshop_id="123456789")
        self.assertIsNotNone(mod)
        self.assertEqual(mod.id, "AdvTacticalGear")
        self.assertEqual(mod.name, "Advanced Tactical Gear B42")
        self.assertEqual(mod.version_min, "42.0.0")
        self.assertEqual(mod.version_max, "42.99.0")
        self.assertEqual(mod.mod_version, "2.5.1")
        self.assertEqual(mod.target_version, "42")

        # Check multi-line require parsing
        expected_reqs = ["BaseMod", "FrameworkB42", "ExtraTiles", "UtilityLib"]
        for r in expected_reqs:
            self.assertIn(r, mod.require)

        # Check pack parsing
        self.assertIn("tactical_tiles", mod.pack)
        self.assertIn("gear_textures", mod.pack)

        # Check incompatible parsing
        self.assertIn("LegacyTacticalGear", mod.incompatible)
        self.assertIn("ConflictingMod", mod.incompatible)

    def test_map_folders_discovery(self):
        """Verifies that custom map folders inside media/maps/ are discovered."""
        mod_folder = os.path.join(self.temp_dir.name, "mods", "CustomMapMod", "common")
        maps_dir = os.path.join(mod_folder, "media", "maps", "NewLouisville")
        os.makedirs(maps_dir, exist_ok=True)
        mod_info_file = os.path.join(mod_folder, "mod.info")
        with open(mod_info_file, "w", encoding="utf-8") as f:
            f.write("name=Custom Map Mod\nid=CustomMapMod\n")

        mod = Mod.from_mod_info(mod_info_file, workshop_id="987654321")
        self.assertIsNotNone(mod)
        self.assertEqual(mod.target_version, "common")
        self.assertIn("NewLouisville", mod.map_folders)

    def test_workshop_scan_build42_priority(self):
        """Verifies that Workshop.scan prioritizes Build 42 (42/) over legacy root mod.info."""
        ws_root = os.path.join(self.temp_dir.name, "workshop_content")
        item_folder = os.path.join(ws_root, "555123")

        # 1. Legacy version at root
        legacy_dir = os.path.join(item_folder, "mods", "MyAwesomeMod")
        os.makedirs(legacy_dir, exist_ok=True)
        with open(os.path.join(legacy_dir, "mod.info"), "w", encoding="utf-8") as f:
            f.write("name=My Awesome Mod (Legacy B41)\nid=MyAwesomeMod\nmodversion=1.0\n")

        # 2. Modern B42 version in 42/
        b42_dir = os.path.join(legacy_dir, "42")
        os.makedirs(b42_dir, exist_ok=True)
        with open(os.path.join(b42_dir, "mod.info"), "w", encoding="utf-8") as f:
            f.write("name=My Awesome Mod (B42 Native)\nid=MyAwesomeMod\nmodversion=2.0\nversionMin=42.0.0\n")

        workshop = Workshop(ws_root)
        mods = workshop.scan()

        self.assertIn("MyAwesomeMod", mods)
        chosen = mods["MyAwesomeMod"]
        # The B42 version should have taken precedence
        self.assertEqual(chosen.name, "My Awesome Mod (B42 Native)")
        self.assertEqual(chosen.target_version, "42")
        self.assertEqual(chosen.version_min, "42.0.0")

if __name__ == "__main__":
    unittest.main()
