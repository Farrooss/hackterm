#!/usr/bin/env bash
# Wrap a standalone hackterm binary (from the release workflow's PyInstaller build) into an AppImage.
#
#   packaging/appimage/build-appimage.sh dist/hackterm-linux-x86_64 x86_64 dist/
#
# Needs appimagetool on PATH or in $APPIMAGETOOL (it runs fine without FUSE via
# --appimage-extract-and-run, which this script passes).
set -euo pipefail
bin=${1:?usage: build-appimage.sh <hackterm binary> <x86_64|aarch64> <out dir>}
arch=${2:?arch}
out=${3:?out dir}
cd "$(dirname "$0")/../.."
root=$(pwd)
tool=${APPIMAGETOOL:-appimagetool}
id=io.github.Farrooss.hackterm
version=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' hackterm.py)

appdir=$(mktemp -d)/hackterm.AppDir
mkdir -p "$appdir/usr/bin" "$appdir/usr/share/applications" "$appdir/usr/share/metainfo" \
         "$appdir/usr/share/icons/hicolor/scalable/apps"
install -m755 "$bin" "$appdir/usr/bin/hackterm"
install -m755 packaging/appimage/AppRun "$appdir/AppRun"
install -m644 "packaging/linux/$id.desktop" "$appdir/usr/share/applications/$id.desktop"
install -m644 "packaging/linux/$id.metainfo.xml" "$appdir/usr/share/metainfo/$id.appdata.xml"
install -m644 "packaging/linux/$id.svg" "$appdir/usr/share/icons/hicolor/scalable/apps/$id.svg"
cp "$appdir/usr/share/applications/$id.desktop" "$appdir/$id.desktop"
cp "packaging/linux/$id.svg" "$appdir/$id.svg"
ln -s "$id.svg" "$appdir/.DirIcon"

mkdir -p "$out"
ARCH=$arch VERSION=$version "$tool" --appimage-extract-and-run --no-appstream "$appdir" \
  "$(cd "$out" && pwd)/hackterm-$arch.AppImage"
echo "Built $out/hackterm-$arch.AppImage"
