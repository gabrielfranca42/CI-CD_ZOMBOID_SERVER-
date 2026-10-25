import os
import tempfile
import unittest
from app.models.build_validator import BuildValidator

class TestBuildValidator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_temp_file(self, filename: str, content: str) -> str:
        filepath = os.path.join(self.temp_dir.name, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_valid_lua_with_elseif_chains(self):
        """Verifies that chains of elseif do not trigger false positive block imbalance."""
        lua_code = """
        function OnFillWorldObjectContextMenu(player, context, worldobjects, test)
            local item = getPlayerInventory(player)
            if item:isBroken() then
                context:addOption("Reparar", worldobjects, onRepair)
            elseif item:hasTag("Sharp") then
                context:addOption("Afiar", worldobjects, onSharpen)
            elseif item:hasTag("Blunt") then
                context:addOption("Limpar", worldobjects, onClean)
            else
                context:addOption("Examinar", worldobjects, onExamine)
            end
        end
        """
        fpath = self._create_temp_file("test_elseif.lua", lua_code)
        err = BuildValidator.validate_lua_syntax(fpath)
        self.assertIsNone(err, f"Valid Lua with elseif was falsely rejected: {err}")

    def test_valid_lua_with_nested_blocks(self):
        """Verifies loops, functions, and repeat-until blocks parse correctly."""
        lua_code = """
        local function countToTen()
            local i = 0
            while i < 10 do
                i = i + 1
            end
            for k = 1, 5 do
                print(k)
            end
            repeat
                i = i - 1
            until i == 0
            return i
        end
        """
        fpath = self._create_temp_file("test_blocks.lua", lua_code)
        err = BuildValidator.validate_lua_syntax(fpath)
        self.assertIsNone(err, f"Valid nested blocks were falsely rejected: {err}")

    def test_broken_lua_detected(self):
        """Verifies that an unclosed if block is correctly detected as an error."""
        lua_code = """
        function BrokenFunction()
            if true then
                print("Missing end for function!")
        end
        """
        fpath = self._create_temp_file("test_broken.lua", lua_code)
        err = BuildValidator.validate_lua_syntax(fpath)
        self.assertIsNotNone(err)
        self.assertIn("Desbalanceamento de blocos Lua", err)

    def test_lua_comments_and_strings_ignored(self):
        """Verifies keywords inside comments and strings do not corrupt block balance."""
        lua_code = """
        --[[ 
            if condition then
            function insideComment()
            end
        ]]
        local msg = "if then end function repeat until"
        local multiline = [[ do end ]]
        function RealFunction()
            -- do nothing
            return true
        end
        """
        fpath = self._create_temp_file("test_strings.lua", lua_code)
        err = BuildValidator.validate_lua_syntax(fpath)
        self.assertIsNone(err, f"Keywords in comments/strings caused false positive: {err}")

    def test_pz_script_balanced_braces(self):
        """Verifies valid Project Zomboid item script parses without error."""
        script_code = """
        module Base
        {
            item WaterBottle
            {
                Type = Drainable,
                DisplayName = Water Bottle,
                Icon = WaterBottleFull,
                Weight = 1.0,
            }
            recipe Empty Bottle
            {
                WaterBottle,
                Result: EmptyBottle=1,
                Time: 10.0,
            }
        }
        """
        fpath = self._create_temp_file("media/scripts/items.txt", script_code)
        err = BuildValidator.validate_script_files(fpath)
        self.assertIsNone(err, f"Valid PZ script was rejected: {err}")

    def test_pz_script_unbalanced_braces_detected(self):
        """Verifies missing closing brace in script file is detected."""
        script_code = """
        module Base
        {
            item BrokenItem
            {
                Type = Normal,
                Weight = 1.0,
        }
        """
        fpath = self._create_temp_file("media/scripts/broken.txt", script_code)
        err = BuildValidator.validate_script_files(fpath)
        self.assertIsNotNone(err)
        self.assertIn("Desbalanceamento de chaves", err)

    def test_pz_script_braces_in_strings(self):
        """Verifies braces inside quoted strings do not produce false positive errors."""
        script_code = """
        module Base
        {
            item SpecialNote
            {
                Type = Literature,
                DisplayName = "Note with {brackets} inside",
                Tooltip = "Format: {0}",
            }
        }
        """
        fpath = self._create_temp_file("media/scripts/strings.txt", script_code)
        err = BuildValidator.validate_script_files(fpath)
        self.assertIsNone(err, f"Braces inside quotes caused false positive: {err}")

if __name__ == "__main__":
    unittest.main()
