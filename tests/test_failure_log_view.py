import unittest
import os
import shutil
import tempfile
from app.models.audit_result import AuditResult
from app.models.server_audit_result import ServerAuditResult
from app.models.log_inspector import LogInspectionResult, ModRuntimeStatus
from app.views.failure_log_view import FailureCategory, ModFailureEntry, FailureLogGenerator


class TestFailureLogView(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        self.assertEqual(FailureLogGenerator._sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(FailureLogGenerator._sanitize_filename("mod:with/bad\\chars"), "mod_with_bad_chars")
        self.assertEqual(FailureLogGenerator._sanitize_filename("[J&G] Umbrella Corp [B42/41]"), "[J&G] Umbrella Corp [B42_41]")

    def test_mod_failure_entry_formatting(self):
        entry = ModFailureEntry(
            mod_id="test_mod",
            mod_name="Test Mod Name",
            category=FailureCategory.CRASH,
            mode="SINGLEPLAYER",
            reasons=["Incompatibilidade de animações FBX com Build 42."],
            suggested_fix="Remova o mod.",
            runtime_evidence="Jassimp crash at frame 42"
        )
        content = entry.format_log_content()
        self.assertIn("RELATÓRIO DE FALHA DE MOD — [SINGLEPLAYER] [VERMELHO] — MOD: test_mod", content)
        self.assertIn("MOD ID:       test_mod", content)
        self.assertIn("MODO:         SINGLEPLAYER", content)
        self.assertIn("CRASH", content)
        self.assertIn("Jassimp crash at frame 42", content)
        self.assertIn("MOD QUEBRADO OU INCOMPATÍVEL", content)

    def test_mod_failure_entry_categories(self):
        # CONFIG_ERROR
        cfg_entry = ModFailureEntry(
            mod_id="cfg_mod",
            mod_name="Config Mod",
            category=FailureCategory.CONFIG_ERROR,
            mode="MULTIPLAYER",
            reasons=["Falta Workshop ID"]
        )
        self.assertIn("ERRO DE CONFIGURAÇÃO (PROBLEMA SEU / CONFIG)", cfg_entry.format_log_content())

        # BUILD_FAIL
        bf_entry = ModFailureEntry(
            mod_id="bf_mod",
            mod_name="Build Fail Mod",
            category=FailureCategory.BUILD_FAIL,
            mode="MULTIPLAYER",
            reasons=["Erro de sintaxe Lua"]
        )
        self.assertIn("FALHA DE COMPILAÇÃO / SINTAXE", bf_entry.format_log_content())

        # NO_LOAD
        nl_entry = ModFailureEntry(
            mod_id="nl_mod",
            mod_name="No Load Mod",
            category=FailureCategory.NO_LOAD,
            mode="SINGLEPLAYER",
            reasons=["VFS carregou mas Lua não executou"]
        )
        self.assertIn("MOD NÃO CARREGOU", nl_entry.format_log_content())

    def test_generate_sp_logs(self):
        result = AuditResult()
        result.errors = [
            "[MOD INCOMPATÍVEL COM B42 - CRASH NATIVO JASSIMP] Mod detectado: broken_car_mod (Usa animações FBX incompatíveis).",
            "[CONFLITO DECLARADO (incompatible=)] Mod 'conflict_mod_a' conflita com 'conflict_mod_b'."
        ]
        result.rejected_mod_ids = ["tsarslib"]

        log_res = LogInspectionResult(has_logs=True)
        log_res.mod_runtime_statuses["script_err_mod"] = ModRuntimeStatus(
            mod_id="script_err_mod",
            script_errors=["Error loading media/scripts/items.txt: Unbalanced bracket"]
        )

        generated = FailureLogGenerator.generate_sp_logs(result, log_res, self.test_dir)
        self.assertGreaterEqual(len(generated), 3)

        filenames = [os.path.basename(p) for p in generated]
        self.assertIn("VERMELHO_FALHA_SP_broken_car_mod.txt", filenames)
        self.assertIn("AMARELO_FALHA_SP_conflict_mod_a.txt", filenames)
        self.assertIn("VERMELHO_FALHA_SP_tsarslib.txt", filenames)
        self.assertIn("VERMELHO_FALHA_SP_script_err_mod.txt", filenames)

        with open(os.path.join(self.test_dir, "VERMELHO_FALHA_SP_broken_car_mod.txt"), encoding="utf-8") as f:
            content = f.read()
            self.assertIn("SINGLEPLAYER", content)
            self.assertIn("broken_car_mod", content)
            self.assertIn("CRASH", content)
            self.assertIn("VERMELHO", content)

    def test_generate_mp_logs(self):
        srv_result = ServerAuditResult()
        srv_result.red_mods = [
            ("fatal_mod", "Fatal Mod", "[CRASH] Incompatível com o servidor"),
            ("lua_fail_mod", "Lua Fail Mod", "[FALHA DE COMPILAÇÃO] Erro de sintaxe")
        ]
        srv_result.yellow_mods = [
            ("missing_ws_mod", "Missing WS Mod", "Falta Workshop ID")
        ]
        srv_result.build_failures = [
            ("syntax_mod", "Syntax Mod", ["media/lua/test.lua: unclosed parenthesis"])
        ]

        generated = FailureLogGenerator.generate_mp_logs(srv_result, self.test_dir)
        self.assertGreaterEqual(len(generated), 4)

        filenames = [os.path.basename(p) for p in generated]
        self.assertIn("VERMELHO_FALHA_MP_fatal_mod.txt", filenames)
        self.assertIn("VERMELHO_FALHA_MP_lua_fail_mod.txt", filenames)
        self.assertIn("AMARELO_FALHA_MP_missing_ws_mod.txt", filenames)
        self.assertIn("VERMELHO_FALHA_MP_syntax_mod.txt", filenames)

        with open(os.path.join(self.test_dir, "VERMELHO_FALHA_MP_syntax_mod.txt"), encoding="utf-8") as f:
            content = f.read()
            self.assertIn("MULTIPLAYER", content)
            self.assertIn("syntax_mod", content)
            self.assertIn("FALHA DE COMPILAÇÃO", content)
            self.assertIn("unclosed parenthesis", content)
            self.assertIn("VERMELHO", content)


if __name__ == "__main__":
    unittest.main()
