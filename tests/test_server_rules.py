import unittest
from app.models.mod import Mod
from app.models.system_specs import SystemSpecs
from app.models.server_config import ServerConfig
from app.models.server_rules import ServerRulesEngine

class DummyServerConfig:
    def __init__(self, mods, workshop_items, maps, host_mem=2048):
        self._mods = mods
        self._ws = workshop_items
        self._maps = maps
        self._mem = host_mem

    def load_mods(self):
        return self._mods

    def load_workshop_items(self):
        return self._ws

    def load_maps(self):
        return self._maps

    def load_host_memory(self):
        return self._mem

class DummyWorkshop:
    def __init__(self, mod_dict):
        self.mods = mod_dict

    def get_mod(self, mid: str):
        return self.mods.get(mid)

class TestServerRules(unittest.TestCase):

    def setUp(self):
        self.specs = SystemSpecs(
            total_ram_gb=16.0,
            free_ram_gb=8.0,
            total_pagefile_gb=8.0,
            free_pagefile_gb=6.0,
            commit_limit_gb=24.0,
            game_version="Build 42.21.0",
            workshop_dir="dummy/ws",
            user_zomboid_dir="dummy/pz",
            game_dir="dummy/game"
        )
        self.engine = ServerRulesEngine(self.specs)

    def test_missing_map_folder_detected(self):
        """Verifies that a server mod with custom map folder not in Map= is detected."""
        map_mod = Mod(
            id="OverhaulMap",
            name="Overhaul Map",
            mod_folder="",
            workshop_id="777888",
            map_folders=["OverhaulCellFolder"]
        )
        workshop = DummyWorkshop({"OverhaulMap": map_mod})

        # Server configuration missing OverhaulCellFolder from Map=
        server_cfg = DummyServerConfig(
            mods=["OverhaulMap"],
            workshop_items=["777888"],
            maps=["Muldraugh, KY"]
        )

        result = self.engine.evaluate(server_cfg, workshop)
        self.assertTrue(len(result.missing_map_mappings) > 0)
        self.assertIn("OverhaulCellFolder", result.missing_map_mappings[0])

    def test_tilepacks_not_treated_as_guaranteed_crash(self):
        """Verifies that standard tilepacks are not falsely categorized as RED crash mods."""
        tile_mod = Mod(
            id="melos_tiles_for_miles_pack",
            name="Melo's Tiles For Miles",
            mod_folder="",
            workshop_id="333444",
            depthmap_count=50
        )
        workshop = DummyWorkshop({"melos_tiles_for_miles_pack": tile_mod})

        server_cfg = DummyServerConfig(
            mods=["melos_tiles_for_miles_pack"],
            workshop_items=["333444"],
            maps=["Muldraugh, KY"]
        )

        result = self.engine.evaluate(server_cfg, workshop)
        # Should not be in red_mods
        red_ids = [r[0] for r in result.red_mods]
        self.assertNotIn("melos_tiles_for_miles_pack", red_ids)

    def test_real_crash_mod_rejected(self):
        """Verifies that genuine B42 crashers like amclub are flagged as RED."""
        amclub_mod = Mod(
            id="amclub",
            name="Autotsar Motorclub",
            mod_folder="",
            workshop_id="111222"
        )
        workshop = DummyWorkshop({"amclub": amclub_mod})

        server_cfg = DummyServerConfig(
            mods=["amclub"],
            workshop_items=["111222"],
            maps=["Muldraugh, KY"]
        )

        result = self.engine.evaluate(server_cfg, workshop)
        red_ids = [r[0] for r in result.red_mods]
        self.assertIn("amclub", red_ids)
        self.assertFalse(result.is_green)

if __name__ == "__main__":
    unittest.main()
