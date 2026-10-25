[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$pyCmd = "python"
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pyCmd = "py"
}

while ($true) {
    Clear-Host
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host "         PROJECT ZOMBOID BUILD 42 - QUALITY GATE & CI/CD PIPELINE" -ForegroundColor Cyan
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[--- PIPELINE SINGLEPLAYER ---]" -ForegroundColor Green
    Write-Host "[1] Auditoria SP e Teste de Hardware (audit)" -ForegroundColor Green
    Write-Host "[2] Higienizar Modlist SP (default.txt)" -ForegroundColor Green
    Write-Host "[3] Purgar Mods Reprovados do Disco (SP)" -ForegroundColor Green
    Write-Host "[4] Testar Admissao de Novo Mod no SP" -ForegroundColor Green
    Write-Host ""
    Write-Host "[--- PIPELINE MULTIPLAYER (SERVIDOR) ---]" -ForegroundColor Yellow
    Write-Host "[5] Auditoria do Servidor (Build/Compilacao + Cores)" -ForegroundColor Yellow
    Write-Host "[6] Higienizar Servidor - Apenas VERMELHOS (crash/grave)" -ForegroundColor Red
    Write-Host "[7] Higienizar Servidor - VERMELHOS + AMARELOS (crash + alertas)" -ForegroundColor DarkYellow
    Write-Host "[8] Testar Admissao de Novo Mod no Servidor (Build + Hardware MP)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "[--- GERENCIAMENTO AVANCADO DE MODS ---]" -ForegroundColor Magenta
    Write-Host "[9] Remover Mod Especifico por ID (SP, MP ou Ambos)" -ForegroundColor Magenta
    Write-Host "[10] Baixar e Validar Mod/Dependencia via SteamCMD (Tempo Real)" -ForegroundColor Magenta
    Write-Host "[11] Reordenar Modlist Automaticamente (Ordem Topologica de Dependencias)" -ForegroundColor Magenta
    Write-Host "[12] Sincronizar Todos os Mods do Servidor via SteamCMD (Pre-Boot)" -ForegroundColor Cyan
    Write-Host "[13] Baixar/Implantar Todos os Mods via Manifesto JSON (data/server_mods_manifest.json)" -ForegroundColor Green
    Write-Host "[14] Ativar Zero-Steam Boot (Limpar WorkshopItems= e Iniciar Direto Sem Steam)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "[0] Sair" -ForegroundColor Gray
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host ""

    $opt = Read-Host "Escolha uma opcao (0-14)"

    switch ($opt) {
        "1" {
            Write-Host ""
            Write-Host "Executando Auditoria Singleplayer..." -ForegroundColor Cyan
            & $pyCmd "$PSScriptRoot\main.py" audit
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "2" {
            Write-Host ""
            Write-Host "Executando Higienizacao da Modlist Singleplayer..." -ForegroundColor Yellow
            & $pyCmd "$PSScriptRoot\main.py" sanitize
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "3" {
            Write-Host ""
            $confirm = Read-Host "Deseja realmente apagar do disco as pastas dos mods reprovados? (S/N)"
            if ($confirm -eq "S" -or $confirm -eq "s") {
                & $pyCmd "$PSScriptRoot\main.py" purge
            } else {
                Write-Host "Operacao cancelada." -ForegroundColor Yellow
            }
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "4" {
            Write-Host ""
            $modId = Read-Host "Digite o ID do mod para testar admissao no Singleplayer"
            if ($modId) {
                & $pyCmd "$PSScriptRoot\main.py" test-mod $modId
            }
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "5" {
            Write-Host ""
            Write-Host "Executando Auditoria do Servidor e Classificacao de Mods por Cores..." -ForegroundColor Cyan
            & $pyCmd "$PSScriptRoot\main.py" server-audit
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "6" {
            Write-Host ""
            Write-Host "Higienizando Servidor - Removendo apenas mods VERMELHOS (crash/grave)..." -ForegroundColor Red
            $confirm = Read-Host "Confirma remocao dos mods VERMELHOS do servidor? (S/N)"
            if ($confirm -eq "S" -or $confirm -eq "s") {
                & $pyCmd "$PSScriptRoot\main.py" server-sanitize --level red
            } else {
                Write-Host "Operacao cancelada." -ForegroundColor Yellow
            }
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "7" {
            Write-Host ""
            Write-Host "Higienizando Servidor - Removendo mods VERMELHOS + AMARELOS..." -ForegroundColor DarkYellow
            $confirm = Read-Host "Confirma remocao dos mods VERMELHOS e AMARELOS do servidor? (S/N)"
            if ($confirm -eq "S" -or $confirm -eq "s") {
                & $pyCmd "$PSScriptRoot\main.py" server-sanitize --level yellow
            } else {
                Write-Host "Operacao cancelada." -ForegroundColor Yellow
            }
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "8" {
            Write-Host ""
            $modId = Read-Host "Digite o ID do mod para testar admissao no Servidor"
            if ($modId) {
                & $pyCmd "$PSScriptRoot\main.py" server-test-mod $modId
            }
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "9" {
            Write-Host ""
            $modId = Read-Host "Digite o ID do mod que deseja remover"
            if ($modId) {
                Write-Host "Onde deseja remover?"
                Write-Host "[1] Singleplayer apenas"
                Write-Host "[2] Multiplayer (Servidor) apenas"
                Write-Host "[3] Ambos (Singleplayer e Servidor)"
                $whereOpt = Read-Host "Opcao (1-3, padrao: 3)"
                $modeArg = "both"
                if ($whereOpt -eq "1") { $modeArg = "sp" }
                elseif ($whereOpt -eq "2") { $modeArg = "mp" }

                $delOpt = Read-Host "Deseja apagar os arquivos fisicos do disco tambem? (S/N, padrao: N)"
                $delArg = ""
                if ($delOpt -eq "S" -or $delOpt -eq "s") {
                    $delArg = "--delete-files"
                }

                if ($delArg) {
                    & $pyCmd "$PSScriptRoot\main.py" remove-mod $modId --mode $modeArg --delete-files
                } else {
                    & $pyCmd "$PSScriptRoot\main.py" remove-mod $modId --mode $modeArg
                }
            }
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "10" {
            Write-Host ""
            $modOrWs = Read-Host "Digite o ID do mod ou o Workshop ID numerico da Steam para baixar via SteamCMD"
            if ($modOrWs) {
                Write-Host "Onde deseja ativar apos baixar e validar?"
                Write-Host "[1] Singleplayer (default.txt)"
                Write-Host "[2] Multiplayer (servertest.ini)"
                $whereOpt = Read-Host "Opcao (1-2, padrao: 1)"
                $modeArg = if ($whereOpt -eq "2") { "mp" } else { "sp" }

                & $pyCmd "$PSScriptRoot\main.py" install-mod $modOrWs --mode $modeArg
            }
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "11" {
            Write-Host ""
            Write-Host "Calculando e aplicando ordem topologica de dependencias..." -ForegroundColor Cyan
            & $pyCmd "$PSScriptRoot\main.py" reorder
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "12" {
            Write-Host ""
            Write-Host "Sincronizando todos os Workshop IDs do Servidor via SteamCMD..." -ForegroundColor Cyan
            & $pyCmd "$PSScriptRoot\main.py" server-sync
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "13" {
            Write-Host ""
            Write-Host "Baixando e implantando mods a partir do manifesto JSON..." -ForegroundColor Green
            & $pyCmd "$PSScriptRoot\main.py" sync-manifest
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "14" {
            Write-Host ""
            Write-Host "Ativando Zero-Steam Boot no Servidor..." -ForegroundColor Yellow
            & $pyCmd "$PSScriptRoot\main.py" zero-steam
            Write-Host ""
            Read-Host "Pressione ENTER para voltar ao menu..."
        }
        "0" {
            Write-Host "Saindo da pipeline..."
            break
        }
        Default {
            Write-Host "Opcao invalida. Tente novamente." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }

    if ($opt -eq "0") {
        break
    }
}

