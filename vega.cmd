@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 > nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "VEGA_REPOSITORY_LAUNCHER=%~f0"
set "VEGA_PROJECT_ROOT=%~dp0"

pushd "%VEGA_PROJECT_ROOT%" > nul || (
    >&2 echo VEGA could not open its project root: "%VEGA_PROJECT_ROOT%"
    exit /b 1
)

if defined VEGA_PYTHON if exist "%VEGA_PYTHON%" (
    goto run_explicit_python
)

if exist "%~dp0.runtime\python.exe" (
    goto run_bundled_python
)

if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
    goto run_virtualenv_python
)

if exist "%~dp0.venv\Scripts\python.exe" (
    goto run_project_python
)

for %%I in (py.exe) do if not "%%~$PATH:I"=="" goto run_py_launcher
for %%I in (python.exe) do if not "%%~$PATH:I"=="" goto run_path_python

>&2 echo VEGA could not find Python. Set VEGA_PYTHON, activate a virtual environment, or install the Python launcher.
set "VEGA_EXIT_CODE=1"
goto launcher_exit

:run_explicit_python
"%VEGA_PYTHON%" "%~dp0scripts\vega.py" %*
set "VEGA_EXIT_CODE=%ERRORLEVEL%"
goto launcher_exit

:run_bundled_python
"%~dp0.runtime\python.exe" "%~dp0scripts\vega.py" %*
set "VEGA_EXIT_CODE=%ERRORLEVEL%"
goto launcher_exit

:run_virtualenv_python
"%VIRTUAL_ENV%\Scripts\python.exe" "%~dp0scripts\vega.py" %*
set "VEGA_EXIT_CODE=%ERRORLEVEL%"
goto launcher_exit

:run_project_python
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\vega.py" %*
set "VEGA_EXIT_CODE=%ERRORLEVEL%"
goto launcher_exit

:run_py_launcher
py -3 "%~dp0scripts\vega.py" %*
set "VEGA_EXIT_CODE=%ERRORLEVEL%"
goto launcher_exit

:run_path_python
python "%~dp0scripts\vega.py" %*
set "VEGA_EXIT_CODE=%ERRORLEVEL%"

:launcher_exit
popd > nul
exit /b %VEGA_EXIT_CODE%
