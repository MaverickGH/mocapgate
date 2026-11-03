@echo off
setlocal
chcp 65001 >nul
set "HERE=%~dp0"
if /i not "%HERE:.zip\=%"=="%HERE%" goto :in_zip
if /i not "%HERE:\AppData\Local\Temp\=%"=="%HERE%" goto :in_zip
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo Решения / Fixes: docs\troubleshooting.ru.md , docs\troubleshooting.en.md
  pause
)
exit /b %CODE%
:in_zip
echo [X] Архив не распакован: распакуйте ZIP целиком ("Извлечь все...") и запустите файл из распакованной папки.
echo [X] The archive is not extracted: extract the whole ZIP ("Extract All...") and run the file from the extracted folder.
pause
exit /b 4
