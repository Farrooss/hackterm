# Changelog

## [Unreleased]

### Added

- `--screensaver`: hackterm runs by itself and quits on any key. It is safe to leave on an OLED screen: the picture drifts, the layout reshuffles, titles move, borders are dimmer, the background is near-black, maps change by themselves, and the screen blanks briefly every 15 minutes.
- `--screensavepreview`: the screensaver sped up, so everything it does happens within a minute.
- `tools/burnin_check.py` simulates the screensaver and checks that no cell stays the same for long.

## [0.0.3] - 2026-11-26

### Changed

- The standalone binaries are less than half the size: about 9 MB instead of 21 MB.

### Added

- Homebrew tap: `brew install farrooss/tap/hackterm` (Linux and macOS).

## [0.0.2] - 2026-11-26

### Added

- `F10` melts a corner of the screen like hot wax, then snaps it back. It also happens by itself every few minutes.
- Packages for every major distro, built for each release: `.deb` (Debian, Ubuntu), `.rpm` (Fedora, openSUSE), `.apk` (Alpine) and Arch.
- Standalone binaries for x86_64 and aarch64 Linux that don't need Python.
- Install with `uv tool install` or `pipx install`.
- Homebrew formula, and an AUR package ready for when AUR registration reopens.

## [0.0.1] - 2026-11-26

First release.
