@echo off
chcp 65001 >nul
title FirstChip FC3281 / ZC3281 Flasher & Recovery
echo ======================================================================
echo   RECUPERACION OFICIAL FIRSTCHIP FC3281 / ZC3281 / FC3379
echo ======================================================================
echo.
echo Pasos a seguir:
echo 1. Conecta tu memoria USB FirstChip en un puerto USB (preferiblemente USB 2.0 o puerto directo de la placa base).
echo 2. El programa MpTool se abrira a continuacion.
echo 3. Tu pendrive debera aparecer en uno de los puertos numerados (en color amarillo/verde).
echo 4. Si aparece identificado, simplemente haz clic en "Start" (o presiona la barra espaciadora).
echo 5. Espera a que termine (la barra se pondra en VERDE con el mensaje "Pass" / "OK").
echo 6. Desconecta y vuelve a conectar tu memoria USB. Estara como nueva.
echo.
echo NOTA: Si entras en "Setting", la contrasena viene VACIA por defecto (deja el campo en blanco y pulsa OK).
echo.
pause
echo Iniciando FirstChip U3 MpTool...

if exist "%~dp0FCMptools_U3_20241101_3.10.14.8\MpTools.exe" (
    start "" /D "%~dp0FCMptools_U3_20241101_3.10.14.8" "%~dp0FCMptools_U3_20241101_3.10.14.8\MpTools.exe"
) else if exist "%~dp0FCMptools_U3_20251210_3.31.24.14\MpTools.exe" (
    start "" /D "%~dp0FCMptools_U3_20251210_3.31.24.14" "%~dp0FCMptools_U3_20251210_3.31.24.14\MpTools.exe"
) else (
    echo [ERROR] No se encontro el ejecutable MpTools.exe. Por favor revisa las subcarpetas.
    pause
)
