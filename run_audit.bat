@echo off
chcp 65001 >nul
where py >nul 2>&1
if %errorlevel% equ 0 (
    py "%~dp0main.py" audit %*
) else (
    python "%~dp0main.py" audit %*
)
pause
