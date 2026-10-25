import os
import re
from typing import List, Tuple, Dict, Optional
from .mod import Mod

class BuildValidator:
    """Performs static build and compilation verification on mods (Lua syntax, scripts, balance)."""

    @staticmethod
    def _strip_lua_comments_and_strings(content: str) -> str:
        """Strips comments and string literals from Lua source code to allow accurate keyword scanning."""
        # 1. Multi-line comments --[(=*)\[ ... \]\1\]
        content = re.sub(r'--\[(=*)\[.*?\]\1\]', '', content, flags=re.DOTALL)
        # 2. Multi-line strings [(=*)\[ ... \]\1\]
        content = re.sub(r'(?<!-)\[(=*)\[.*?\]\1\]', '""', content, flags=re.DOTALL)
        # 3. Single-line comments -- ...
        content = re.sub(r'--[^\r\n]*', '', content)
        # 4. Quoted single-line strings "..." and '...'
        content = re.sub(r'"(?:\\.|[^"\\])*"', '""', content)
        content = re.sub(r"'(?:\\.|[^'\\])*'", "''", content)
        return content

    @staticmethod
    def validate_lua_syntax(file_path: str) -> Optional[str]:
        """Validates Lua syntax and block integrity without false positives on elseif chains."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return f"Erro de leitura: {e}"

        if "\x00" in content:
            return "Arquivo corrompido com bytes nulos."

        cleaned = BuildValidator._strip_lua_comments_and_strings(content)

        # In Lua grammar, blocks are opened by:
        # - 'if' (closed by matching 'end', regardless of how many 'elseif' or 'else' branches exist)
        # - 'do' (standalone 'do', 'while ... do', 'for ... do', all closed by 'end')
        # - 'function' (closed by 'end')
        # - 'repeat' (closed by 'until')
        tokens = re.findall(r'\b(if|do|function|repeat|end|until)\b', cleaned)

        block_starts = 0
        block_ends = 0
        for t in tokens:
            if t in ("if", "do", "function"):
                block_starts += 1
            elif t == "repeat":
                block_starts += 1
            elif t == "end":
                block_ends += 1
            elif t == "until":
                block_ends += 1

        if block_starts != block_ends:
            diff = abs(block_starts - block_ends)
            return (
                f"Desbalanceamento de blocos Lua ({block_starts} aberturas vs {block_ends} fechamentos, "
                f"diferença: {diff}) - script incompleto ou com erro de sintaxe."
            )

        return None

    @staticmethod
    def validate_script_files(file_path: str) -> Optional[str]:
        """Validates Zomboid item/recipe/model script files (.txt) ensuring balanced braces."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return f"Erro de leitura: {e}"

        if "\x00" in content:
            return "Arquivo de script corrompido com bytes nulos."

        # Remove multi-line comments /* ... */
        content_clean = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # Remove single-line comments // ... and # ...
        content_clean = re.sub(r'(?://|#)[^\r\n]*', '', content_clean)
        # Remove quoted strings "..." to prevent braces inside strings from skewing counts
        content_clean = re.sub(r'"(?:\\.|[^"\\])*"', '""', content_clean)

        open_braces = content_clean.count("{")
        close_braces = content_clean.count("}")

        if open_braces != close_braces:
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

    @classmethod
    def validate_mod(cls, mod: Mod) -> List[str]:
        """Alias for compile_check_mod."""
        return cls.compile_check_mod(mod)
