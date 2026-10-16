@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title Novel Engine - lanzador
cd /d "%~dp0"

set "RAIZ=%~dp0"
set "BACKEND=%RAIZ%backend"
set "WEB=%RAIZ%apps\web"
set "PY=%BACKEND%\.venv\Scripts\python.exe"
set "DB=%RAIZ%data\novel_engine.sqlite"
rem Rama de trabajo esperada. Si estás en otra, el lanzador avisa pero no cambia de rama.
set "RAMA_ESPERADA=claude/reorganizacion-navegacion"

echo.
echo === Novel Engine: arranque ===
echo.

rem ---- 1. Herramientas --------------------------------------------------------
for %%t in (git node npm curl.exe) do (
  where %%t >nul 2>nul || call :fallo "No se encuentra «%%t» en el PATH. Instálalo y vuelve a intentarlo."
)

rem ---- 2. Repositorio y rama --------------------------------------------------
git rev-parse --is-inside-work-tree >nul 2>nul || call :fallo "Esta carpeta no es un repositorio Git."
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "RAMA=%%b"
echo Rama actual: !RAMA!
if "!RAMA!"=="HEAD" echo [AVISO] Estás en HEAD separado. No se actualiza automáticamente.
if not "!RAMA!"=="%RAMA_ESPERADA%" echo [AVISO] La rama esperada es %RAMA_ESPERADA%. No se cambia de rama; se arranca con «!RAMA!».

rem Cambios locales en archivos versionados. next-env.d.ts lo reescribe Next.js y no cuenta.
set "SUCIO="
for /f "delims=" %%c in ('git status --porcelain --untracked-files=no -- . ":(exclude)apps/web/next-env.d.ts"') do set "SUCIO=1"

rem ---- 3. Actualización segura (solo avance rápido, sin cambios locales) -------
set "SIN_RED="
git remote get-url origin >nul 2>nul || (echo [AVISO] No hay remoto «origin». No se comprueban actualizaciones. & set "SIN_RED=1")
if not defined SIN_RED (
  git fetch origin --quiet >nul 2>nul || (echo [AVISO] No se pudo consultar GitHub. Se arranca con el código local. & set "SIN_RED=1")
)
if not defined SIN_RED (
  git rev-parse --verify --quiet "origin/!RAMA!" >nul 2>nul || (echo [AVISO] No existe origin/!RAMA!. No se actualiza. & set "SIN_RED=1")
)
if not defined SIN_RED (
  for /f %%n in ('git rev-list --count HEAD..origin/!RAMA!') do set "DETRAS=%%n"
  for /f %%n in ('git rev-list --count origin/!RAMA!..HEAD') do set "DELANTE=%%n"
  if "!DETRAS!"=="0" (
    echo Código al día con origin/!RAMA!.
  ) else if not "!DELANTE!"=="0" (
    echo [AVISO] La rama local y origin/!RAMA! han divergido. No se actualiza; resuélvelo a mano.
  ) else if defined SUCIO (
    echo [AVISO] Hay !DETRAS! cambio^(s^) nuevo^(s^) en origin, pero tienes cambios locales sin confirmar. No se actualiza.
  ) else (
    echo Actualizando !DETRAS! cambio^(s^) de origin/!RAMA! ^(solo avance rápido^)...
    git merge --ff-only "origin/!RAMA!" >nul 2>nul || echo [AVISO] La actualización no era de avance rápido. No se ha cambiado nada.
  )
)
if defined SUCIO echo [AVISO] Hay cambios locales sin confirmar. Se arranca con el código actual, tal como está.

rem ---- 4. Dependencias y compilación ------------------------------------------
if not exist "%PY%" call :fallo "Falta el entorno de Python del backend. Crea el entorno: cd backend, luego python -m venv .venv y .venv\Scripts\pip install -e .[dev]"
if not exist "%WEB%\node_modules" call :fallo "Faltan dependencias del frontend. Ejecuta: cd apps\web && npm ci"
if not exist "%WEB%\.next\BUILD_ID" call :fallo "Falta la compilación del frontend. Ejecuta: cd apps\web && npm run build"

rem ---- 5. Instancias ya abiertas ----------------------------------------------
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>nul && call :fallo "Ya hay algo escuchando en el puerto 8000. Cierra la instancia anterior con «Detener Novel Engine.bat» y vuelve a lanzar."
netstat -ano | findstr /R /C:":3000 .*LISTENING" >nul 2>nul && call :fallo "Ya hay algo escuchando en el puerto 3000. Cierra la instancia anterior con «Detener Novel Engine.bat» y vuelve a lanzar."

rem ---- 6. Migraciones: solo se comprueban, nunca se aplican -------------------
if not exist "%DB%" call :fallo "No existe la base de datos %DB%. Crea y migra la base siguiendo docs\MIGRACION_LOCAL.md. El lanzador no migra por su cuenta."
set "AL_DIA="
pushd "%BACKEND%"
for /f "delims=" %%x in ('"%PY%" -c "from app.config import load_settings; from app.db.session import create_engine_for; from app.db.esquema import estado_del_esquema; print(estado_del_esquema(create_engine_for(load_settings().database_url))['al_dia'])" 2^>nul') do set "AL_DIA=%%x"
popd
if /i not "!AL_DIA!"=="True" call :fallo "La base de datos no está al día con las migraciones (o no se pudo leer). No se aplica nada automáticamente. Sigue docs\MIGRACION_LOCAL.md: copia de seguridad verificada y luego la migración."

rem ---- 7. Procesos separados ---------------------------------------------------
echo Arrancando backend en http://127.0.0.1:8000 ...
start "Novel Engine backend" /D "%BACKEND%" cmd /k ""%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
echo Arrancando frontend en http://localhost:3000 ...
start "Novel Engine web" /D "%WEB%" cmd /k "npm run start"

rem ---- 8. Esperar a que estén listos ------------------------------------------
call :esperar "http://127.0.0.1:8000/health" 60 "El backend no respondió en 60 s. Mira la ventana «Novel Engine backend» para ver el error." || goto :fin_error
call :esperar "http://127.0.0.1:3000/" 90 "El frontend no respondió en 90 s. Mira la ventana «Novel Engine web» para ver el error." || goto :fin_error

rem ---- 9. Abrir el navegador solo cuando todo responde ------------------------
echo.
echo Novel Engine está listo. Abriendo el navegador...
start "" "http://localhost:3000"
echo Para detenerlo usa «Detener Novel Engine.bat» o cierra las dos ventanas de servidor.
echo.
pause
exit /b 0

:esperar
rem %1 = URL, %2 = segundos máximos, %3 = mensaje si no responde
set "CODIGO=000"
for /l %%i in (1,1,%~2) do (
  if not "!CODIGO!"=="200" (
    timeout /t 1 /nobreak >nul
    for /f %%c in ('curl.exe -s -o NUL -w "%%{http_code}" %~1 2^>nul') do set "CODIGO=%%c"
  )
)
if "!CODIGO!"=="200" exit /b 0
echo [ERROR] %~3
exit /b 1

:fallo
echo.
echo [ERROR] %~1
echo.
pause
exit /b 1

:fin_error
echo.
echo El arranque se ha detenido. Revisa el mensaje de arriba.
pause
exit /b 1
