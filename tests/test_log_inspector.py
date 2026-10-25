import os
import tempfile
import unittest
from app.models.log_inspector import LogInspector, ModRuntimeStatus

class TestLogInspector(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_console_log(self, content: str) -> str:
        console_path = os.path.join(self.temp_dir.name, "console.txt")
        with open(console_path, "w", encoding="utf-8") as f:
            f.write(content)
        return console_path

    def test_boot_successful_and_clean_exit(self):
        """Verifies that normal game startup and clean exit are detected as SUCCESS."""
        log_content = """
        LOG  : Mod          f:0> loading TestModA
        LOG  : Mod          f:0> loading TestModB
        LOG  : General      f:0> Arranque do jogo
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : Lua          f:120> : [SurvivorBriefing] briefing shown for player 0
        LOG  : General      f:232> Saving GlobalModData
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertTrue(res.has_logs)
        self.assertTrue(res.boot_successful)
        self.assertTrue(res.clean_exit)
        self.assertFalse(res.fatal_crash)
        self.assertIn("TestModA", res.mods_loaded)
        self.assertIn("TestModB", res.mods_loaded)
        self.assertIn("Sessão executada com sucesso", res.diagnostic_summary)

    def test_fatal_crash_detected(self):
        """Verifies that native fatal exceptions (like access violation or OOM) are caught."""
        log_content = """
        LOG  : General      f:0> Loading textures...
        ERROR: General      f:0> EXCEPTION_ACCESS_VIOLATION in native module jassimp.dll
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertTrue(res.has_logs)
        self.assertTrue(res.fatal_crash)
        self.assertFalse(res.clean_exit)
        self.assertIn("CRASH REAL DETECTADO", res.diagnostic_summary)

    def test_handled_exceptions_and_overrides(self):
        """Verifies that non-fatal duplicate registrations and VFS overrides are counted but not fatal."""
        log_content = """
        LOG  : Mod          f:0> loading CraftEnginePartsModerate
        LOG  : Mod          f:0> mod "CraftEnginePartsModerate" overrides media/recipes.txt
        ERROR: General      f:0> Exception: Tried to register duplicate object: vfe:bullets_762 in: ammo_type
        LOG  : General      f:0> Arranque do jogo
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertTrue(res.boot_successful)
        self.assertFalse(res.fatal_crash)
        self.assertEqual(res.overrides_count, 1)
        self.assertEqual(res.handled_errors_count, 1)

    def test_missing_console_log_handled(self):
        """Verifies safe handling when console.txt does not exist."""
        empty_dir = os.path.join(self.temp_dir.name, "empty")
        os.makedirs(empty_dir, exist_ok=True)
        res = LogInspector.inspect(empty_dir)

        self.assertFalse(res.has_logs)
        self.assertIn("Nenhum arquivo console.txt", res.diagnostic_summary)

    # ─── NEW: Per-Mod Runtime Execution Tests ───

    def test_per_mod_vfs_loading_tracked(self):
        """Verifies that each mod loaded via VFS is individually tracked."""
        log_content = """
        LOG  : Mod          f:0> loading ModAlpha
        LOG  : Mod          f:0> loading ModBeta
        LOG  : Mod          f:0> loading ModGamma
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertEqual(res.total_vfs_loaded, 3)
        self.assertIn("ModAlpha", res.mods_loaded)
        self.assertIn("ModBeta", res.mods_loaded)
        self.assertIn("ModGamma", res.mods_loaded)
        # All three have statuses tracked
        self.assertIn("ModAlpha", res.mod_runtime_statuses)
        self.assertTrue(res.mod_runtime_statuses["ModAlpha"].vfs_loaded)

    def test_lua_execution_detected_via_bracket_pattern(self):
        """Verifies that Lua execution is attributed to mod via [ModName] pattern."""
        log_content = """
        LOG  : Mod          f:0> loading Railroader
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : Lua          f:0> :	[Railroader] RR_TrainEntity.lua: loading...
        LOG  : Lua          f:0> :	[Railroader] RR_TrainEntity.lua: loaded OK
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertIn("Railroader", res.mods_with_lua_execution)
        self.assertTrue(res.mod_runtime_statuses["Railroader"].lua_executed)
        self.assertTrue(len(res.mod_runtime_statuses["Railroader"].lua_evidence) > 0)
        self.assertEqual(res.total_lua_confirmed, 1)

    def test_lua_execution_detected_via_modname_prefix(self):
        """Verifies Lua execution detection via ModName: action prefix pattern."""
        log_content = """
        LOG  : Mod          f:0> loading ReducedWoodWeight25p41
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : Lua          f:0> :	ReducedWoodWeight25p41: Modified weight of Firewood from 1.5 to 0.38
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        # The mod name prefix should match
        self.assertIn("ReducedWoodWeight25p41", res.mods_with_lua_execution)
        self.assertTrue(res.mod_runtime_statuses["ReducedWoodWeight25p41"].lua_executed)

    def test_silent_mod_detected(self):
        """Verifies that a mod loaded by VFS but with no Lua output is flagged as silent."""
        log_content = """
        LOG  : Mod          f:0> loading SilentTextureMod
        LOG  : Mod          f:0> loading ActiveLuaMod
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : Lua          f:0> :	[ActiveLuaMod] initialized OK
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        # SilentTextureMod is VFS loaded but has no Lua evidence
        self.assertIn("SilentTextureMod", res.mods_without_lua_execution)
        self.assertNotIn("SilentTextureMod", res.mods_with_lua_execution)
        self.assertEqual(res.total_silent_mods, 1)
        self.assertEqual(res.total_lua_confirmed, 1)

        # ActiveLuaMod has Lua evidence
        self.assertIn("ActiveLuaMod", res.mods_with_lua_execution)

    def test_mod_with_path_style_id(self):
        """Verifies that mods loaded with path-style IDs (e.g., 12345/ModName) are handled."""
        log_content = """
        LOG  : Mod          f:0> loading 2874163136/CaptainJuezo1_WIP_B42
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertIn("CaptainJuezo1_WIP_B42", res.mods_loaded)
        self.assertTrue(res.mod_runtime_statuses["CaptainJuezo1_WIP_B42"].vfs_loaded)

    def test_vfs_overrides_attributed_to_mod(self):
        """Verifies that VFS overrides are counted per-mod."""
        log_content = """
        LOG  : Mod          f:0> loading 1VCESTANDARD
        LOG  : Mod          f:0> mod "1VCESTANDARD" overrides media/textures/clothes/hat/baseballcapblue.png
        LOG  : Mod          f:0> mod "1VCESTANDARD" overrides media/textures/clothes/hat/baseballcapred.png
        LOG  : Mod          f:0> mod "1VCESTANDARD" overrides media/clothing/clothingitems/hat_baseballcap.xml
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertEqual(res.mod_runtime_statuses["1VCESTANDARD"].vfs_overrides, 3)
        self.assertEqual(res.overrides_count, 3)

    def test_registry_errors_attributed(self):
        """Verifies that Java registry errors (duplicates) are attributed to the correct mod."""
        log_content = """
        LOG  : Mod          f:0> loading VFExpansionReduxb42
        LOG  : General      f:0> VehiclesDB2.init() start
        ERROR: General      f:0> Lua((MOD:Vanilla Firearms Expansion)).registries.lua> Exception thrown
        	java.lang.IllegalArgumentException: Tried to register duplicate object: vfe:bullets_762 in: ammo_type
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertEqual(res.handled_errors_count, 1)
        self.assertTrue(len(res.registry_errors) > 0)

    def test_script_errors_detected(self):
        """Verifies that recipe/script errors are captured from logs."""
        log_content = """
        LOG  : Mod          f:0> loading CJ_WeaponPack
        LOG  : General      f:0> VehiclesDB2.init() start
        ERROR: General      f:0 at Recipe.Load> Could not assign [key]: 'Result' : 'CJ_SKS_Sawn'.
        ERROR: General      f:0 at Recipe.Load> Could not assign [key]: 'Sound' : 'Sawing'.
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertEqual(len(res.script_errors), 2)
        self.assertTrue(res.boot_successful)

    def test_diagnostic_includes_lua_ratio(self):
        """Verifies that the diagnostic summary includes the Lua execution ratio."""
        log_content = """
        LOG  : Mod          f:0> loading ModA
        LOG  : Mod          f:0> loading ModB
        LOG  : Mod          f:0> loading ModC
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : Lua          f:0> :	[ModA] init OK
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        # Should mention 1/3 mods with Lua execution
        self.assertIn("1/3", res.diagnostic_summary)
        self.assertIn("com execução Lua confirmada", res.diagnostic_summary)

    def test_detailed_diagnostics_for_silent_mods(self):
        """Verifies that detailed diagnostics are generated when silent mods exist."""
        log_content = """
        LOG  : Mod          f:0> loading SilentMod1
        LOG  : Mod          f:0> loading SilentMod2
        LOG  : Mod          f:0> loading ActiveMod
        LOG  : General      f:0> VehiclesDB2.init() start
        LOG  : Lua          f:0> :	[ActiveMod] running
        LOG  : General      f:232> GameThread exited.
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertEqual(res.total_silent_mods, 2)
        self.assertTrue(len(res.detailed_diagnostics) > 0)
        self.assertTrue(any("SEM EXECUÇÃO LUA" in d for d in res.detailed_diagnostics))

    def test_mod_runtime_status_property(self):
        """Verifies ModRuntimeStatus.status property returns correct classification."""
        # EXECUTANDO: loaded + lua executed, no errors
        s1 = ModRuntimeStatus(mod_id="Test1", vfs_loaded=True, lua_executed=True)
        self.assertEqual(s1.status, "EXECUTANDO")

        # PARCIAL: loaded + lua executed, with script errors
        s2 = ModRuntimeStatus(mod_id="Test2", vfs_loaded=True, lua_executed=True,
                              script_errors=["error1"])
        self.assertEqual(s2.status, "PARCIAL (erros de script)")

        # CARREGADO MAS SEM EXECUÇÃO LUA
        s3 = ModRuntimeStatus(mod_id="Test3", vfs_loaded=True, lua_executed=False)
        self.assertEqual(s3.status, "CARREGADO MAS SEM EXECUÇÃO LUA")

        # DESCONHECIDO
        s4 = ModRuntimeStatus(mod_id="Test4", vfs_loaded=False, lua_executed=False)
        self.assertEqual(s4.status, "DESCONHECIDO")

    def test_oom_crash_detected(self):
        """Verifies that OutOfMemoryError is detected as fatal crash."""
        log_content = """
        LOG  : General      f:0> VehiclesDB2.init() start
        ERROR: General      f:0> java.lang.OutOfMemoryError: Java heap space
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertTrue(res.fatal_crash)
        self.assertIn("OutOfMemoryError", res.crash_reason)

    def test_jassimp_crash_detected(self):
        """Verifies that Jassimp bad allocation is detected as fatal crash."""
        log_content = """
        LOG  : General      f:0> VehiclesDB2.init() start
        ERROR: General      f:0> bad allocation in Jassimp.aiImportFile
        """
        self._create_console_log(log_content)
        res = LogInspector.inspect(self.temp_dir.name)

        self.assertTrue(res.fatal_crash)
        self.assertIn("bad allocation", res.crash_reason)


if __name__ == "__main__":
    unittest.main()
