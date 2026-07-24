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
if errorlevel 1 exit /b 1
if not exist "dist\Shadow.exe" (
  echo Build failed: dist\Shadow.exe missing
  exit /b 1
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC (
  for /f "usebackq delims=" %%v in (`uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"`) do set "VERSION=%%v"
  echo Compiling installer with Inno Setup (v%VERSION%)...
  "%ISCC%" "/DMyAppVersion=%VERSION%" "installer\shadow.iss"
  if errorlevel 1 exit /b 1
  echo.
  echo Build OK:
  echo   dist\Shadow.exe
  echo   dist\Shadow-%VERSION%-windows-x64-setup.exe
) else (
  echo.
  echo Build OK: dist\Shadow.exe
  echo Inno Setup 6 not found — skipped setup.exe. Install from https://jrsoftware.org/isinfo.php
)

echo Run as Administrator for network blocking.
endlocal
