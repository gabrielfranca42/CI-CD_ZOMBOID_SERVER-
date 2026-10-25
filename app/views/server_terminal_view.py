from app.models.server_audit_result import ServerAuditResult
from app.models.system_specs import SystemSpecs

class ServerTerminalView:
    """Renders formatted Multiplayer Server audit results with color-coded mod classification."""

    @staticmethod
    def show_banner():
        print("\n" + "="*75)
        print("      PROJECT ZOMBOID BUILD 42 - MULTIPLAYER SERVER QUALITY GATE")
        print("="*75)

    @staticmethod
    def show_report(specs: SystemSpecs, result: ServerAuditResult):
        ServerTerminalView.show_banner()
        print(f"Ambiente: Windows | RAM Física: {specs.total_ram_gb} GB | Paginação: {specs.total_pagefile_gb} GB | Commit Limit: {specs.commit_limit_gb} GB")
        print(f"Alocação: Servidor ({result.host_memory_mb} MB) + Cliente ({result.client_memory_gb} GB)")
        print(f"Mods Ativos no Servidor: {result.total_server_mods} | IDs Workshop Sincronizados: {result.total_workshop_items}")

        hw_status = "APROVADO" if result.hardware_test_passed else "REPROVADO (Estouro de Commit)"
        print(f"TESTE DE HARDWARE DO SERVIDOR: [{hw_status}] (Demanda: ~{result.total_required_commit_gb} GB / Limite: {result.available_commit_gb} GB)")

        build_status = "PASSOU SEM ERROS" if len(result.build_failures) == 0 else f"{len(result.build_failures)} MODS COM ERRO"
        print(f"VERIFICAÇÃO DE BUILD/COMPILAÇÃO: [{build_status}]")
        print("-"*75)
        print(f"STATUS DO SERVIDOR MULTIPLAYER: [{result.server_status}]")
        print("-"*75)

        # ─── PAINEL DE CORES ───
        counts = result.summary_counts
        print(f"\n┌─────────────────────────────────────────────────────────┐")
        print(f"│  CLASSIFICAÇÃO DE MODS POR SEVERIDADE                   │")
        print(f"├─────────────────────────────────────────────────────────┤")
        print(f"│  🔴 VERMELHO (Grave/Crash/Não Compila): {counts['red']:>4} mods      │")
        print(f"│  🟡 AMARELO  (Alerta/Sujeito a Erro):   {counts['yellow']:>4} mods      │")
        print(f"│  🟢 VERDE    (Aprovado/Saudável):        {counts['green']:>4} mods      │")
        print(f"│  ── TOTAL:                               {counts['total']:>4} mods      │")
        print(f"└─────────────────────────────────────────────────────────┘")

        # ─── MODS VERMELHOS (GRAVES) ───
        if result.red_mods:
            print(f"\n🔴 ═══ MODS VERMELHOS — IMPEDEM INICIALIZAÇÃO / CRASH GRAVE ({len(result.red_mods)}) ═══")
            for mid, mname, reason in result.red_mods:
                print(f"  ❌ {mname}")
                print(f"     ID:     {mid}")
                print(f"     Motivo: {reason}")

        # ─── MODS AMARELOS (ALERTAS) ───
        if result.yellow_mods:
            print(f"\n🟡 ═══ MODS AMARELOS — SUJEITO A ERRO / VERIFICAR ({len(result.yellow_mods)}) ═══")
            for mid, mname, reason in result.yellow_mods:
                print(f"  ⚠️  {mname}")
                print(f"     ID:     {mid}")
                print(f"     Motivo: {reason}")

        # ─── MODS VERDES (SAUDÁVEIS) ───
        if result.green_mods:
            print(f"\n🟢 ═══ MODS VERDES — APROVADOS ({len(result.green_mods)}) ═══")
            for mid, mname in result.green_mods:
                print(f"  ✅ {mname} ({mid})")

        # ─── ERROS E AVISOS DETALHADOS ───
        if result.errors:
            print(f"\n{'─'*75}")
            print("[!] FALHAS CRÍTICAS QUE IMPEDEM O SERVIDOR DE INICIAR:")
            for i, err in enumerate(result.errors, 1):
                print(f"\n{i}. {err}")

        if result.missing_workshop_mappings:
            print(f"\n[?] MODS SEM WORKSHOP ID ({len(result.missing_workshop_mappings)} encontrados):")
            for m in result.missing_workshop_mappings[:5]:
                print(f" - {m}")
            if len(result.missing_workshop_mappings) > 5:
                print(f"   ... e mais {len(result.missing_workshop_mappings) - 5} mods. Use 'Sincronizar Servidor' para preencher automaticamente.")

        if result.missing_map_mappings:
            print(f"\n[🗺️] MAPAS SEM CONFIGURAÇÃO EM Map= ({len(result.missing_map_mappings)} encontrados):")
            for m in result.missing_map_mappings[:5]:
                print(f" - {m}")
            if len(result.missing_map_mappings) > 5:
                print(f"   ... e mais {len(result.missing_map_mappings) - 5} mapas.")

        if result.warnings:
            print("\n[?] AVISOS DO SERVIDOR:")
            for warn in result.warnings[:5]:
                print(f" - {warn}")

        print("\n" + "="*75)
        print("DECISÃO DO QUALITY GATE DO SERVIDOR:")
        if result.is_green:
            print(">>> PIPELINE VERDE: SERVIDOR VALIDADO, SINCRONIZADO E PRONTO PARA INICIAR.")
        else:
            has_red = len(result.red_mods) > 0
            has_yellow = len(result.yellow_mods) > 0
            if has_red:
                print(">>> PIPELINE VERMELHO: SERVIDOR REJEITADO. CORRIJA OS ERROS ANTES DE HOSTEAR.")
                print(f"    Use 'Higienizar Servidor' para remover os {len(result.red_mods)} mods vermelhos.")
            elif has_yellow:
                print(">>> PIPELINE AMARELO: SERVIDOR COM ALERTAS. REVISE OS MODS SINALIZADOS.")
            else:
                print(">>> PIPELINE REPROVADO: VERIFIQUE OS ERROS DE HARDWARE/CONFIGURAÇÃO.")

            if has_yellow:
                print(f"    {len(result.yellow_mods)} mods amarelos podem ser removidos opcionalmente com 'Higienizar Amarelos'.")
        print("="*75 + "\n")
