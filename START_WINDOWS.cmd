@echo off
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
py -3.12 mocapgate.py studio %*
