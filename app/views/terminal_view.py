import sys
from app.models.audit_result import AuditResult
from app.models.system_specs import SystemSpecs

class TerminalView:
    """Renders formatted audit output to the terminal."""

    @staticmethod
    def show_banner():
        print("\n" + "="*75)
        print("        PROJECT ZOMBOID BUILD 42 - MOD QUALITY GATE (CI/CD)")
        print("="*75)

    @staticmethod
    def show_step(step: str):
        print(f"--> {step}")

    @staticmethod
    def show_report(specs: SystemSpecs, result: AuditResult):
        TerminalView.show_banner()
        print(f"Ambiente: Windows | RAM Física: {specs.total_ram_gb} GB | Paginação: {specs.total_pagefile_gb} GB | Commit Limit: {specs.commit_limit_gb} GB")
        print(f"Jogo: {specs.game_version} | Mods Ativos: {result.total_active_mods} (Oficina: {result.total_workshop_mods})")
        print(f"DepthMaps Ativos: {result.total_depthmaps} ({result.total_depthmap_mb} MB) | VRAM/Buffer Est.: ~{result.est_native_vram_gb} GB")
        print(f"Animações 3D (.FBX): {result.total_fbx_animations} esqueletos")
        hw_status = "APROVADO" if result.hardware_test_passed else "REPROVADO (Falta Memória Virtual/Swap)"
        print(f"TESTE DE CAPACIDADE DE HARDWARE: [{hw_status}] (Demanda: ~{result.required_memory_gb} GB / Limite: {result.available_commit_gb} GB)")
        print("-"*75)
        print(f"STATUS SINGLEPLAYER: [{result.sp_status}]")
        print(f"STATUS MULTIPLAYER:  [{result.mp_status}]")
        print("-"*75)

        if result.errors:
            print("\n[!] FALHAS CRITICAS QUE REPROVAM A MODLIST (MERGE BLOQUEADO):")
            for i, err in enumerate(result.errors, 1):
                print(f"\n{i}. {err}")

        if result.mp_issues:
            print("\n[!] CONDICOES PARA MULTIPLAYER:")
            for issue in result.mp_issues:
                print(f" - {issue}")

        if result.warnings:
            print("\n[?] AVISOS E INCONSISTENCIAS:")
            for warn in result.warnings[:6]:
                print(f" - {warn}")
            if len(result.warnings) > 6:
                print(f"   ... e mais {len(result.warnings) - 6} avisos menores.")

        print("\n" + "="*75)
        print("DECISAO DO QUALITY GATE:")
        if result.is_green:
            print(">>> PIPELINE VERDE: MODLIST VALIDADA E APROVADA PARA JOGAR.")
        else:
            print(">>> PIPELINE VERMELHO: MODLIST REJEITADA. APLIQUE AS CORRECOES.")
        print("="*75 + "\n")

    @staticmethod
    def show_message(msg: str):
        print(f"[+] {msg}")

    @staticmethod
    def show_error(err: str):
        print(f"[-] {err}")
