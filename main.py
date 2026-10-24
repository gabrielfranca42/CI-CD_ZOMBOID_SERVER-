#!/usr/bin/env python3
"""
Project Zomboid Mod CI/CD Pipeline & Quality Gate
Entry Point (MVC Architecture)
"""

import sys
import argparse

# Ensure proper encoding on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.controllers.audit_controller import AuditController
from app.controllers.gatekeeper_controller import GatekeeperController
from app.controllers.server_controller import ServerController

def main():
    parser = argparse.ArgumentParser(
        description="Project Zomboid Build 42 - Mod CI/CD Quality Gate & Auditor"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # Command: audit (Singleplayer)
    audit_parser = subparsers.add_parser("audit", help="Executa auditoria completa dos mods do Singleplayer")
    audit_parser.add_argument("--no-export", action="store_true", help="Não gerar audit_report.md")

    # Command: sanitize (Singleplayer)
    sanitize_parser = subparsers.add_parser("sanitize", help="Higieniza a modlist do Singleplayer")
    sanitize_parser.add_argument(
        "--delete-files",
        action="store_true",
        help="Apaga os arquivos físicos do mod do disco em caso de reprovação"
    )

    # Command: purge (Singleplayer)
    purge_parser = subparsers.add_parser("purge", help="Audita e apaga do disco todos os mods que reprovarem no teste de hardware")
    purge_parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Apenas desativa da lista sem deletar os arquivos do disco"
    )

    # Command: test-mod (Singleplayer)
    test_parser = subparsers.add_parser("test-mod", help="Valida se um mod novo pode ser adicionado ao Singleplayer")
    test_parser.add_argument("mod_id", help="ID do mod para testar admissão")

    # Command: server-audit (Multiplayer)
    srv_audit = subparsers.add_parser("server-audit", help="Audita o Servidor e verifica compilação dos mods")

    # Command: server-sanitize (Multiplayer)
    srv_san = subparsers.add_parser("server-sanitize", help="Higieniza o servidor e sincroniza WorkshopItems")
    srv_san.add_argument("--memory", type=int, default=2048, help="Memória do servidor em MB (padrão: 2048)")
    srv_san.add_argument("--level", choices=["red", "yellow"], default="red",
                         help="Nível de higienização: 'red' = só graves/crash, 'yellow' = graves + alertas (padrão: red)")

    # Command: server-test-mod (Multiplayer)
    srv_test = subparsers.add_parser("server-test-mod", help="Valida compilação e admissão de novo mod no Servidor")
    srv_test.add_argument("mod_id", help="ID do mod para testar no servidor")

    args = parser.parse_args()

    if args.command == "sanitize":
        controller = GatekeeperController()
        controller.purge_rejected_mods(delete_files=args.delete_files)
    elif args.command == "purge":
        controller = GatekeeperController()
        controller.purge_rejected_mods(delete_files=not args.keep_files)
    elif args.command == "test-mod":
        controller = GatekeeperController()
        controller.admit_candidate_mod(args.mod_id)
    elif args.command == "server-audit":
        s_controller = ServerController()
        s_controller.audit_server()
    elif args.command == "server-sanitize":
        s_controller = ServerController()
        s_controller.sanitize_and_sync_server(target_memory_mb=args.memory, level=args.level)
    elif args.command == "server-test-mod":
        s_controller = ServerController()
        s_controller.admit_candidate_mod_mp(args.mod_id)
    else:
        # Default behavior: run audit
        controller = AuditController()
        controller.run_audit(export_md=not getattr(args, "no_export", False))

if __name__ == "__main__":
    main()
