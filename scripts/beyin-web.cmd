@echo off
setlocal EnableExtensions DisableDelayedExpansion
if defined PYTHONPATH (
    set "PYTHONPATH=%~dp0..;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%~dp0.."
)
set "launcher_python="
for %%P in (py.exe) do if not "%%~$PATH:P"=="" set "launcher_python=py -3"
if not defined launcher_python (
    for %%P in (python.exe) do if not "%%~$PATH:P"=="" set "launcher_python=python"
)
rem The message below is UTF-8. The code page is switched only on this path, because the
rem switch outlives the script in the user's console.
if not defined launcher_python chcp 65001 >nul
if not defined launcher_python (
    1>&2 echo Python bulunamadı. Python 3.11 ya da üstünü kurun.
    exit /b 127
)
%launcher_python% -P -m beyin_web %*
exit /b %errorlevel%
