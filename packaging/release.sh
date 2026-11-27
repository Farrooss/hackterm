#!/usr/bin/env bash
# Release helper. Run from anywhere inside the repo.
#
#   packaging/release.sh bump 0.0.3   set the version in hackterm.py, PKGBUILD, the Homebrew formula and
#                                     the snap, and add a release to the MetaInfo
#   packaging/release.sh sums         after the tag is pushed: fill in the tarball checksum in
#                                     PKGBUILD and the formula, and regenerate .SRCINFO
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

pkgbuild=packaging/aur/PKGBUILD
formula=packaging/homebrew/hackterm.rb
snap=snap/snapcraft.yaml
metainfo=packaging/linux/io.github.Farrooss.hackterm.metainfo.xml
version() { sed -n 's/^__version__ = "\(.*\)"/\1/p' hackterm.py; }

case "${1:-}" in
  bump)
    v=${2:?usage: release.sh bump X.Y.Z}
    sed -i "s/^__version__ = \".*\"/__version__ = \"$v\"/" hackterm.py
    sed -i -e "s/^pkgver=.*/pkgver=$v/" -e "s/^pkgrel=.*/pkgrel=1/" -e "s/^sha256sums=.*/sha256sums=('SKIP')/" "$pkgbuild"
    sed -i -e "s|/tags/v[^/]*\.tar\.gz|/tags/v$v.tar.gz|" -e "s/sha256 \"[0-9a-f]*\"/sha256 \"$(printf '0%.0s' {1..64})\"/" "$formula"
    sed -i "s/^version: \".*\"/version: \"$v\"/" "$snap"
    if ! grep -q "<release version=\"$v\"" "$metainfo"; then
      sed -i "s|^  <releases>|  <releases>\n    <release version=\"$v\" date=\"$(date +%F)\"/>|" "$metainfo"
    fi
    echo "Version set to $v. Add a CHANGELOG entry (and a line for the $metainfo release), commit, then tag v$v."
    ;;
  sums)
    v=$(version)
    url="https://github.com/Farrooss/hackterm/archive/refs/tags/v$v.tar.gz"
    sum=$(curl -fsSL "$url" | sha256sum | cut -d' ' -f1)
    sed -i "s/^sha256sums=.*/sha256sums=('$sum')/" "$pkgbuild"
    sed -i "s/sha256 \"[0-9a-f]*\"/sha256 \"$sum\"/" "$formula"
    (cd packaging/aur && makepkg --printsrcinfo > .SRCINFO)
    echo "v$v tarball sha256: $sum"
    echo "Updated $pkgbuild, packaging/aur/.SRCINFO and $formula."
    ;;
  *)
    sed -n '2,7p' "$0"; exit 1 ;;
esac
