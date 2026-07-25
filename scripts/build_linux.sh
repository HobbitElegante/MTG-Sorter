#!/usr/bin/env bash
# Build a Linux AppImage via PyInstaller onedir + appimagetool.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ARCH="$(uname -m)"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
TOOLS_DIR="$ROOT/tools"
APPIMAGETOOL="$TOOLS_DIR/appimagetool-${ARCH}.AppImage"
DIST_DIR="$ROOT/dist"
APPDIR="$DIST_DIR/MTG-Sorter.AppDir"
ONEDIR="$DIST_DIR/MTG-Sorter"
OUT_APPIMAGE="$DIST_DIR/MTG-Sorter-${ARCH}.AppImage"

echo "==> Syncing packaging extras"
uv sync --extra packaging --extra dev

echo "==> Running PyInstaller"
rm -rf "$ONEDIR" "$ROOT/build/mtg_sorter" "$APPDIR"
uv run pyinstaller --noconfirm --clean "$ROOT/packaging/mtg_sorter.spec"

if [[ ! -x "$ONEDIR/MTG-Sorter" ]]; then
  echo "error: expected executable at $ONEDIR/MTG-Sorter" >&2
  exit 1
fi

echo "==> Ensuring appimagetool"
mkdir -p "$TOOLS_DIR"
if [[ ! -x "$APPIMAGETOOL" ]]; then
  echo "Downloading appimagetool from $APPIMAGETOOL_URL"
  curl -fsSL -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
  chmod +x "$APPIMAGETOOL"
fi

if [[ ! -x "$APPIMAGETOOL" ]]; then
  echo "error: appimagetool is missing at $APPIMAGETOOL" >&2
  echo "Install it manually from https://github.com/AppImage/appimagetool/releases" >&2
  exit 1
fi

echo "==> Assembling AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ONEDIR/." "$APPDIR/usr/bin/"
# AppRun launches the onedir binary (relative to AppDir).
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/MTG-Sorter" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cp "$ROOT/packaging/mtg-sorter.desktop" "$APPDIR/mtg-sorter.desktop"
cp "$ROOT/packaging/mtg-sorter.desktop" "$APPDIR/usr/share/applications/mtg-sorter.desktop"
cp "$ROOT/packaging/mtg-sorter.png" "$APPDIR/mtg-sorter.png"
cp "$ROOT/packaging/mtg-sorter.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/mtg-sorter.png"

echo "==> Building AppImage"
rm -f "$OUT_APPIMAGE"
export ARCH
# GitHub Actions and other CI runners often lack FUSE; extract-and-run avoids that.
if [[ "${CI:-}" == "true" || "${APPIMAGE_EXTRACT_AND_RUN:-}" == "1" ]]; then
  export APPIMAGE_EXTRACT_AND_RUN=1
fi
set +e
if [[ "${APPIMAGE_EXTRACT_AND_RUN:-}" == "1" ]]; then
  APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$OUT_APPIMAGE"
  status=$?
else
  "$APPIMAGETOOL" "$APPDIR" "$OUT_APPIMAGE"
  status=$?
  if [[ $status -ne 0 ]]; then
    echo "appimagetool failed (exit $status); retrying with APPIMAGE_EXTRACT_AND_RUN=1"
    APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$OUT_APPIMAGE"
    status=$?
  fi
fi
set -e
if [[ $status -ne 0 || ! -f "$OUT_APPIMAGE" ]]; then
  echo "error: appimagetool failed. Install FUSE or use APPIMAGE_EXTRACT_AND_RUN=1." >&2
  echo "Manual: APPIMAGE_EXTRACT_AND_RUN=1 $APPIMAGETOOL \"$APPDIR\" \"$OUT_APPIMAGE\"" >&2
  exit 1
fi

echo "Built: $OUT_APPIMAGE"
