@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
  echo uv is required. Install from https://docs.astral.sh/uv/
  exit /b 1
)

echo Syncing dependencies...
uv sync --group dev

echo Building Shadow.exe ...
uv run pyinstaller --noconfirm --clean shadow.spec

if exist "dist\Shadow.exe" (
  echo.
  echo Build OK: dist\Shadow.exe
  echo Run as Administrator for network blocking.
) else (
  echo Build failed.
  exit /b 1
)
endlocal
