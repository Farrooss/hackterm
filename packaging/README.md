# Releasing

## What happens automatically

Pushing a tag like `v0.0.3` runs `.github/workflows/release.yml`, which:

1. checks the tag matches `__version__` in `hackterm.py`, and that the script runs on Python 3.8 and 3.14
2. builds `.deb`, `.rpm`, `.apk` and Arch packages with [nfpm](https://nfpm.goreleaser.com) from `packaging/nfpm.yaml`
3. builds the Python wheel and sdist
4. builds standalone PyInstaller binaries for x86_64 and aarch64 on Ubuntu 22.04, so they run on older glibc too
5. creates the GitHub release with all of the above, a `SHA256SUMS` file, and notes taken from that version's section of `CHANGELOG.md`

To try the build without releasing, run the workflow by hand from the Actions tab
(`gh workflow run release.yml`). It uploads the files as workflow artifacts instead.

## Steps for a release

```sh
packaging/release.sh bump 0.0.3     # sets the version in hackterm.py, PKGBUILD and the formula
$EDITOR CHANGELOG.md                # add a "## [0.0.3] - YYYY-MM-DD" section
git commit -am "Release 0.0.3"
git tag v0.0.3
git push origin main v0.0.3         # starts the release workflow
packaging/release.sh sums           # once the tag is on GitHub: fills in checksums, regenerates .SRCINFO
git commit -am "Packaging checksums for 0.0.3" && git push
```

Then update the AUR and the Homebrew tap as below.

## AUR

As of 2026-11-26, AUR account registration is temporarily closed, so this is on hold. Until then,
Arch users install the `.pkg.tar.zst` from the release with `sudo pacman -U`.

One-time setup, once you have an account: add your SSH key to your AUR account, then

```sh
git clone ssh://aur@aur.archlinux.org/hackterm.git ~/Work/aur-hackterm
```

Each release:

```sh
cp packaging/aur/PKGBUILD packaging/aur/.SRCINFO ~/Work/aur-hackterm/
cd ~/Work/aur-hackterm
makepkg -si                          # test that it builds and installs
git commit -am "Update to 0.0.3" && git push
```

## Homebrew tap

The tap is [Farrooss/homebrew-tap](https://github.com/Farrooss/homebrew-tap), cloned at `~/Work/homebrew-tap`.
Users install with `brew install farrooss/tap/hackterm`.

Each release, after `release.sh sums`:

```sh
tail -n +3 packaging/homebrew/hackterm.rb > ~/Work/homebrew-tap/Formula/hackterm.rb   # drops the header comment
cd ~/Work/homebrew-tap
git commit -am "hackterm 0.0.3" && git push
```

To check the formula without installing Homebrew, use its container:

```sh
podman run --rm -v "$PWD/packaging/homebrew:/f:ro,Z" docker.io/homebrew/brew bash -c \
  'brew tap-new --no-git test/tap && cp /f/hackterm.rb $(brew --repo test/tap)/Formula/ &&
   brew install test/tap/hackterm && brew test test/tap/hackterm && brew audit --strict test/tap/hackterm'
```
