@echo off
cd /d "%~dp0"
set "PATH=%CD%;%PATH%"
set PYTHONDONTWRITEBYTECODE=1
"%~dp0python\python.exe" "%~dp0mocapgate.py" studio %*
