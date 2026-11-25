# hackterm

A cinematic fake-hacking console for your terminal. Mash the keyboard and it looks like you're breaching a mainframe.

It's pure theatre: it makes no network connections and doesn't touch your system.

## Features

- **Boot sequence:** a fake kernel log, a glitchy logo over matrix rain, then "ESTABLISHING UPLINK"
- **Type anything:** every keypress pours out syntax-highlighted exploit code (C, asm, Python, shell)
- **Map panel** (F9 to swap): a rotating ASCII globe with connection arcs, a network map you pivot through host by host, a radar sweep picking up contacts, or a world traceroute
- **Live memory hex dump** that occasionally "leaks" credentials and keys
- **Password cracker** that locks in characters one by one
- **Systems panel:** CPU/NET sparklines, firewall layers being breached, a port scan, the proxy chain
- **Events:** ACCESS GRANTED, INTRUSION ALERT, trace countdown with proxy rerouting, a fake download, fullscreen matrix rain
- **Screen glitches**, plus random events when you're not touching the keyboard
- **Themes:** phosphor green, amber, cyber, red team, and your current Omarchy theme if you use one

## Requirements

- Python 3.8+ (standard library only, no dependencies)
- A truecolor terminal (Alacritty, Kitty, Ghostty, foot, WezTerm, GNOME Terminal, Konsole…)
- At least 60×20; it looks best fullscreen

## Install

```sh
git clone https://github.com/Farrooss/hackterm.git
cd hackterm
ln -s "$PWD/hackterm.py" ~/.local/bin/hackterm
hackterm
```

Or just run `python3 hackterm.py`.

## Controls

| Key | Effect |
|---|---|
| any key | type "code" (typing fast speeds up the cracker and the hex dump) |
| `Tab` | ACCESS GRANTED |
| `Shift-Tab` | INTRUSION ALERT |
| `F1` | trace detected, then reroute through proxies |
| `F2` | fullscreen matrix rain |
| `F3` | fake download |
| `F4` | cycle theme |
| `F5` | turn random events on or off |
| `F6` | show or hide the key hints (they hide automatically after 10s) |
| `F7` / `F8` | slow down / speed up the panels |
| `F9` | swap the map panel: globe, network map, radar, traceroute |
| `Esc Esc` / `Ctrl-C` | quit |

Options: `--no-boot` skips the boot sequence, `--theme N` starts on theme N, `--speed X` sets the panel speed (0.25–2, default 0.6), `--map N` starts on map N (0 globe, 1 network, 2 radar, 3 traceroute), and `--chars N` sets the most characters one keypress types (default 2).

## Omarchy / Hyprland

To get a fullscreen hotkey on Omarchy, add this to `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + CTRL + H", "Hackterm", { tui = "hackterm" })
```

and this to `~/.config/hypr/hyprland.lua`:

```lua
o.window("^org\\.omarchy\\.hackterm$", { fullscreen = true })
```

## License

MIT
