@echo off
setlocal
rem Run from any directory. Override SLOTOTTER_CUPL_ROOT if needed.
set "slototter_cupl=C:\Wincupl"
if defined SLOTOTTER_CUPL_ROOT set "slototter_cupl=%SLOTOTTER_CUPL_ROOT%"
set "slototter_flags=-jalxum2"
if not "%~1"=="" if /I not "%~1"=="test" (
    echo Usage: build.cmd [test]
    exit /b 2
)
if not exist "%slototter_cupl%\Shared\cupl.exe" (
    echo WinCUPL not found in %slototter_cupl%.
    echo Set SLOTOTTER_CUPL_ROOT to its installation directory.
    exit /b 2
)
pushd "%~dp0"
if errorlevel 1 exit /b 2
if not exist build mkdir build
if /I "%~1"=="test" (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 generate_vectors.py
    ) else (
        python generate_vectors.py
    )
    if errorlevel 1 goto failed
    set "slototter_flags=-sjalxum2"
)
copy /y slototter.pld build\slototter.pld >nul
if errorlevel 1 goto failed
pushd build
if errorlevel 1 goto failed
rem Remove a stale programming image so a failed build cannot look current.
if exist slototter.jed del slototter.jed
"%slototter_cupl%\Shared\cupl.exe" %slototter_flags% "%slototter_cupl%\Shared\cupl.dl" "%CD%\slototter.pld" >compile.log 2>&1
if errorlevel 1 goto compile_failed
findstr /c:"Design FITS" slototter.fit >nul
if errorlevel 1 goto compile_failed
if not exist slototter.jed goto compile_failed
findstr /c:"Total Logic cells used" /c:"Total Flip-Flop used" /c:"Design FITS" slototter.fit
echo Build passed: %CD%\slototter.jed
if /I "%~1"=="test" echo Functional simulation passed; see slototter.so.
popd
popd
exit /b 0

:compile_failed
type compile.log
if exist slototter.jed del slototter.jed
popd
:failed
popd
echo Build failed.
exit /b 1
