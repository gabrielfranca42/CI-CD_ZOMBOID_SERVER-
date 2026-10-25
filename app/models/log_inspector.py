import os
import re
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass, field

@dataclass
class ModRuntimeStatus:
    """Tracks individual mod loading and execution evidence from game logs."""
    mod_id: str
    vfs_loaded: bool = False          # Engine loaded it into VFS (LOG : Mod ... loading ...)
    vfs_overrides: int = 0            # Count of VFS file overrides this mod performed
    lua_executed: bool = False        # At least one Lua print/log from this mod was detected
    lua_evidence: List[str] = field(default_factory=list)  # Specific Lua execution evidence
    script_errors: List[str] = field(default_factory=list) # Recipe/Script errors tied to this mod
    registry_errors: int = 0          # Duplicate registry errors (handled by Java try/catch)

    @property
    def status(self) -> str:
        if self.vfs_loaded and self.lua_executed and not self.script_errors:
            return "EXECUTANDO"
        elif self.vfs_loaded and self.lua_executed and self.script_errors:
            return "PARCIAL (erros de script)"
        elif self.vfs_loaded and not self.lua_executed:
            return "CARREGADO MAS SEM EXECUÇÃO LUA"
        else:
            return "DESCONHECIDO"


@dataclass
class LogInspectionResult:
    has_logs: bool = False
    log_file: str = ""
    last_modified: str = ""
    boot_successful: bool = False
    clean_exit: bool = False
    fatal_crash: bool = False
    crash_reason: Optional[str] = None
    handled_errors_count: int = 0
    overrides_count: int = 0
    mods_loaded: List[str] = field(default_factory=list)
    mods_with_lua_execution: List[str] = field(default_factory=list)
    mods_without_lua_execution: List[str] = field(default_factory=list)
    mod_runtime_statuses: Dict[str, ModRuntimeStatus] = field(default_factory=dict)
    script_errors: List[str] = field(default_factory=list)
    registry_errors: List[str] = field(default_factory=list)
    total_vfs_loaded: int = 0
    total_lua_confirmed: int = 0
    total_silent_mods: int = 0
    diagnostic_summary: str = ""
    detailed_diagnostics: List[str] = field(default_factory=list)


class LogInspector:
    """Inspects Project Zomboid console.txt to ground CI/CD decisions in real game logs.

    Enhanced to detect per-mod runtime execution status:
    - VFS loading (engine registered the mod)
    - Lua execution (mod's scripts actually ran)
    - Script/recipe errors (mod loaded but items/recipes failed)
    - Silent failures (mod loaded by engine but never executed Lua)
    """

    # Patterns for identifying Lua execution evidence from specific mods
    # Format: (pattern_in_log, mod_id_extractor_or_None)
    LUA_MOD_MARKERS = [
        # Direct mod name in brackets: [ModName] message
        (re.compile(r'\[(\w[\w\s\-\.]+?)\]'), None),
        # "Mod Loaded: Name by Author" pattern
        (re.compile(r'Mod Loaded:\s+(\S+)'), None),
        # ModName: action pattern (e.g., "ReducedWoodWeightMod: Modified weight")
        (re.compile(r'^:\s+(\w+(?:Mod|mod|Pack|pack|Patch|patch|Core|core|Lib|lib))[\s:]'), None),
    ]

    @staticmethod
    def inspect(user_zomboid_dir: str) -> LogInspectionResult:
        res = LogInspectionResult()
        console_path = os.path.join(user_zomboid_dir, "console.txt")

        if not os.path.exists(console_path):
            res.diagnostic_summary = "Nenhum arquivo console.txt encontrado em " + user_zomboid_dir
            return res

        res.has_logs = True
        res.log_file = console_path

        try:
            mtime = os.path.getmtime(console_path)
            import datetime
            res.last_modified = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            pass

        try:
            with open(console_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            res.diagnostic_summary = f"Erro ao ler console.txt: {e}"
            return res

        # Phase 1: Build per-mod runtime tracking
        mod_statuses: Dict[str, ModRuntimeStatus] = {}
        lua_execution_evidence: Dict[str, Set[str]] = {}  # mod_id -> set of evidence strings

        for line in lines:
            line_str = line.strip()

            # ── Boot milestones ──
            if any(marker in line_str for marker in (
                "Arranque do jogo", "VehiclesDB2.init() start",
                "briefing shown for player", "GameThread entered"
            )):
                res.boot_successful = True

            if "GameThread exited" in line_str or "Saving GlobalModData" in line_str:
                res.clean_exit = True

            # ── Fatal crashes ──
            if any(f_marker in line_str for f_marker in (
                "EXCEPTION_ACCESS_VIOLATION", "SIGSEGV",
                "java.lang.OutOfMemoryError",
                "bad allocation in Jassimp.aiImportFile"
            )):
                res.fatal_crash = True
                res.crash_reason = line_str

            # ── VFS Mod Loading: "LOG  : Mod ... loading <modid>" ──
            vfs_match = re.search(r'LOG\s*:\s*Mod\s+.*?loading\s+(.+)', line_str)
            if vfs_match:
                mod_id = vfs_match.group(1).strip()
                # Handle path-style mod IDs like "2874163136/CaptainJuezo1_WIP_B42"
                if "/" in mod_id:
                    mod_id = mod_id.split("/", 1)[1]
                if mod_id not in mod_statuses:
                    mod_statuses[mod_id] = ModRuntimeStatus(mod_id=mod_id)
                mod_statuses[mod_id].vfs_loaded = True
                if mod_id not in res.mods_loaded:
                    res.mods_loaded.append(mod_id)

            # ── VFS Overrides: 'mod "X" overrides ...' ──
            override_match = re.search(r'mod\s+"([^"]+)"\s+overrides\s+', line_str)
            if override_match:
                ov_mod = override_match.group(1)
                res.overrides_count += 1
                if ov_mod in mod_statuses:
                    mod_statuses[ov_mod].vfs_overrides += 1

            # ── Lua execution evidence (LOG : Lua lines) ──
            if "LOG  : Lua" in line_str:
                # Extract the message content after the log prefix
                lua_content_match = re.search(r'LOG\s*:\s*Lua\s+.*?>\s*:?\s*(.*)', line_str)
                if lua_content_match:
                    lua_msg = lua_content_match.group(1).strip()
                    if lua_msg:
                        # Try to attribute this Lua execution to a specific mod
                        attributed = False

                        # Pattern 1: [ModName] message
                        bracket_match = re.search(r'\[([^\]]+)\]', lua_msg)
                        if bracket_match:
                            bracket_name = bracket_match.group(1).strip()
                            # Find mod by matching bracket name to mod_id (case-insensitive partial)
                            for mid in mod_statuses:
                                if bracket_name.lower() in mid.lower() or mid.lower() in bracket_name.lower():
                                    mod_statuses[mid].lua_executed = True
                                    if lua_msg not in mod_statuses[mid].lua_evidence:
                                        mod_statuses[mid].lua_evidence.append(lua_msg[:120])
                                    attributed = True
                                    break

                        # Pattern 2: "ModName: action" or "ModName action"
                        if not attributed:
                            for mid in mod_statuses:
                                mid_lower = mid.lower()
                                msg_lower = lua_msg.lower()
                                # Check if mod ID appears at start of Lua message
                                if msg_lower.startswith(mid_lower) or mid_lower.replace("_", "") in msg_lower.replace("_", ""):
                                    mod_statuses[mid].lua_executed = True
                                    if lua_msg not in mod_statuses[mid].lua_evidence:
                                        mod_statuses[mid].lua_evidence.append(lua_msg[:120])
                                    attributed = True
                                    break

                        # Pattern 3: "Mod Loaded: Name by Author"
                        if not attributed:
                            loaded_match = re.search(r'Mod Loaded:\s+(\S+)', lua_msg)
                            if loaded_match:
                                loaded_name = loaded_match.group(1)
                                for mid in mod_statuses:
                                    if loaded_name.lower() in mid.lower() or mid.lower() in loaded_name.lower():
                                        mod_statuses[mid].lua_executed = True
                                        mod_statuses[mid].lua_evidence.append(lua_msg[:120])
                                        attributed = True
                                        break

            # ── Non-fatal handled errors (Java try/catch absorbed) ──
            if "Tried to register duplicate object" in line_str or "IllegalArgumentException" in line_str:
                res.handled_errors_count += 1
                # Try to attribute to a mod via the MOD tag in the error
                mod_err_match = re.search(r'\(MOD:([^)]+)\)', line_str)
                if mod_err_match:
                    err_mod = mod_err_match.group(1).strip()
                    for mid in mod_statuses:
                        if err_mod.lower() in mid.lower() or mid.lower() in err_mod.lower():
                            mod_statuses[mid].registry_errors += 1
                            break
                res.registry_errors.append(line_str[:150])

            # ── Script/Recipe errors (Could not assign [key]) ──
            if "Could not assign [key]" in line_str or "Sanitizing container name" in line_str:
                res.script_errors.append(line_str[:150])

        # Phase 2: Compute per-mod runtime classification
        res.mod_runtime_statuses = mod_statuses

        for mid, status in mod_statuses.items():
            if status.vfs_loaded and status.lua_executed:
                res.mods_with_lua_execution.append(mid)
            elif status.vfs_loaded and not status.lua_executed:
                res.mods_without_lua_execution.append(mid)

        res.total_vfs_loaded = len([s for s in mod_statuses.values() if s.vfs_loaded])
        res.total_lua_confirmed = len(res.mods_with_lua_execution)
        res.total_silent_mods = len(res.mods_without_lua_execution)

        # Phase 3: Formulate diagnostic summary
        if res.fatal_crash and not res.clean_exit:
            res.diagnostic_summary = f"CRASH REAL DETECTADO NOS LOGS: {res.crash_reason}"
        elif res.boot_successful:
            status_exit = "saída limpa" if res.clean_exit else "em execução/sessão concluída"
            lua_ratio = f"{res.total_lua_confirmed}/{res.total_vfs_loaded}" if res.total_vfs_loaded > 0 else "0/0"
            res.diagnostic_summary = (
                f"Sessão executada com sucesso ({res.last_modified}): Jogo inicializou "
                f"({res.total_vfs_loaded} mods carregados pelo VFS, {lua_ratio} com execução Lua confirmada, "
                f"{res.overrides_count} sobrescritas VFS absorvidas, "
                f"{res.handled_errors_count} avisos recuperados pelo Java, {status_exit})."
            )

            # Add detailed per-mod diagnostics
            if res.total_silent_mods > 0:
                silent_note = (
                    f"[ATENÇÃO - MODS SEM EXECUÇÃO LUA DETECTADA] "
                    f"{res.total_silent_mods} mod(s) foram carregados pelo VFS mas não apresentaram "
                    f"evidência de execução Lua no console.txt. Isso pode significar: "
                    f"(1) mods puramente de assets/texturas que não possuem scripts Lua, "
                    f"(2) mods cujos scripts Lua rodaram silenciosamente sem gerar saída no console, ou "
                    f"(3) mods com falha silenciosa de carregamento. "
                    f"Mods silenciosos: {res.mods_without_lua_execution[:10]}"
                )
                res.detailed_diagnostics.append(silent_note)

            if res.script_errors:
                script_note = (
                    f"[ERROS DE SCRIPT/RECEITA DETECTADOS] "
                    f"{len(res.script_errors)} erro(s) de carregamento de receitas/scripts. "
                    f"Esses itens ou receitas não funcionarão no jogo. "
                    f"Primeiros erros: {res.script_errors[:3]}"
                )
                res.detailed_diagnostics.append(script_note)

            if res.registry_errors:
                reg_note = (
                    f"[REGISTROS DUPLICADOS ABSORVIDOS] "
                    f"{len(res.registry_errors)} registros duplicados foram absorvidos pelo Java try/catch. "
                    f"Esses não causam crash mas indicam sobreposição de conteúdo entre mods."
                )
                res.detailed_diagnostics.append(reg_note)
        else:
            res.diagnostic_summary = f"Log localizado ({res.last_modified}), mas sem marcos claros de inicialização."

        return res
