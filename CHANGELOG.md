# Changelog

## [Unreleased]

### Added

- A Flatpak, a Snap and AppImages (x86_64 and ARM) on each release. Flathub doesn't list terminal-only apps, so the Flatpak is a download from the release page.
- An app icon, and a menu entry with Screensaver and Screensaver Preview actions, for the Flatpak, Snap and AppImage.

## [0.0.4] - 2026-11-28 — The Saver

hackterm can now be your screensaver.

### Added

- `hackterm --screensaver` runs by itself and quits on any key. It's made to be left on, even on an OLED screen, so no part of the picture stays in one place for long:
  - the picture moves by one cell every 20 seconds
  - every 4 minutes the panels swap sides and change size
  - panel titles move along their borders, the borders are dimmer, and the background is near-black, even with a light theme
  - the map changes every 90 seconds, matrix rain takes over every 8 to 12 minutes, and the screen goes black for 2.5 seconds every 15 minutes

  It works with `--theme`, `--map`, `--speed` and `--no-boot`.
- `hackterm --screensavepreview` shows everything the screensaver does in about a minute, so you can see it without waiting.
- For contributors: `tools/burnin_check.py` (in the source) simulates two hours of the screensaver and checks that no cell shows the same thing for 2 minutes.

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
