
## Which file do I need?

| You're on | Download | Then run |
|---|---|---|
| Debian, Ubuntu, Mint, Pop!_OS | `hackterm_VERSION-1_all.deb` | `sudo apt install ./hackterm_VERSION-1_all.deb` |
| Fedora, RHEL, openSUSE | `hackterm-VERSION-1.noarch.rpm` | `sudo dnf install ./hackterm-VERSION-1.noarch.rpm` |
| Arch, Omarchy, Manjaro | `hackterm-VERSION-1-any.pkg.tar.zst` | `sudo pacman -U ./hackterm-VERSION-1-any.pkg.tar.zst` |
| Alpine | `hackterm_VERSION-r1_noarch.apk` | `sudo apk add --allow-untrusted ./hackterm_VERSION-r1_noarch.apk` |
| macOS, or Linux with Homebrew | nothing | `brew install farrooss/tap/hackterm` |
| Any Linux, as a Flatpak | `hackterm-x86_64.flatpak` | `flatpak install --user ./hackterm-x86_64.flatpak` |
| Any Linux, as a Snap | `hackterm_VERSION_amd64.snap` | `sudo snap install --dangerous ./hackterm_VERSION_amd64.snap` |
| Any Linux, as an AppImage | `hackterm-x86_64.AppImage` (Intel/AMD) or `hackterm-aarch64.AppImage` (ARM) | `chmod +x hackterm-*.AppImage` then run it |
| Any Linux, no Python | `hackterm-linux-x86_64` (Intel/AMD) or `hackterm-linux-aarch64` (ARM) | `chmod +x hackterm-linux-*` then `./hackterm-linux-x86_64` |
| Anywhere with uv or pipx | nothing | `uv tool install git+https://github.com/Farrooss/hackterm` |

The packages work on any CPU and use your system's Python 3.8+. The standalone binaries include Python, so they need nothing else.

`hackterm-VERSION-py3-none-any.whl` and `hackterm-VERSION.tar.gz` are the Python wheel and source package. `SHA256SUMS` lets you check your download: `sha256sum -c --ignore-missing SHA256SUMS`.
