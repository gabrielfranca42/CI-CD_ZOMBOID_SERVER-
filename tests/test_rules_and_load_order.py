import unittest
from app.models.mod import Mod
from app.models.workshop import Workshop
from app.models.system_specs import SystemSpecs
from app.models.rules import RulesEngine

class DummyWorkshop:
    def __init__(self, mod_dict):
        self.mods = mod_dict

    def get_mod(self, mid: str):
        return self.mods.get(mid)

class TestRulesAndLoadOrder(unittest.TestCase):

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
        self.engine = RulesEngine(self.specs)

    def test_topological_load_order(self):
        """Verifies that dependencies are ordered before dependent mods."""
        # Mod C requires Mod B; Mod B requires Mod A.
        # Initial disordered list: ["ModC", "ModA", "ModB"]
        mod_a = Mod(id="ModA", name="Framework A", mod_folder="")
        mod_b = Mod(id="ModB", name="Library B", mod_folder="", require=["ModA"])
        mod_c = Mod(id="ModC", name="Feature C", mod_folder="", require=["ModB"])

        workshop = DummyWorkshop({"ModA": mod_a, "ModB": mod_b, "ModC": mod_c})

        initial_order = ["ModC", "ModA", "ModB"]
        ordered = RulesEngine.compute_recommended_load_order(initial_order, workshop)

        # ModA must be before ModB, and ModB must be before ModC
        self.assertLess(ordered.index("ModA"), ordered.index("ModB"))
        self.assertLess(ordered.index("ModB"), ordered.index("ModC"))

    def test_native_incompatible_rule(self):
        """Verifies that native incompatible tags trigger conflict errors."""
        mod_a = Mod(id="ModA", name="Mod A", mod_folder="", incompatible=["ModB"])
        mod_b = Mod(id="ModB", name="Mod B", mod_folder="")

        workshop = DummyWorkshop({"ModA": mod_a, "ModB": mod_b})
        result = self.engine.evaluate(["ModA", "ModB"], workshop)

        self.assertFalse(result.is_green)
        self.assertTrue(any("incompatible=" in err for err in result.errors))

    def test_tilepack_dependency_protection(self):
        """Verifies that tile packs with high depthmaps are protected if required by active map mods."""
        # Low commit specs to trigger hardware threshold
        specs_low = SystemSpecs(
            total_ram_gb=8.0,
            free_ram_gb=2.0,
            total_pagefile_gb=1.0,
            free_pagefile_gb=0.5,
            commit_limit_gb=9.0,
            game_version="Build 42.21.0",
            workshop_dir="dummy/ws",
            user_zomboid_dir="dummy/pz",
            game_dir="dummy/game"
        )
        engine_low = RulesEngine(specs_low)

        # Heavy tile pack required by a map
        tile_pack = Mod(
            id="simonMDsTiles",
            name="Simon Mds Tiles",
            mod_folder="",
            depthmap_count=100,
            depthmap_size_mb=25.0
        )
        map_mod = Mod(
            id="IslandMap",
            name="Island Map",
            mod_folder="",
            require=["simonMDsTiles"]
        )

        workshop = DummyWorkshop({"simonMDsTiles": tile_pack, "IslandMap": map_mod})
        result = engine_low.evaluate(["IslandMap", "simonMDsTiles"], workshop)

        # simonMDsTiles must NOT be in rejected_mod_ids because IslandMap requires it
        self.assertNotIn("simonMDsTiles", result.rejected_mod_ids)
        self.assertTrue(any("TILEPACK PESADO PROTEGIDO" in w for w in result.warnings))

    def test_vfe_and_craft_engine_parts_are_non_blocking_warnings(self):
        """Verifies that VFE duplicate registrations and multiple CraftEngineParts do not block SP pipeline."""
        mod_vfe3 = Mod(id="VFExpansion3", name="VFE 3 Legacy", mod_folder="")
        mod_vfe_redux = Mod(id="VFExpansionReduxb42", name="VFE Redux B42", mod_folder="")
        mod_cep1 = Mod(id="CraftEngineParts", name="CEP Standard", mod_folder="")
        mod_cep2 = Mod(id="CraftEnginePartsModerate", name="CEP Moderate", mod_folder="")

        workshop = DummyWorkshop({
            "VFExpansion3": mod_vfe3,
            "VFExpansionReduxb42": mod_vfe_redux,
            "CraftEngineParts": mod_cep1,
            "CraftEnginePartsModerate": mod_cep2
        })

        result = self.engine.evaluate(["VFExpansion3", "VFExpansionReduxb42", "CraftEngineParts", "CraftEnginePartsModerate"], workshop)

        # Neither should produce blocking errors
        vfe_errors = [e for e in result.errors if "VFE DUPLICADO" in e]
        cep_errors = [e for e in result.errors if "CraftEngineParts" in e]
        self.assertEqual(len(vfe_errors), 0, "VFE was falsely treated as fatal error")
        self.assertEqual(len(cep_errors), 0, "CraftEngineParts was falsely treated as fatal error")

        # Both should produce informative warnings
        self.assertTrue(any("VFE DUPLICADO" in w for w in result.warnings))
        self.assertTrue(any("CraftEngineParts" in w for w in result.warnings))

if __name__ == "__main__":
    unittest.main()
