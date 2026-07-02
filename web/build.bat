@echo off
setlocal
cd /d "%~dp0"

if exist dist rmdir /s /q dist
if exist dist.zip del /f /q dist.zip

call pnpm install
if errorlevel 1 exit /b 1

call pnpm run build
if errorlevel 1 exit /b 1

powershell -NoProfile -Command "Compress-Archive -Path dist\* -DestinationPath dist.zip -Force"
