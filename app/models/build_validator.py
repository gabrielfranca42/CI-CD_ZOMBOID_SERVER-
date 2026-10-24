import os
import re
from typing import List, Tuple, Dict, Optional
from .mod import Mod

class BuildValidator:
    """Performs static build and compilation verification on mods (Lua syntax, scripts, balance)."""

    @staticmethod
    def validate_lua_syntax(file_path: str) -> Optional[str]:
        """Simple syntax and integrity scanner for a Lua script."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return f"Erro de leitura: {e}"

        if "\x00" in content:
            return "Arquivo corrompido com bytes nulos."

        lines = content.splitlines()
        block_starts = 0
        block_ends = 0

        in_multiline_comment = False
        in_multiline_string = False

        for i, line in enumerate(lines, 1):
            s = line.strip()

            # Handle multi-line comments --[[ ... ]]
            if in_multiline_comment:
                if "]]" in s:
                    in_multiline_comment = False
                continue
            if "--[[" in s:
                in_multiline_comment = True
                continue

            # Handle multi-line strings [[ ... ]]
            if in_multiline_string:
                if "]]" in s:
                    in_multiline_string = False
                continue

            # Skip single-line comments
            if s.startswith("--"):
                continue

            # Remove inline comments (-- ...) before analysis
            s_no_comment = re.sub(r'--(?!\[).*$', '', s)

            # Strip string literals to avoid counting keywords inside quotes
            s_clean = re.sub(r'\"(\\.|[^\"])*\"', '', s_no_comment)
            s_clean = re.sub(r"'(\\.|[^'])*'", '', s_clean)

            # Detect start of multi-line string on this line
            if "[[" in s_clean and not s_clean.strip().startswith("--"):
                # Only if it's not followed by ]] on the same line
                after_bracket = s_clean.split("[[", 1)[1] if "[[" in s_clean else ""
                if "]]" not in after_bracket:
                    in_multiline_string = True

            # Count block keywords using word boundaries
            tokens = re.findall(r'\b(function|then|do|repeat|until|end)\b', s_clean)
            for t in tokens:
                if t in ("function", "then", "do", "repeat"):
                    block_starts += 1
                elif t in ("end", "until"):
                    block_ends += 1

        # A severe imbalance typically indicates a truncated or broken Lua script
        # Use a percentage-based threshold to avoid false positives from inline patterns
        # like "if x then return end" or lambda-style closures common in PZ mods
        total_blocks = max(block_starts, block_ends, 1)
        abs_diff = abs(block_starts - block_ends)

        # Generous thresholds: PZ mods use unusual Lua patterns
        # Small files (≤80 blocks): absolute threshold of 8
        # Medium files (80-200 blocks): 20% tolerance, min 10
        # Large files (>200 blocks): 18% tolerance, min 25
        if total_blocks > 200:
            threshold = max(int(total_blocks * 0.18), 25)
        elif total_blocks > 80:
            threshold = max(int(total_blocks * 0.20), 10)
        else:
            threshold = 8

        if abs_diff > threshold:
            return f"Desbalanceamento grave de blocos (starts: {block_starts}, ends: {block_ends}) - possível script incompleto."

        return None

    @staticmethod
    def validate_script_files(file_path: str) -> Optional[str]:
        """Validates Zomboid item/recipe script files (.txt)."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return f"Erro de leitura: {e}"

        if "\x00" in content:
            return "Arquivo de script corrompido com bytes nulos."

        # Remove comments (/* ... */ and // ...)
        content_no_comments = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content_no_comments = re.sub(r'//.*$', '', content_no_comments, flags=re.MULTILINE)

        open_braces = content_no_comments.count("{")
        close_braces = content_no_comments.count("}")

        # Allow off-by-one tolerance for script files (common in PZ mod scripts)
        if abs(open_braces - close_braces) > 1:
            return f"Desbalanceamento de chaves em script PZ: {open_braces} '{{' vs {close_braces} '}}'."

        return None

    @classmethod
    def compile_check_mod(cls, mod: Mod) -> List[str]:
        """Runs the compile and build check across all files of a mod."""
        errors = []
        if not mod.mod_folder or not os.path.exists(mod.mod_folder):
            return ["Pasta do mod não encontrada no disco."]

        lua_checked = 0
        scripts_checked = 0

        for root, _, files in os.walk(mod.mod_folder):
            for file in files:
                f_lower = file.lower()
                full_path = os.path.join(root, file)

                if f_lower.endswith(".lua"):
                    lua_checked += 1
                    err = cls.validate_lua_syntax(full_path)
                    if err:
                        rel = os.path.relpath(full_path, mod.mod_folder)
                        errors.append(f"Erro em Lua ({rel}): {err}")
                elif f_lower.endswith(".txt") and "media" in root.lower() and "scripts" in root.lower():
                    scripts_checked += 1
                    err = cls.validate_script_files(full_path)
                    if err:
                        rel = os.path.relpath(full_path, mod.mod_folder)
                        errors.append(f"Erro em Script ({rel}): {err}")

        return errors
