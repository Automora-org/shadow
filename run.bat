@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
  echo uv is required. Install from https://docs.astral.sh/uv/
  exit /b 1
)

uv sync
uv run shadow
endlocal
