import os
import datetime
import re
from typing import List, Dict, Optional, Tuple
from app.models.audit_result import AuditResult
from app.models.server_audit_result import ServerAuditResult
from app.models.log_inspector import LogInspectionResult, ModRuntimeStatus


class FailureCategory:
    """Classifies why a mod failed the pipeline."""
    CRASH = "CRASH"                       # Mod causes game/server to crash (fatal)
    NO_LOAD = "NAO_CARREGA"               # Mod loaded by VFS but Lua never executed
    BUILD_FAIL = "FALHA_COMPILACAO"       # Lua syntax error or script corruption
    CONFIG_ERROR = "ERRO_CONFIGURACAO"    # Missing dependency, wrong load order, missing Workshop ID
    CONFLICT = "CONFLITO"                 # Declared incompatibility or duplicate mod
    HARDWARE = "ESTOURO_HARDWARE"         # Exceeds memory/VRAM budget


class ModFailureEntry:
    """Represents a single mod failure with full diagnostic context."""

    def __init__(self, mod_id: str, mod_name: str, category: str,
                 mode: str, reasons: List[str],
                 suggested_fix: str = "", runtime_evidence: str = ""):
        self.mod_id = mod_id
        self.mod_name = mod_name
        self.category = category          # FailureCategory constant
        self.mode = mode                  # "SINGLEPLAYER" or "MULTIPLAYER"
        self.reasons = reasons            # List of diagnostic reasons
        self.suggested_fix = suggested_fix
        self.runtime_evidence = runtime_evidence  # Evidence from console.txt if available
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def color(self) -> str:
        """Severity color: VERMELHO for fatal/crashes/build fails, AMARELO for warnings/configs."""
        if self.category in (FailureCategory.CRASH, FailureCategory.BUILD_FAIL, FailureCategory.HARDWARE):
            return "VERMELHO"
        return "AMARELO"

    def format_log_content(self) -> str:
        """Formats the full failure report for a single mod."""
        separator = "=" * 72
        lines = [
            separator,
            f"  RELATÓRIO DE FALHA DE MOD — [{self.mode}] [{self.color}] — MOD: {self.mod_id}",
            f"  Gerado em: {self.timestamp}",
            separator,
            "",
            f"  MOD ID:       {self.mod_id}",
            f"  MOD NOME:     {self.mod_name}",
            f"  MODO:         {self.mode}",
            f"  GRAVIDADE:    {self.color}",
            f"  CATEGORIA:    {self._category_label()}",
            f"  VEREDICTO:    REPROVADO NA PIPELINE",
            "",
            "-" * 72,
            "  DIAGNÓSTICO — POR QUE ESTE MOD FOI REPROVADO?",
            "-" * 72,
        ]

        for i, reason in enumerate(self.reasons, 1):
            lines.append(f"  {i}. {reason}")

        if self.runtime_evidence:
            lines.extend([
                "",
                "-" * 72,
                "  EVIDÊNCIA DO LOG DE EXECUÇÃO (console.txt)",
                "-" * 72,
                f"  {self.runtime_evidence}",
            ])

        if self.suggested_fix:
            lines.extend([
                "",
                "-" * 72,
                "  COMO CORRIGIR",
                "-" * 72,
                f"  {self.suggested_fix}",
            ])

        lines.extend([
            "",
            "-" * 72,
            "  É ERRO MEU (CONFIG) OU O MOD ESTÁ QUEBRADO?",
            "-" * 72,
        ])

        if self.category == FailureCategory.CONFIG_ERROR:
            lines.extend([
                "  → ERRO DE CONFIGURAÇÃO (PROBLEMA SEU / CONFIG)",
                "  Este mod provavelmente funciona, mas sua instalação/configuração",
                "  está impedindo o carregamento correto. Verifique as dependências,",
                "  a ordem de carregamento ou a falta do Workshop ID no ini.",
            ])
        elif self.category == FailureCategory.CRASH:
            lines.extend([
                "  → MOD QUEBRADO OU INCOMPATÍVEL (PROBLEMA DO MOD)",
                "  Este mod causa crash fatal no motor do jogo (ex: B41 anims no Jassimp B42).",
                "  Não é possível resolver apenas por configuração — o autor precisa",
                "  atualizar o código ou você deve remover o mod.",
            ])
        elif self.category == FailureCategory.BUILD_FAIL:
            lines.extend([
                "  → MOD QUEBRADO (PROBLEMA DO MOD)",
                "  Os arquivos Lua ou scripts deste mod contêm erros de sintaxe,",
                "  chaves desbalanceadas ou corrupção de script.",
                "  Tente desinscrever/reinscrever. Se persistir, o código do mod está quebrado.",
            ])
        elif self.category == FailureCategory.NO_LOAD:
            lines.extend([
                "  → MOD NÃO CARREGOU / EXECUÇÃO LUA FALHOU",
                "  O mod foi registrado pelo VFS mas nunca executou código Lua com sucesso.",
                "  Se o mod depende de outro mod que está ausente, o erro é de CONFIGURAÇÃO.",
                "  Se todas as dependências estão ativas mas o script falhou, o MOD ESTÁ QUEBRADO.",
            ])
        elif self.category == FailureCategory.CONFLICT:
            lines.extend([
                "  → ERRO DE CONFIGURAÇÃO (CONFLITO ENTRE MODS)",
                "  Dois mods que você ativou disputam os mesmos arquivos ou declaram 'incompatible='.",
                "  Desative uma das versões concorrentes.",
            ])
        elif self.category == FailureCategory.HARDWARE:
            lines.extend([
                "  → LIMITAÇÃO DO SEU HARDWARE",
                "  Seu PC não possui memória física ou arquivo de paginação suficiente.",
                "  Aumente o arquivo de paginação do Windows ou remova mods pesados de tiles/veículos.",
            ])

        lines.append(separator)
        return "\n".join(lines)

    def _category_label(self) -> str:
        labels = {
            FailureCategory.CRASH: "🔴 CRASH / MOD INCOMPATÍVEL (fatal)",
            FailureCategory.NO_LOAD: "🟠 NÃO CARREGA (VFS carregou mas Lua não executou)",
            FailureCategory.BUILD_FAIL: "🔴 FALHA DE COMPILAÇÃO / SINTAXE (Script quebrado)",
            FailureCategory.CONFIG_ERROR: "🟡 ERRO DE CONFIGURAÇÃO (dependência/ordem/Workshop ID)",
            FailureCategory.CONFLICT: "🟡 CONFLITO ENTRE MODS (incompatible=)",
            FailureCategory.HARDWARE: "🔴 ESTOURO DE HARDWARE (memória insuficiente)",
        }
        return labels.get(self.category, self.category)


class FailureLogGenerator:
    """Generates individual .txt log files for each mod that failed the pipeline."""

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Removes unsafe characters from filenames."""
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip('. ')

    @classmethod
    def generate_sp_logs(cls, result: AuditResult, log_result: Optional[LogInspectionResult],
                         output_dir: str) -> List[str]:
        """Generates failure logs for Singleplayer audit results.
        Returns list of generated log file paths.
        Only generates logs for mods that failed, were rejected, or had runtime errors.
        """
        os.makedirs(output_dir, exist_ok=True)
        generated = []
        entries: List[ModFailureEntry] = []

        # Classify each error from the audit result into failure entries
        for error_msg in result.errors:
            entry = cls._parse_sp_error(error_msg, "SINGLEPLAYER", log_result)
            if entry:
                entries.append(entry)

        # Rejected mods from rules evaluation
        for mod_id in getattr(result, "rejected_mod_ids", []):
            entry = ModFailureEntry(
                mod_id=mod_id,
                mod_name=mod_id,
                category=FailureCategory.CRASH if mod_id in ("amclub", "autotsartrailers", "tsarslib") else FailureCategory.HARDWARE,
                mode="SINGLEPLAYER",
                reasons=[f"Mod '{mod_id}' foi explicitamente reprovado pelas regras de admissão."],
                suggested_fix=cls._suggest_fix_for_category(FailureCategory.CRASH, mod_id)
            )
            entries.append(entry)

        # Mods with script errors recorded in runtime logs
        if log_result and log_result.has_logs:
            for mod_id, status in log_result.mod_runtime_statuses.items():
                if status.script_errors:
                    entry = ModFailureEntry(
                        mod_id=mod_id,
                        mod_name=mod_id,
                        category=FailureCategory.BUILD_FAIL,
                        mode="SINGLEPLAYER",
                        reasons=[
                            f"O mod '{mod_id}' apresentou erros de carregamento de scripts/receitas no log:",
                            *status.script_errors
                        ],
                        suggested_fix=cls._suggest_fix_for_category(FailureCategory.BUILD_FAIL, mod_id),
                        runtime_evidence="; ".join(status.script_errors)
                    )
                    entries.append(entry)

        # Deduplicate by mod_id
        seen_ids = set()
        for entry in entries:
            if entry.mod_id in seen_ids:
                continue
            seen_ids.add(entry.mod_id)

            safe_name = cls._sanitize_filename(entry.mod_id)
            filename = f"{entry.color}_FALHA_SP_{safe_name}.txt"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(entry.format_log_content())

            generated.append(filepath)

        return generated

    @classmethod
    def generate_mp_logs(cls, result: ServerAuditResult, output_dir: str) -> List[str]:
        """Generates failure logs for Multiplayer/Server audit results.
        Returns list of generated log file paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        generated = []
        entries: List[ModFailureEntry] = []

        # RED mods (crash/compilation)
        for mod_id, mod_name, reason in result.red_mods:
            category = FailureCategory.CRASH
            if "COMPILAÇÃO" in reason.upper() or "BUILD" in reason.upper():
                category = FailureCategory.BUILD_FAIL

            entry = ModFailureEntry(
                mod_id=mod_id,
                mod_name=mod_name,
                category=category,
                mode="MULTIPLAYER",
                reasons=[reason],
                suggested_fix=cls._suggest_fix_for_category(category, mod_id)
            )
            entries.append(entry)

        # YELLOW mods (config/alert)
        for mod_id, mod_name, reason in result.yellow_mods:
            category = FailureCategory.CONFIG_ERROR
            if "Workshop ID" in reason:
                category = FailureCategory.CONFIG_ERROR
            elif "mapa" in reason.lower() or "Map" in reason:
                category = FailureCategory.CONFIG_ERROR
            elif "BUILD" in reason.upper() or "ALERTA DE BUILD" in reason.upper():
                category = FailureCategory.BUILD_FAIL

            entry = ModFailureEntry(
                mod_id=mod_id,
                mod_name=mod_name,
                category=category,
                mode="MULTIPLAYER",
                reasons=[reason],
                suggested_fix=cls._suggest_fix_for_category(category, mod_id)
            )
            entries.append(entry)

        # Build failures with detailed errors
        for mod_id, mod_name, build_errors in result.build_failures:
            entry = ModFailureEntry(
                mod_id=mod_id,
                mod_name=mod_name,
                category=FailureCategory.BUILD_FAIL,
                mode="MULTIPLAYER",
                reasons=build_errors,
                suggested_fix=cls._suggest_fix_for_category(FailureCategory.BUILD_FAIL, mod_id)
            )
            entries.append(entry)

        # Deduplicate by mod_id
        seen_ids = set()
        for entry in entries:
            if entry.mod_id in seen_ids:
                continue
            seen_ids.add(entry.mod_id)

            safe_name = cls._sanitize_filename(entry.mod_id)
            filename = f"{entry.color}_FALHA_MP_{safe_name}.txt"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(entry.format_log_content())

            generated.append(filepath)

        return generated

    @staticmethod
    def _parse_sp_error(error_msg: str, mode: str,
                        log_result: Optional[LogInspectionResult]) -> Optional[ModFailureEntry]:
        """Parses a structured error message from the SP rules engine into a ModFailureEntry."""

        # Extract mod ID from common error patterns
        mod_id = "desconhecido"
        mod_name = "Desconhecido"
        category = FailureCategory.CRASH
        reasons = [error_msg]
        runtime_evidence = ""
        suggested_fix = ""

        # Pattern: [MOD INCOMPATÍVEL COM B42 - CRASH NATIVO JASSIMP]
        if "CRASH NATIVO JASSIMP" in error_msg or "MOD INCOMPATÍVEL" in error_msg:
            category = FailureCategory.CRASH
            # Extract mod ID from "Mod detectado: xxx"
            id_match = re.search(r'Mod detectado:\s*(\S+)', error_msg)
            if id_match:
                mod_id = id_match.group(1)
                mod_name = mod_id
            suggested_fix = (
                "Este mod usa animações FBX da Build 41 que são incompatíveis com o Jassimp da B42.\n"
                "  Solução: Remova o mod e procure uma versão atualizada para a Build 42 na Oficina."
            )

        # Pattern: [CONFLITO DECLARADO (incompatible=)]
        elif "incompatible=" in error_msg or "CONFLITO" in error_msg:
            category = FailureCategory.CONFLICT
            id_match = re.search(r"Mod '([^']+)'", error_msg)
            if id_match:
                mod_id = id_match.group(1)
                mod_name = mod_id
            suggested_fix = (
                "Dois mods ativos declaram conflito entre si. Desative um deles.\n"
                "  O campo 'incompatible=' no mod.info indica essa incompatibilidade."
            )

        # Pattern: [CRASH REAL REGISTRADO EM LOG]
        elif "CRASH REAL REGISTRADO" in error_msg:
            category = FailureCategory.CRASH
            mod_id = "sistema"
            mod_name = "Crash Fatal do Jogo"
            if log_result and log_result.crash_reason:
                runtime_evidence = log_result.crash_reason
            suggested_fix = (
                "O jogo sofreu um crash fatal na última execução.\n"
                "  Verifique o console.txt completo para identificar o mod causador."
            )

        # Pattern: [TESTE DE HARDWARE FALHOU]
        elif "TESTE DE HARDWARE" in error_msg:
            category = FailureCategory.HARDWARE
            mod_id = "hardware"
            mod_name = "Limite de Hardware Excedido"
            suggested_fix = (
                "Seu PC não tem memória suficiente para todos os mods ativos.\n"
                "  Soluções: (1) Remover mods pesados de tiles/texturas.\n"
                "  (2) Aumentar o arquivo de paginação do Windows.\n"
                "  (3) Adicionar mais RAM física."
            )

        # Pattern: [SOBRECARGA CRÍTICA DE ANIMAÇÕES 3D]
        elif "SOBRECARGA" in error_msg and "FBX" in error_msg:
            category = FailureCategory.HARDWARE
            mod_id = "fbx_overload"
            mod_name = "Sobrecarga de Animações 3D"
            suggested_fix = "Reduza o número de mods com modelos .FBX (veículos, armaduras, armas 3D)."

        else:
            # Generic fallback
            id_match = re.search(r"'([^']+)'", error_msg)
            if id_match:
                mod_id = id_match.group(1)
                mod_name = mod_id

        return ModFailureEntry(
            mod_id=mod_id,
            mod_name=mod_name,
            category=category,
            mode=mode,
            reasons=reasons,
            suggested_fix=suggested_fix,
            runtime_evidence=runtime_evidence
        )

    @staticmethod
    def _suggest_fix_for_category(category: str, mod_id: str) -> str:
        fixes = {
            FailureCategory.CRASH: (
                f"Remova o mod '{mod_id}' da lista de mods ativos.\n"
                f"  Se o mod era funcional na Build 41, procure uma versão atualizada para B42."
            ),
            FailureCategory.BUILD_FAIL: (
                f"1. Tente desinscrever e reinscrever o mod '{mod_id}' na Oficina Steam.\n"
                f"  2. Se o erro persistir, o mod possui código Lua ou scripts quebrados.\n"
                f"  3. Reporte o erro ao autor do mod na página da Oficina."
            ),
            FailureCategory.CONFIG_ERROR: (
                f"1. Verifique se todas as dependências do mod '{mod_id}' estão instaladas.\n"
                f"  2. Execute 'py main.py server-sanitize' para sincronizar Workshop IDs.\n"
                f"  3. Confira se o mod está na versão correta (42/ ou common/)."
            ),
            FailureCategory.CONFLICT: (
                f"Remova um dos mods em conflito com '{mod_id}'.\n"
                f"  Consulte o mod.info de cada mod para verificar as tags 'incompatible='."
            ),
            FailureCategory.HARDWARE: (
                "Reduza mods pesados ou aumente recursos de memória do sistema."
            ),
            FailureCategory.NO_LOAD: (
                f"1. Verifique se '{mod_id}' possui scripts Lua em media/lua/.\n"
                f"  2. Se sim, confira dependências (require=) e ordem de carregamento.\n"
                f"  3. Se é mod de texturas/tiles, o aviso pode ser ignorado."
            ),
        }
        return fixes.get(category, "Verifique o mod manualmente.")
