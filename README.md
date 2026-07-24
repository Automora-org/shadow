# Shadow

Windows tray app that freezes Internal Observer pending captures and blocks network for one configured process.

## Features

- Configure **process name** (`.exe` only), **pending directory**, and **hotkeys**
- Settings **auto-save** to `config.json` next to the app (no Save button)
- Hotkeys are set by **clicking the button and pressing a key** (not typed)
- Hide to **system tray** — icon turns **red** when Shadow is ON, **blue** when OFF
- **Disable hotkey (default F8)** — Shadow ON:
  - Capture a screenshot with observer-style red overlay in **Inter** (`timestamp`, `Keys: 0 | Mouse: 0`, window title)
  - Watch the pending directory; replace any new observer files with that frozen screen (same image, new overlay timestamps)
  - Block inbound/outbound network for the configured process via Windows Firewall
- **Enable hotkey (default F9)** — Shadow OFF:
  - Stop replacements
  - Remove the firewall block

## Defaults

| Setting | Default |
|---------|---------|
| Process name | `wordpress.exe` |
| Pending directory | `%USERPROFILE%\.internal-observer\pending\` |
| Disable hotkey | `F8` |
| Enable hotkey | `F9` |

## Requirements

- Windows 10/11
- [uv](https://docs.astral.sh/uv/)
- Python 3.11+ (installed automatically by uv if needed)
- Administrator rights for firewall network blocking

## Setup

```bash
uv sync
```

Include build tools (PyInstaller):

```bash
uv sync --group dev
```

## Run (development)

```bash
uv run shadow
```

Or double-click:

- `run.bat` — sync + launch (UAC may appear)
- `run_as_admin.bat` — force elevation

## Build application

Create a standalone `Shadow.exe` (windowed, requests Administrator):

```bash
uv sync --group dev
uv run pyinstaller --noconfirm --clean shadow.spec
```

Or double-click `build.bat`.

Output:

```text
dist/Shadow.exe
```

`config.json` is created beside the exe on first run.

### Distribute

Copy `dist/Shadow.exe` to any Windows machine. No Python install required. Run as Administrator for network blocking.

With [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed, `build.bat` also produces a setup wizard:

```text
dist/Shadow-<version>-windows-x64-setup.exe
```

## GitHub Releases

CI builds a **Windows Setup installer** (Inno Setup) and publishes a GitHub Release when you push a version tag:

```bash
git tag v1.0.1
git push origin v1.0.1
```

Or run **Actions → Release → Run workflow** and enter a version (e.g. `1.0.1`).

Release asset:

```text
Shadow-<version>-windows-x64-setup.exe
```

Installer includes: modern wizard, Program Files install, Start Menu shortcuts, optional desktop icon, optional sign-in autostart, and uninstaller.

## Project layout

```text
.github/workflows/release.yml  # build + GitHub Release
installer/shadow.iss           # Inno Setup installer script
pyproject.toml                 # project metadata + dependencies (uv)
uv.lock                        # locked dependency versions
shadow.spec                    # PyInstaller build spec
shadow/                        # application package
shadow/assets/Inter-Regular.ttf
shadow_entry.py                # frozen entrypoint for the exe build
build.bat                      # one-click Windows build (+ installer if ISCC present)
run.bat                        # one-click run via uv
README.md
```

## Configuration

Changes save automatically to `config.json` in the app directory (repo root in development, next to `Shadow.exe` when frozen).

Process name must be a bare `.exe` filename (for example `wordpress.exe`). Hotkeys are captured by clicking the hotkey button, then pressing the desired key.

```json
{
  "process_name": "wordpress.exe",
  "pending_dir": "C:\\Users\\You\\.internal-observer\\pending\\",
  "disable_hotkey": "f8",
  "enable_hotkey": "f9"
}
```

## Notes

- Network blocking uses `netsh advfirewall` rules named `ShadowAppBlock_*` and cleans them up on Shadow OFF / exit.
- Global hotkeys work best when the app is elevated.
- Only one process name is blocked (the configured executable path).
- Module packaging uses Hatchling via `pyproject.toml`; day-to-day installs and runs go through **uv**.
