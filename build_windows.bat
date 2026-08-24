@echo off
setlocal

set "REPO_DIR=%~dp0"
set "BASH=C:\devkitPro\msys2\usr\bin\bash.exe"
set "BUILD_START=%DATE% %TIME%"
set "BUILD_LOG=%TEMP%\fe8ex_build_%RANDOM%_%RANDOM%.log"
set "ERROR_LOG=%REPO_DIR%errorlog.txt"
set "ITEM_ID_CAP=0xCD"
if not defined MODERN_TOOLCHAIN_ROOT set "MODERN_TOOLCHAIN_ROOT=/opt/devkitpro/devkitARM"
if not defined BUILD_JOBS set "BUILD_JOBS=%NUMBER_OF_PROCESSORS%"
if "%BUILD_JOBS%"=="" set "BUILD_JOBS=1"
if not defined PYTHON set "PYTHON=/c/Python312/python.exe"

if not exist "%BASH%" (
    echo Could not find devkitPro MSYS bash at:
    echo   %BASH%
    >"%ERROR_LOG%" (
        echo Could not find devkitPro MSYS bash at:
        echo   %BASH%
    )
    exit /b 1
)

"%BASH%" -lc "export PATH='/c/Program Files/Git/cmd:/mingw64/bin:/usr/bin:%MODERN_TOOLCHAIN_ROOT%/bin':$PATH; cd '/c/devkitPro/fe8ex'; make --no-print-directory expansion-modern-toolchain-check PYTHON=%PYTHON% MODERN_TOOLCHAIN_ROOT=%MODERN_TOOLCHAIN_ROOT% FE8_ITEM_ID_CAP=%ITEM_ID_CAP% && make --no-print-directory expansion-modern-rom -j%BUILD_JOBS% PYTHON=%PYTHON% MODERN_TOOLCHAIN_ROOT=%MODERN_TOOLCHAIN_ROOT% MODERN_CONFIG=release MODERN_ABI=aapcs FE8_ITEM_ID_CAP=%ITEM_ID_CAP%" > "%BUILD_LOG%" 2>&1
set "BUILD_RESULT=%ERRORLEVEL%"
type "%BUILD_LOG%"
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$start = [datetime]::Parse($env:BUILD_START); $elapsed = (Get-Date) - $start; '{0:00}:{1:00}:{2:00}' -f [int]$elapsed.TotalHours, $elapsed.Minutes, $elapsed.Seconds"`) do set "BUILD_ELAPSED=%%T"

echo.
if "%BUILD_RESULT%"=="0" (
    echo Build complete.
    echo ROM: build\expansion-modern\release\aapcs\fireemblem8.gba
) else (
    echo Build failed with exit code %BUILD_RESULT%.
    copy /Y "%BUILD_LOG%" "%ERROR_LOG%" >nul
    >>"%ERROR_LOG%" echo.
    >>"%ERROR_LOG%" echo Build failed with exit code %BUILD_RESULT%.
    >>"%ERROR_LOG%" echo Time taken: %BUILD_ELAPSED%
    >>"%ERROR_LOG%" echo Jobs: %BUILD_JOBS%
    echo Full build output saved to:
    echo   %ERROR_LOG%
)
echo Time taken: %BUILD_ELAPSED%
echo Jobs: %BUILD_JOBS%
echo FE8_ITEM_ID_CAP: %ITEM_ID_CAP%
echo MODERN_TOOLCHAIN_ROOT: %MODERN_TOOLCHAIN_ROOT%
echo PYTHON: %PYTHON%
del "%BUILD_LOG%" >nul 2>nul
pause
exit /b %BUILD_RESULT%
