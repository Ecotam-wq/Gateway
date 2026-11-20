@echo off
setlocal
cd /d "%~dp0"
set "ECOTAM_PY=%USERPROFILE%\.platformio\penv\Scripts\python.exe"
if exist "%ECOTAM_PY%" goto start
where py >nul 2>nul
if not errorlevel 1 (
  echo [ECOTAM] Usando Python do Windows...
  py -3 "ecotam_gateway.py"
  goto end
)
where python >nul 2>nul
if not errorlevel 1 (
  python "ecotam_gateway.py"
  goto end
)
echo [ERRO] Python nao encontrado. Instale Python 3 ou abra o PlatformIO.
goto end
:start
"%ECOTAM_PY%" "ecotam_gateway.py"
:end
echo.
echo Pressione qualquer tecla para fechar...
pause >nul
endlocal
