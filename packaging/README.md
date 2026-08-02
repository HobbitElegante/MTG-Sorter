# Packaging

Build portable binaries with **PyInstaller** (`onedir`). Linux wraps the folder in an **AppImage**. Windows produces `dist/MTG-Sorter/MTG-Sorter.exe` and zips it for distribution.

Published builds appear on the repository **Releases** page when a version tag is pushed.

## Requirements

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- Optional extra: `uv sync --extra packaging`
- Linux AppImage: `curl` (script downloads `appimagetool` into `tools/`). FUSE helps; without it (or in CI) the script uses `APPIMAGE_EXTRACT_AND_RUN=1`.

## Linux

```bash
./scripts/build_linux.sh
```

Output: `dist/MTG-Sorter-x86_64.AppImage` (arch name follows `uname -m`).

Smoke with an isolated data dir:

```bash
TMP=$(mktemp -d)
MTG_SORTER_DATA_DIR="$TMP" QT_QPA_PLATFORM=offscreen APPIMAGE_EXTRACT_AND_RUN=1 \
  ./dist/MTG-Sorter-x86_64.AppImage &
# then quit the window / kill the process; check $TMP/mtg_sorter.db exists
```

## Windows

Run on Windows (or `windows-latest` in GitHub Actions):

```powershell
.\scripts\build_windows.ps1
```

Output:

- `dist\MTG-Sorter\MTG-Sorter.exe`
- `dist\MTG-Sorter-windows-x64.zip` (folder zipped for Releases)

## Publishing a GitHub Release

CI builds and publishes automatically when you **push a version tag**. Binaries are listed on the release for that tag (and at `/releases/latest`).

### Checklist (each version)

1. Code ready on `main` — local tests green: `uv run pytest`.
2. Version string in `pyproject.toml` matches the tag you will create (e.g. `0.7.1`).
3. Commit and push:
   ```bash
   git push origin main
   ```
4. Create and push the tag:
   ```bash
   git tag v0.7.1
   git push origin v0.7.1
   ```
5. Open the repo **Actions** tab — wait for the **Release** workflow (tests + Linux AppImage + Windows zip). Often ~10–20 minutes.
6. Open **Releases** — `v0.7.1` should list the AppImage and the Windows zip.
7. Optional: edit the release notes.

### If the workflow fails

1. Open the red job log in **Actions** and fix the issue on `main`.
2. Either bump to a new tag (`v0.7.2`) after pushing the fix, or delete the bad tag and recreate it:
   ```bash
   git tag -d v0.7.1
   git push origin :refs/tags/v0.7.1
   git tag v0.7.1
   git push origin v0.7.1
   ```

Known headless pitfalls already handled in `.github/workflows/release.yml`:

- Do **not** install `pytest-qt` in the test job (it auto-loads Qt). Entry point name is `pytest-qt` (hyphen), not `pytestqt`.
- `ui/__init__.py` must stay lazy so formatter tests do not import PySide6.
- Linux build needs system libs (`libegl1`, …) because PyInstaller imports PySide6.

### Prerequisite

The packaging scripts, workflow (`.github/workflows/release.yml`), and related code must already be on the commit you tag. Tagging an old commit will not include AppImage/Windows builds.

## Notes

- User data (SQLite + images) goes to the platform user-data dir when frozen; override with `MTG_SORTER_DATA_DIR`.
- Alembic migration scripts are bundled under `_MEIPASS/mtg_sorter/database/alembic`.
- Workflow file: [`.github/workflows/release.yml`](../.github/workflows/release.yml).
- **Smoke Windows-like UI on Linux:** `QT_STYLE_OVERRIDE=Windows uv run mtg-sorter` (forces the Qt Windows style; useful for layout bugs that only show under the native style, e.g. zero-width combos). Not a substitute for a real Windows VM when validating the `.exe`.
- **Combo standard:** every data `QComboBox` should go through `mtg_sorter.ui.combo.configure_data_combo` (minimum contents length). Do not nest a `QGroupBox` that only wraps a combo inside another group box — that collapsed Language/Theme under native Windows in `v0.9.3`.
