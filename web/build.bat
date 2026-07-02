@echo off
setlocal
cd /d "%~dp0"

if exist dist rmdir /s /q dist
if exist dist.zip del /f /q dist.zip

call pnpm install
if errorlevel 1 exit /b 1

call pnpm run build
if errorlevel 1 exit /b 1

powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.IO.Compression.FileSystem; $zip='dist.zip'; if (Test-Path $zip) { Remove-Item $zip -Force }; $archive=[System.IO.Compression.ZipFile]::Open($zip, 'Create'); try { Get-ChildItem dist -Recurse -File | ForEach-Object { $entry=$_.FullName.Substring((Resolve-Path dist).Path.Length + 1).Replace('\','/'); [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $entry) | Out-Null } } finally { $archive.Dispose() }"
