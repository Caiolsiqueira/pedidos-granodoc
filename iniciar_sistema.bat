@echo off
title Pedidos Granodoc - Servidor de Suprimentos
color 0A
cd /d "%~dp0"

echo ========================================================
echo   INICIANDO SISTEMA DE GESTAO DE PEDIDOS GRANODOC
echo ========================================================
echo.

if exist "..\.venv\Scripts\python.exe" (
    echo [OK] Ambiente virtual (.venv) localizado.
    "..\.venv\Scripts\python.exe" run.py
) else (
    echo [AVISO] Usando Python do sistema...
    python run.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Ocorreu um problema ao iniciar o servidor.
    pause
)
