@echo off
chcp 65001 >nul 2>&1
echo ======================================================================
echo     PROJECT ZOMBOID BUILD 42 - QUALITY GATE (use run_pipeline.ps1)
echo ======================================================================
echo.
echo Para o menu interativo completo com cores, execute no PowerShell:
echo.
echo     powershell -ExecutionPolicy Bypass -File "%~dp0run_pipeline.ps1"
echo.
echo Atalhos diretos (sem menu):
echo     python main.py audit                        - Auditoria SP
echo     python main.py server-audit                 - Auditoria Servidor
echo     python main.py server-sanitize --level red   - Higienizar Vermelhos
echo     python main.py server-sanitize --level yellow - Higienizar Vermelhos+Amarelos
echo.
pause
