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
    Write-Host "[9] Sair" -ForegroundColor Gray
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host ""

    $opt = Read-Host "Escolha uma opcao (1-9)"

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
            Write-Host "Saindo da pipeline..."
            break
        }
        Default {
            Write-Host "Opcao invalida. Tente novamente." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }

    if ($opt -eq "9") {
        break
    }
}
