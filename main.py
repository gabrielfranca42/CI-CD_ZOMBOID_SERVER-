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
    sanitize_parser.add_argument(
        "--level",
        choices=["red", "yellow"],
        default="red",
        help="Nível de higienização: 'red' = apenas reprovados/crash, 'yellow' = reprovados + alertas de duplicata"
    )

    # Command: purge (Singleplayer)
    purge_parser = subparsers.add_parser("purge", help="Audita e apaga do disco todos os mods que reprovarem no teste de hardware")
    purge_parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Apenas desativa da lista sem deletar os arquivos do disco"
    )

    # Command: remove-mod (Singleplayer & Multiplayer)
    remove_parser = subparsers.add_parser("remove-mod", help="Remove um mod específico por ID")
    remove_parser.add_argument("mod_id", help="ID do mod a ser removido")
    remove_parser.add_argument("--mode", choices=["sp", "mp", "both"], default="both",
                               help="Onde remover: 'sp', 'mp' ou 'both' (padrão: both)")
    remove_parser.add_argument("--delete-files", action="store_true",
                               help="Apaga os arquivos físicos do disco")

    # Command: install-mod (SteamCMD download + real-time validation)
    inst_parser = subparsers.add_parser("install-mod", help="Baixa mod/dependência via SteamCMD e valida em tempo real")
    inst_parser.add_argument("mod_id", help="ID do mod ou Workshop ID numérico para instalar")
    inst_parser.add_argument("--mode", choices=["sp", "mp", "both"], default="sp",
                             help="Adicionar ao: 'sp' (Singleplayer) ou 'mp' (Multiplayer)")

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
    srv_san.add_argument("--delete-files", action="store_true", help="Apaga os arquivos físicos do disco")

    # Command: reorder (Singleplayer load order optimization)
    subparsers.add_parser("reorder", help="Reordena a modlist do Singleplayer na ordem topológica ideal")

    # Command: server-test-mod (Multiplayer)
    srv_test = subparsers.add_parser("server-test-mod", help="Valida compilação e admissão de novo mod no Servidor")
    srv_test.add_argument("mod_id", help="ID do mod para testar no servidor")

    # Command: server-sync (Multiplayer pre-boot SteamCMD workshop sync)
    subparsers.add_parser("server-sync", help="Pré-sincroniza todos os mods da Workshop do servidor via SteamCMD")

    # Command: sync-manifest (Download all mods defined in server_mods_manifest.json)
    manifest_parser = subparsers.add_parser("sync-manifest", help="Baixa e implanta todos os mods via manifesto JSON")
    manifest_parser.add_argument("--no-local-copy", action="store_true", help="Não copiar para a pasta de mods do usuário")

    # Command: deploy-local (Deploy all workshop mods to local mods directory)
    deploy_local_parser = subparsers.add_parser("deploy-local", help="Implanta todos os mods da Workshop na pasta local do usuário")
    deploy_local_parser.add_argument("--clean-workshop-items", action="store_true", help="Limpa WorkshopItems= do servertest.ini para inicialização total offline/local")

    # Command: zero-steam (Zero-Steam Boot activation)
    subparsers.add_parser("zero-steam", help="Ativa Zero-Steam Boot limpando WorkshopItems= e mantendo Mods=")

    args = parser.parse_args()

    if args.command == "sanitize":
        controller = GatekeeperController()
        controller.purge_rejected_mods(delete_files=args.delete_files)
    elif args.command == "purge":
        controller = GatekeeperController()
        controller.purge_rejected_mods(delete_files=not args.keep_files)
    elif args.command == "reorder":
        controller = GatekeeperController()
        controller.reorder_mods()
    elif args.command == "remove-mod":
        if args.mode in ("sp", "both"):
            g_controller = GatekeeperController()
            g_controller.remove_mod_by_id(args.mod_id, delete_files=args.delete_files)
        if args.mode in ("mp", "both"):
            s_controller = ServerController()
            s_controller.remove_mod_by_id(args.mod_id, delete_files=args.delete_files and args.mode == "mp")
    elif args.command == "install-mod":
        if args.mode in ("sp", "both"):
            g_controller = GatekeeperController()
            g_controller.install_and_admit_mod(args.mod_id)
        if args.mode in ("mp", "both"):
            s_controller = ServerController()
            s_controller.install_and_admit_mod_mp(args.mod_id)
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
    elif args.command == "server-sync":
        s_controller = ServerController()
        s_controller.sync_workshop_steamcmd()
    elif args.command == "sync-manifest":
        s_controller = ServerController()
        s_controller.sync_from_json_manifest(copy_to_local_mods=not args.no_local_copy)
    elif args.command == "deploy-local":
        s_controller = ServerController()
        s_controller.deploy_all_mods_to_local(clean_workshop_items=args.clean_workshop_items)
    elif args.command == "zero-steam":
        s_controller = ServerController()
        s_controller.apply_zero_steam_boot()
    else:
        # Default behavior: run audit
        controller = AuditController()
        controller.run_audit(export_md=not getattr(args, "no_export", False))


if __name__ == "__main__":
    main()
