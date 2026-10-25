import os
import tempfile
import unittest
from app.models.server_config import ServerConfig

class TestServerConfig(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.server_ini = os.path.join(self.temp_dir.name, "Server", "servertest.ini")
        self.host_ini = os.path.join(self.temp_dir.name, "Lua", "host.ini")
        os.makedirs(os.path.dirname(self.server_ini), exist_ok=True)
        os.makedirs(os.path.dirname(self.host_ini), exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_mods_stripping_slashes(self):
        """Verifies that leading/trailing slashes and backslashes in Mods= are stripped."""
        ini_content = "Mods=\\ModAlpha;\\ModBeta;/ModGamma;ModDelta;\nWorkshopItems=111;222;\n"
        with open(self.server_ini, "w", encoding="utf-8") as f:
            f.write(ini_content)

        cfg = ServerConfig(self.server_ini, self.host_ini)
        mods = cfg.load_mods()
        self.assertEqual(mods, ["ModAlpha", "ModBeta", "ModGamma", "ModDelta"])

    def test_load_and_save_maps_with_muldraugh_last(self):
        """Verifies that custom maps are loaded and always saved before Muldraugh, KY."""
        ini_content = "Mods=ModA;\nWorkshopItems=123;\nMap=CustomIsland;Muldraugh, KY;\n"
        with open(self.server_ini, "w", encoding="utf-8") as f:
            f.write(ini_content)

        cfg = ServerConfig(self.server_ini, self.host_ini)
        maps = cfg.load_maps()
        self.assertIn("CustomIsland", maps)
        self.assertEqual(maps[-1], "Muldraugh, KY")

        # Now save with an additional map
        cfg.save_server_mods(
            mods=["ModA", "ModB"],
            workshop_items=["123", "456"],
            maps=["CustomIsland", "NewCheckpoint", "Muldraugh, KY"]
        )

        with open(self.server_ini, "r", encoding="utf-8") as f:
            saved_content = f.read()

        self.assertIn("Mods=ModA;ModB;\n", saved_content)
        self.assertIn("WorkshopItems=123;456;\n", saved_content)
        self.assertIn("Map=CustomIsland;NewCheckpoint;Muldraugh, KY;\n", saved_content)

    def test_host_memory_read_and_write(self):
        """Verifies reading and writing memory in host.ini."""
        cfg = ServerConfig(self.server_ini, self.host_ini)
        cfg.set_host_memory(4096)
        self.assertEqual(cfg.load_host_memory(), 4096)

        cfg.set_host_memory(8192)
        self.assertEqual(cfg.load_host_memory(), 8192)

if __name__ == "__main__":
    unittest.main()
