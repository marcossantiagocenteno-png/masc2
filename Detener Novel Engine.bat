@echo off
chcp 65001 >nul
setlocal
title Novel Engine - detener
echo Cerrando las ventanas de Novel Engine (cierre ordenado)...
taskkill /FI "WINDOWTITLE eq Novel Engine backend*" /T >nul 2>nul
taskkill /FI "WINDOWTITLE eq Novel Engine web*" /T >nul 2>nul
echo Si alguna ventana sigue abierta, ciérrala a mano: el servidor no se para por la fuerza.
echo.
pause
