import os
from app.models.system_specs import SystemSpecs
from app.models.workshop import Workshop
from app.models.mod_list import ModList
from app.models.rules import RulesEngine
from app.models.audit_result import AuditResult
from app.views.terminal_view import TerminalView
from app.views.report_view import ReportView

class AuditController:
    """Orchestrates the entire Mod CI/CD Audit workflow."""

    def __init__(self):
        self.specs = SystemSpecs.detect()
        self.workshop = Workshop(self.specs.workshop_dir)
        default_txt_path = os.path.join(self.specs.user_zomboid_dir, "mods", "default.txt")
        self.mod_list = ModList(default_txt_path)
        self.rules_engine = RulesEngine(self.specs)

    def run_audit(self, export_md: bool = True) -> AuditResult:
        TerminalView.show_step("Detectando especificações do sistema e diretórios...")
        TerminalView.show_step("Indexando mods da Oficina Steam...")
        self.workshop.scan()

        TerminalView.show_step(f"Carregando lista de mods ativos ({self.mod_list.file_path})...")
        active_mods = self.mod_list.load()

        TerminalView.show_step("Executando regras de validação e testes unitários...")
        result = self.rules_engine.evaluate(active_mods, self.workshop)

        TerminalView.show_report(self.specs, result)

        if export_md:
            report_path = os.path.join(os.getcwd(), "audit_report.md")
            ReportView.export_markdown(self.specs, result, report_path)
            TerminalView.show_message(f"Relatório exportado em: {report_path}")

        # Failure Logs (.txt individual per broken mod)
        from app.views.failure_log_view import FailureLogGenerator
        from app.models.log_inspector import LogInspector
        log_res = LogInspector.inspect(self.specs.user_zomboid_dir)
        logs_dir = os.path.join(os.getcwd(), "failure_logs")
        generated_logs = FailureLogGenerator.generate_sp_logs(result, log_res, logs_dir)
        if generated_logs:
            TerminalView.show_message(f"Logs de falha individuais (.txt) gerados em: {logs_dir} ({len(generated_logs)} arquivo(s))")

        return result

