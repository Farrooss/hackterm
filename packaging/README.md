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

One-time setup: add your SSH key to your AUR account, then

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

One-time setup: create a public GitHub repo named `homebrew-tap` with a `Formula/` folder.
Users then install with `brew install farrooss/tap/hackterm`.

Each release, copy `packaging/homebrew/hackterm.rb` to `Formula/hackterm.rb` in that repo, commit and push.
If you have Homebrew, check it first with `brew install --build-from-source ./Formula/hackterm.rb && brew test hackterm`.
