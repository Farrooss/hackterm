#!/usr/bin/env python3
"""hackterm — a cinematic fake-hacking console. Pure theatre: touches nothing.

Type anything  -> fluent exploit code pours out
Tab            -> ACCESS GRANTED          Shift-Tab -> INTRUSION ALERT
F1 trace       F2 matrix       F3 exfil       F4 theme       F5 auto-events
F6 show/hide key hints         F7 / F8 -> slower / faster
F9 cycle map panel (globe, network, radar, traceroute)
F10 melt a corner of the screen
Esc Esc / Ctrl-C -> quit
"""
import math
import os
import random
import re
import select
import signal
import sys
import termios
import time
import tty

__version__ = "0.0.2"
FPS = 30
R = random.Random()

# ───────────────────────────── colours / themes ──────────────────────────────


def rgb(r, g, b):
    return (int(r) << 16) | (int(g) << 8) | int(b)


def hexc(s):
    s = s.strip().lstrip("#")
    return int(s[:6], 16)


def mix(a, b, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    ar, ag, ab = a >> 16, (a >> 8) & 255, a & 255
    br, bg, bb = b >> 16, (b >> 8) & 255, b & 255
    return rgb(ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t)


def mk_theme(name, pri, acc, hi, warn, alert, bg, txt):
    return {
        "name": name, "pri": pri, "acc": acc, "hi": hi, "warn": warn,
        "alert": alert, "bg": bg, "txt": txt,
        "dim": mix(bg, pri, 0.38), "faint": mix(bg, pri, 0.16),
        "border": mix(bg, pri, 0.6), "panel": mix(bg, pri, 0.035),
    }


THEMES = [
    mk_theme("PHOSPHOR", rgb(0, 255, 110), rgb(160, 255, 200), rgb(235, 255, 240),
             rgb(255, 210, 40), rgb(255, 45, 70), rgb(3, 9, 5), rgb(120, 230, 150)),
    mk_theme("AMBER", rgb(255, 176, 0), rgb(255, 220, 140), rgb(255, 245, 225),
             rgb(255, 120, 30), rgb(255, 40, 40), rgb(10, 6, 0), rgb(230, 170, 70)),
    mk_theme("CYBER", rgb(0, 225, 255), rgb(255, 60, 210), rgb(240, 250, 255),
             rgb(255, 230, 0), rgb(255, 40, 90), rgb(4, 4, 14), rgb(130, 200, 235)),
    mk_theme("RED TEAM", rgb(255, 40, 60), rgb(255, 150, 160), rgb(255, 235, 235),
             rgb(255, 200, 0), rgb(255, 255, 255), rgb(10, 2, 3), rgb(230, 110, 120)),
]


def omarchy_theme():
    p = os.path.expanduser("~/.local/state/omarchy/current/theme/colors.toml")
    try:
        kv = dict(re.findall(r'^\s*(\w+)\s*=\s*"(#[0-9a-fA-F]{6})', open(p).read(), re.M))
        return mk_theme("OMARCHY", hexc(kv["accent"]),
                        hexc(kv.get("bright_cyan", kv.get("light_foreground", kv["accent"]))),
                        hexc(kv.get("bright_foreground", "#ffffff")),
                        hexc(kv.get("yellow", "#ffd000")), hexc(kv.get("red", "#ff3040")),
                        hexc(kv.get("darker_background", kv["background"])),
                        hexc(kv.get("foreground", kv["accent"])))
    except Exception:
        return None


# ───────────────────────────────── screen ────────────────────────────────────


class Screen:
    def __init__(self):
        self.prev = None
        self.w = self.h = 0

    def resize(self, w, h):
        self.w, self.h = w, h
        self.prev = None

    def clear(self, bg):
        n = self.w * self.h
        self.ch = [" "] * n
        self.fg = [0] * n
        self.bg = [bg] * n

    def put(self, x, y, c, fg, bg=None):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = y * self.w + x
            self.ch[i] = c
            self.fg[i] = fg
            if bg is not None:
                self.bg[i] = bg

    def text(self, x, y, s, fg, bg=None, maxw=None):
        if maxw is not None:
            s = s[:max(0, maxw)]
        for k, c in enumerate(s):
            self.put(x + k, y, c, fg, bg)
        return x + len(s)

    def fill(self, x, y, w, h, bg, c=" "):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, c, bg, bg)

    def box(self, x, y, w, h, col, title=None, tcol=None, bg=None):
        if w < 2 or h < 2:
            return
        if bg is not None:
            self.fill(x + 1, y + 1, w - 2, h - 2, bg)
        for xx in range(x + 1, x + w - 1):
            self.put(xx, y, "─", col)
            self.put(xx, y + h - 1, "─", col)
        for yy in range(y + 1, y + h - 1):
            self.put(x, yy, "│", col)
            self.put(x + w - 1, yy, "│", col)
        self.put(x, y, "┌", col)
        self.put(x + w - 1, y, "┐", col)
        self.put(x, y + h - 1, "└", col)
        self.put(x + w - 1, y + h - 1, "┘", col)
        if title:
            t = f" {title} "[: max(0, w - 6)]
            self.put(x + 2, y, "┤", col)
            self.text(x + 3, y, t, tcol or col)
            self.put(x + 3 + len(t), y, "├", col)

    def render(self):
        out = ["\x1b[?2026h"]
        w = self.w
        ch, fg, bg = self.ch, self.fg, self.bg
        prev = self.prev
        lf = lb = None
        for y in range(self.h):
            base = y * w
            synced = False
            for x in range(w):
                i = base + x
                c, f, b = ch[i], fg[i], bg[i]
                if prev is not None and prev[0][i] == c and prev[1][i] == f and prev[2][i] == b:
                    synced = False
                    continue
                if not synced:
                    out.append(f"\x1b[{y + 1};{x + 1}H")
                    synced = True
                if f != lf:
                    out.append(f"\x1b[38;2;{f >> 16};{(f >> 8) & 255};{f & 255}m")
                    lf = f
                if b != lb:
                    out.append(f"\x1b[48;2;{b >> 16};{(b >> 8) & 255};{b & 255}m")
                    lb = b
                out.append(c)
        out.append("\x1b[?2026l")
        self.prev = (ch, fg, bg)
        data = "".join(out).encode("utf-8", "replace")
        fd = sys.stdout.fileno()
        while data:
            try:
                n = os.write(fd, data)
                data = data[n:]
            except BlockingIOError:
                select.select([], [fd], [], 0.05)
            except InterruptedError:
                pass


# ─────────────────────────────── big font ────────────────────────────────────

_F = """
A .###.|#...#|#####|#...#|#...#
B ####.|#...#|####.|#...#|####.
C .####|#....|#....|#....|.####
D ####.|#...#|#...#|#...#|####.
E #####|#....|####.|#....|#####
F #####|#....|####.|#....|#....
G .####|#....|#..##|#...#|.####
H #...#|#...#|#####|#...#|#...#
I #####|..#..|..#..|..#..|#####
J #####|...#.|...#.|#..#.|.##..
K #...#|#..#.|###..|#..#.|#...#
L #....|#....|#....|#....|#####
M #...#|##.##|#.#.#|#...#|#...#
N #...#|##..#|#.#.#|#..##|#...#
O .###.|#...#|#...#|#...#|.###.
P ####.|#...#|####.|#....|#....
Q .###.|#...#|#.#.#|#..#.|.##.#
R ####.|#...#|####.|#..#.|#...#
S .####|#....|.###.|....#|####.
T #####|..#..|..#..|..#..|..#..
U #...#|#...#|#...#|#...#|.###.
V #...#|#...#|#...#|.#.#.|..#..
W #...#|#...#|#.#.#|##.##|#...#
X #...#|.#.#.|..#..|.#.#.|#...#
Y #...#|.#.#.|..#..|..#..|..#..
Z #####|...#.|..#..|.#...|#####
0 .###.|#..##|#.#.#|##..#|.###.
1 ..#..|.##..|..#..|..#..|.###.
2 .###.|#...#|..##.|.#...|#####
3 ####.|....#|.###.|....#|####.
4 #...#|#...#|#####|....#|....#
5 #####|#....|####.|....#|####.
6 .###.|#....|####.|#...#|.###.
7 #####|....#|...#.|..#..|..#..
8 .###.|#...#|.###.|#...#|.###.
9 .###.|#...#|.####|....#|.###.
! #|#|#|.|#
. .|.|.|.|#
: .|#|.|#|.
- .....|.....|#####|.....|.....
/ ....#|...#.|..#..|.#...|#....
"""
FONT = {}
for _ln in _F.strip().splitlines():
    FONT[_ln[0]] = _ln[2:].split("|")
FONT[" "] = ["..."] * 5


def big_width(s):
    return sum(len(FONT.get(c, FONT[" "])[0]) + 1 for c in s.upper()) - 1


def draw_big(scr, x, y, s, col, shadow=None, glitch=0.0):
    cx = x
    for c in s.upper():
        g = FONT.get(c, FONT[" "])
        for ry, row in enumerate(g):
            off = R.randint(-2, 2) if glitch and R.random() < glitch else 0
            for rx, p in enumerate(row):
                if p == "#":
                    if shadow is not None:
                        scr.put(cx + rx + 1 + off, y + ry + 1, "▒", shadow)
        cx += len(g[0]) + 1
    cx = x
    for c in s.upper():
        g = FONT.get(c, FONT[" "])
        for ry, row in enumerate(g):
            off = R.randint(-2, 2) if glitch and R.random() < glitch else 0
            for rx, p in enumerate(row):
                if p == "#":
                    scr.put(cx + rx + off, y + ry, "█", col)
        cx += len(g[0]) + 1


# ───────────────────────────── matrix rain ───────────────────────────────────

GLYPHS = [chr(c) for c in range(0xFF66, 0xFF9E)] + list("0123456789Z:.=*+-<>¦|")


class Rain:
    def __init__(self):
        self.w = self.h = 0
        self.drops, self.grid = [], []

    def _drop(self, h, start=False):
        return [R.uniform(-h, 0) if not start else R.uniform(-h * 1.5, h),
                R.uniform(8, 30), R.randint(4, max(5, h // 2 + 4))]

    def setup(self, w, h):
        if (w, h) == (self.w, self.h):
            return
        self.w, self.h = w, h
        self.grid = [[R.choice(GLYPHS) for _ in range(w)] for _ in range(h)]
        self.drops = [self._drop(h, True) for _ in range(w)]

    def update(self, dt):
        if not self.drops:
            return
        for d in self.drops:
            d[0] += d[1] * dt
            if d[0] - d[2] > self.h:
                d[:] = self._drop(self.h)
        for _ in range(max(1, self.w * self.h // 40)):
            self.grid[R.randrange(self.h)][R.randrange(self.w)] = R.choice(GLYPHS)

    def draw(self, scr, x0, y0, th, strength=1.0, mask=None):
        head, pri, bg = th["hi"], th["pri"], th["bg"]
        for x, d in enumerate(self.drops):
            hy = int(d[0])
            ln = d[2]
            for k in range(ln):
                y = hy - k
                if 0 <= y < self.h:
                    if mask and mask(x, y):
                        continue
                    if k == 0:
                        c = mix(bg, head, strength)
                    else:
                        c = mix(bg, pri, strength * (1 - k / ln) ** 1.3)
                    scr.put(x0 + x, y0 + y, self.grid[y][x], c)


# ───────────────────────────── code corpus ───────────────────────────────────
# Lines starting with "|" are program output: they appear instantly.

CORPUS = r"""
/* gibson_breach.c :: ring-0 payload stager */
#include <stdint.h>
#include <sys/mman.h>
#include "quantum_entropy.h"
#define PAYLOAD_SZ   0x1337
#define XOR_SEED     0xDEADBEEF

static uint8_t stage1[] = {
    0x48, 0x31, 0xc0, 0x50, 0x48, 0xbb, 0x2f, 0x62,
    0x69, 0x6e, 0x2f, 0x2f, 0x73, 0x68, 0x53, 0x48,
    0x89, 0xe7, 0x50, 0x57, 0x48, 0x89, 0xe6, 0xb0,
};

static inline uint32_t rotl32(uint32_t v, int r) {
    return (v << r) | (v >> (32 - r));
}

int bypass_firewall(struct node *n, uint32_t key) {
    for (int layer = 0; layer < n->layers; layer++) {
        n->mask[layer] ^= rotl32(key, layer * 7) & XOR_SEED;
        if (!handshake(n, layer, SYN | ACK | URG))
            return -EACCES;
        spoof_ttl(n, 64 + (layer << 2));
    }
    return inject(n, stage1, sizeof(stage1));
}

$ ./scan --stealth --ports 1-65535 10.13.37.42
| [*] SYN stealth scan initiated (decoy x12)
| PORT      STATE     SERVICE     VERSION
| 22/tcp    open      ssh         OpenSSH 7.2p2
| 80/tcp    open      http        nginx 1.10.3
| 443/tcp   filtered  https
| 3306/tcp  open      mysql       5.5.62-log
| 31337/tcp open      elite       ???
| [+] 4 vectors identified in 3.14s

mov     rax, 0x3b
xor     rsi, rsi
xor     rdx, rdx
lea     rdi, [rel shell_path]
push    rdi
syscall
jmp     short decrypt_loop

def crack(target, wordlist):
    for word in mutate(wordlist, leet=True, years=range(1970, 2027)):
        h = sha512_crypt(word, salt=target.salt)
        if constant_time_eq(h, target.hash):
            return word
    return None

async def exfiltrate(session, path):
    async with session.tunnel(hops=7, cipher="chacha20") as t:
        for chunk in stream(path, size=0x10000):
            await t.send(compress(chunk))

$ export PROXYCHAIN="tor://9050,socks5://185.220.101.7,ssh://kiev-relay"
$ ./tunnel --chain $PROXYCHAIN --obfs4 --jitter 40ms
| [+] hop 1 ........ 185.220.101.7     [OK]  41ms
| [+] hop 2 ........ 91.219.236.18     [OK]  88ms
| [+] hop 3 ........ 46.165.230.5      [OK] 120ms
| [*] circuit established :: entropy 7.998 bits/byte

struct packet *forge(uint32_t src, uint32_t dst) {
    struct packet *p = calloc(1, sizeof *p);
    p->ip.saddr  = htonl(src);
    p->ip.daddr  = htonl(dst);
    p->ip.ttl    = 0xFF;
    p->tcp.flags = TH_SYN | TH_PUSH;
    p->tcp.check = csum((uint16_t *)p, sizeof *p >> 1);
    return p;
}

$ sudo ./inject --pid 1 --lib libghost.so
| [*] attaching to pid 1 (init)
| [*] mapping 0x7ffd3a2c0000 rwx
| [+] hook installed: sys_getdents64 -> ghost_getdents
| [+] process hidden. we are invisible.

for (uint64_t k = 0; k < (1ULL << 40); k += STRIDE) {
    __m256i v = _mm256_xor_si256(block, _mm256_set1_epi64x(k));
    if (_mm256_movemask_epi8(_mm256_cmpeq_epi8(v, magic)) == -1)
        goto found;
}

$ ./dump --db customers --table auth --where "role='root'"
| id   user        hash                                  last_login
| 0    root        $6$x9Fq$Kp3...v1Q0                    2026-11-25
| 1    sysop       $6$aZ7e$Lm2...9cQr                    2026-11-24
| [+] 2 rows. piping to cracker...

while ! nc -z 10.13.37.42 31337; do
    knock 7000 8000 9000 && sleep 0.3
done

$ ./rootkit --persist --mode kernel
| [*] compiling module against 6.6.6-hx ... done
| [+] insmod ghost.ko
| [+] persistence: initramfs, systemd-generator, bios-shadow
| [!] watchdog disabled
"""

KW = (r"int|void|char|return|for|while|if|else|static|struct|const|inline|goto|"
      r"uint8_t|uint16_t|uint32_t|uint64_t|def|import|from|class|async|await|with|as|"
      r"None|True|in|do|done|then|fi|sudo|export|mov|xor|lea|push|pop|syscall|jmp|short|"
      r"rax|rdi|rsi|rdx|calloc|sizeof")
TOK = re.compile(
    r"(?P<pre>#(?:include|define)\b)|(?P<com>/\*.*|//.*|(?<!\S)#(?!include|define).*)"
    r"|(?P<str>\"[^\"]*\"?|'[^']*'?)|(?P<num>\b0x[0-9a-fA-F]+\b|\b\d+(?:\.\d+)?\b)"
    r"|(?P<kw>\b(?:" + KW + r")\b)|(?P<prompt>^\$ )|(?P<op>[{}()\[\];=<>+\-*/&|^!~%,:.$])")


class Typer:
    def __init__(self):
        self.src = CORPUS.strip("\n") + "\n\n"
        self.pos = 0
        self.lines = []
        self.cur = ""
        self.cache = {}

    def advance(self, n):
        for _ in range(n):
            if self.pos >= len(self.src):
                self.pos = 0
            if self.cur == "" and self.src.startswith("| ", self.pos):
                end = self.src.index("\n", self.pos)
                self.lines.append("\x01" + self.src[self.pos + 2:end])
                self.pos = end + 1
                continue
            c = self.src[self.pos]
            self.pos += 1
            if c == "\n":
                self.lines.append(self.cur)
                self.cur = ""
            else:
                self.cur += c
        del self.lines[:-300]

    def spans(self, line, th):
        key = (line, th["name"])
        if key in self.cache:
            return self.cache[key]
        if line.startswith("\x01"):
            t = line[1:]
            col = th["acc"] if "[+]" in t else th["warn"] if "[!]" in t else th["txt"]
            res = [(t, mix(th["bg"], col, 0.85))]
        else:
            res, i = [], 0
            cols = {"pre": th["acc"], "com": th["dim"], "str": th["warn"], "num": th["acc"],
                    "kw": th["pri"], "prompt": th["hi"], "op": mix(th["txt"], th["hi"], 0.4)}
            for m in TOK.finditer(line):
                if m.start() > i:
                    res.append((line[i:m.start()], th["txt"]))
                res.append((m.group(), cols[m.lastgroup]))
                i = m.end()
            if i < len(line):
                res.append((line[i:], th["txt"]))
        if len(self.cache) > 2000:
            self.cache.clear()
        self.cache[key] = res
        return res

    def draw(self, scr, x, y, w, h, th, t):
        if h <= 0 or w <= 6:
            return
        vis = self.lines[-(h - 1):] if h > 1 else []
        start_no = len(self.lines) - len(vis) + 1
        rows = vis + [self.cur]
        gut = 4
        for r, line in enumerate(rows):
            yy = y + r
            scr.text(x, yy, f"{(start_no + r) % 10000:>3} ", th["faint"])
            cx = x + gut
            for s, col in self.spans(line, th):
                room = x + w - cx
                if room <= 0:
                    break
                cx = scr.text(cx, yy, s, col, maxw=room)
            if r == len(rows) - 1 and int(t * 2.5) % 2 == 0 and cx < x + w:
                scr.put(cx, yy, "█", th["pri"])


# ───────────────────────────────── globe ─────────────────────────────────────

CITIES = [("SFO", 37.7, -122.4), ("NYC", 40.7, -74.0), ("LON", 51.5, -0.1), ("MOW", 55.7, 37.6),
          ("TYO", 35.7, 139.7), ("SYD", -33.9, 151.2), ("GRU", -23.5, -46.6), ("CPT", -33.9, 18.4),
          ("SIN", 1.3, 103.8), ("REK", 64.1, -21.9), ("DXB", 25.2, 55.3), ("ZRH", 47.4, 8.5)]
SHADE = " .:-=+*#%@"


def land(lon, lat):
    v = (math.sin(lon * 2 + 0.6) * math.cos(lat * 3 - 0.3)
         + 0.6 * math.sin(lon * 5 + lat * 2 + 1.7)
         + 0.35 * math.cos(lon * 9 - lat * 7 + 0.4)
         + 0.2 * math.sin(lon * 17 + lat * 13))
    return v - 0.75 * abs(lat) ** 3


def sph(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo))


class Globe:
    TILT = 0.38
    NAME = "GLOBAL NODE MAP"

    def title(self, t):
        return f"{self.NAME} :: {CITIES[int(t / 4) % len(CITIES)][0]}"

    def __init__(self):
        self.a = 0.0
        self.arcs = []
        self.rain = Rain()

    def update(self, dt, activity=0.0):
        self.a += dt * 0.35
        self.rain.update(dt)
        self.arcs = [a for a in self.arcs if a[2] < 3.2]
        for a in self.arcs:
            a[2] += dt
        while len(self.arcs) < 4:
            i, j = R.sample(range(len(CITIES)), 2)
            self.arcs.append([i, j, R.uniform(-0.8, 0)])

    def fwd(self, p):
        x, y, z = p
        ca, sa = math.cos(self.a), math.sin(self.a)
        x, z = x * ca + z * sa, -x * sa + z * ca
        ct, st = math.cos(self.TILT), math.sin(self.TILT)
        y, z = y * ct - z * st, y * st + z * ct
        return x, y, z

    def draw(self, scr, x0, y0, w, h, th, t):
        self.rain.setup(w, h)
        cx, cy = x0 + w / 2 - 0.5, y0 + h / 2 - 0.5
        ry = h / 2 - 0.6
        rx = ry * 2.1
        if rx > w / 2 - 6:
            rx = w / 2 - 6
            ry = rx / 2.1
        if ry < 2:
            return
        self.rain.draw(scr, x0, y0, th, 0.22,
                       mask=lambda xx, yy: ((x0 + xx - cx) / rx) ** 2 + ((y0 + yy - cy) / ry) ** 2 < 1.15)
        ca, sa = math.cos(-self.a), math.sin(-self.a)
        ct, st = math.cos(-self.TILT), math.sin(-self.TILT)
        bg, pri, dim = th["bg"], th["pri"], th["dim"]
        for yy in range(y0, y0 + h):
            ny = (yy - cy) / ry
            for xx in range(x0, x0 + w):
                nx = (xx - cx) / rx
                d = nx * nx + ny * ny
                if d > 1:
                    if d < 1.12:
                        scr.put(xx, yy, "·", th["faint"])
                    continue
                vz = math.sqrt(1 - d)
                vx, vy = nx, -ny
                # inverse: un-tilt then un-rotate
                py, pz = vy * ct - vz * st, vy * st + vz * ct
                px, pz = vx * ca + pz * sa, -vx * sa + pz * ca
                lat = math.asin(max(-1, min(1, py)))
                lon = math.atan2(px, pz)
                light = max(0.0, -0.45 * vx + 0.35 * vy + 0.82 * vz)
                if land(lon, lat) > 0.25:
                    k = min(len(SHADE) - 1, 1 + int(light * (len(SHADE) - 1)))
                    scr.put(xx, yy, SHADE[k], mix(dim, pri, light))
                else:
                    gl = (abs(math.degrees(lat)) % 30 < 2.2) or (abs(math.degrees(lon)) % 30 < 2.0)
                    if gl:
                        scr.put(xx, yy, "·", mix(bg, dim, 0.4 + light * 0.6))

        def put(px, py, c, col):
            if x0 <= px < x0 + w and y0 <= py < y0 + h:
                scr.put(px, py, c, col)

        def proj(p):
            vx, vy, vz = self.fwd(p)
            return int(round(cx + vx * rx)), int(round(cy - vy * ry)), vz

        for i, j, age in self.arcs:
            if age < 0:
                continue
            a, b = sph(*CITIES[i][1:]), sph(*CITIES[j][1:])
            dot = max(-1, min(1, sum(p * q for p, q in zip(a, b))))
            om = math.acos(dot)
            if om < 1e-3:
                continue
            prog = min(1.0, age / 1.4)
            fade = 1.0 if age < 2.2 else max(0.0, 1 - (age - 2.2))
            n = 40
            for s in range(int(n * prog) + 1):
                u = s / n
                f1, f2 = math.sin((1 - u) * om) / math.sin(om), math.sin(u * om) / math.sin(om)
                lift = 1 + 0.25 * math.sin(math.pi * u) * om / 2
                p = tuple((f1 * p1 + f2 * p2) * lift for p1, p2 in zip(a, b))
                sx, sy, vz = proj(p)
                if vz < -0.05:
                    continue
                head = s == int(n * prog)
                col = mix(bg, th["hi"] if head else th["acc"], fade * (1 if head else 0.75))
                put(sx, sy, "◆" if head and prog < 1 else "•", col)
        for k, (name, la, lo) in enumerate(CITIES):
            sx, sy, vz = proj(sph(la, lo))
            if vz <= 0.05:
                continue
            pulse = 0.5 + 0.5 * math.sin(t * 5 + k)
            put(sx, sy, "●", mix(th["warn"], th["hi"], pulse))
            for k2, c2 in enumerate(name):
                put(sx + 2 + k2, sy, c2, mix(bg, th["warn"], 0.5 + 0.5 * vz))


def line_pts(x0, y0, x1, y1):
    pts, dx, dy = [], abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return pts
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


# ───────────────────────────── network topology ──────────────────────────────

# box-drawing glyph for each set of connections: N=1 E=2 S=4 W=8
BOX = {1: "│", 4: "│", 5: "│", 2: "─", 8: "─", 10: "─", 6: "┌", 12: "┐", 3: "└", 9: "┘",
       7: "├", 13: "┤", 14: "┬", 11: "┴", 15: "┼"}

GATEWAYS = ["gw-edge", "fw01", "vpn02", "border-rtr"]
HOSTS = ["dmz-web01", "mail-relay", "jump01", "ci-runner", "dev-wiki", "print-srv", "vpn-cons",
         "ldap02", "k8s-ctl", "backup-nas", "hr-portal", "git-int", "siem01", "build07"]
CROWNS = ["dc01.corp", "VAULT", "db-cluster", "swift-gw", "mainframe"]


class Topology:
    NAME = "NETWORK MAP"

    def __init__(self):
        self.new()

    def new(self):
        names = R.sample(HOSTS, 5)
        spec = [["you"], [R.choice(GATEWAYS)], names[:3], names[3:], [R.choice(CROWNS)]]
        self.nodes, layers = [], []
        for L, lay in enumerate(spec):
            ids = []
            for k, nm in enumerate(lay):
                fy = (k + 1) / (len(lay) + 1) + (R.uniform(-0.07, 0.07) if len(lay) > 1 else 0)
                self.nodes.append({"name": nm, "L": L, "fy": fy, "st": 2 if L == 0 else 0})
                ids.append(len(self.nodes) - 1)
            layers.append(ids)
        self.edges = set()
        for L in range(len(layers) - 1):
            for a in layers[L]:
                for b in R.sample(layers[L + 1], min(len(layers[L + 1]), R.randint(1, 2))):
                    self.edges.add((a, b))
            for b in layers[L + 1]:
                if not any(e[1] == b for e in self.edges):
                    self.edges.add((R.choice(layers[L]), b))
        self.edges = sorted(self.edges)
        self.path = [0]
        while self.nodes[self.path[-1]]["L"] < len(layers) - 1:
            self.path.append(R.choice([b for a, b in self.edges if a == self.path[-1]]))
        self.hop, self.phase, self.p, self.hold = 0, "move", 0.0, None
        self.packets = []

    def update(self, dt, activity=0.0):
        for pk in self.packets:
            pk[1] += dt * pk[2]
        self.packets = [pk for pk in self.packets if pk[1] < 1]
        while len(self.packets) < 4:
            self.packets.append([R.randrange(len(self.edges)), R.uniform(-1.5, 0), R.uniform(0.5, 1.1)])
        if self.hold is not None:
            self.hold -= dt
            if self.hold < 0:
                self.new()
            return
        rate = dt * (0.7 + activity)
        nxt = self.nodes[self.path[self.hop + 1]]
        if self.phase == "move":
            self.p += rate / 1.1
            if self.p >= 1:
                self.phase, self.p, nxt["st"] = "scan", 0.0, 1
        else:
            self.p += rate / 1.8
            if self.p >= 1:
                nxt["st"] = 2
                self.hop += 1
                self.phase, self.p = "move", 0.0
                if self.hop == len(self.path) - 1:
                    self.hold = 4.0

    def title(self, t):
        if self.hold is not None:
            return f"{self.NAME} :: TARGET OWNED"
        nm = self.nodes[self.path[self.hop + 1]]["name"]
        return f"{self.NAME} :: {'pivot →' if self.phase == 'move' else 'exploiting'} {nm}"

    def draw(self, scr, x0, y0, w, h, th, t):
        if w < 20 or h < 5:
            return
        ncol = 5
        span = (w - 4) / (ncol - 1)
        pos = [(x0 + 1 + round(n["L"] * span), y0 + round(n["fy"] * (h - 1))) for n in self.nodes]
        bg, faint = th["bg"], mix(th["bg"], th["dim"], 0.7)
        onpath = {(self.path[i], self.path[i + 1]) for i in range(len(self.path) - 1)}
        routes = {}
        for a, b in self.edges:
            (ax, ay), (bx, by) = pos[a], pos[b]
            mx = (ax + bx) // 2
            st = 1 if by >= ay else -1
            routes[(a, b)] = ([(x, ay) for x in range(ax, mx)] + [(mx, y) for y in range(ay, by, st)]
                              + [(x, by) for x in range(mx, bx + 1)])
        nodecells = set(pos)

        def paint(cells_by_edge, col):
            bits = {}
            for cells in cells_by_edge:
                for (x1, y1), (x2, y2) in zip(cells, cells[1:]):
                    d1 = 2 if x2 > x1 else 8 if x2 < x1 else 4 if y2 > y1 else 1
                    d2 = {2: 8, 8: 2, 4: 1, 1: 4}[d1]
                    bits[(x1, y1)] = bits.get((x1, y1), 0) | d1
                    bits[(x2, y2)] = bits.get((x2, y2), 0) | d2
            for (x, y), b in bits.items():
                if (x, y) not in nodecells:
                    scr.put(x, y, BOX.get(b, "·"), col)

        owned = [routes[e] for e in onpath if self.nodes[e[1]]["st"] == 2]
        paint([c for e, c in routes.items() if not (e in onpath and self.nodes[e[1]]["st"] == 2)], faint)
        paint(owned, th["pri"])
        if self.hold is None and self.phase == "move":
            cells = routes[(self.path[self.hop], self.path[self.hop + 1])]
            n = max(1, int(self.p * len(cells)))
            paint([cells[:n + 1]], th["acc"])
            if n < len(cells) and cells[n] not in nodecells:
                scr.put(cells[n][0], cells[n][1], "◆", th["hi"])
        for ei, prog, _ in self.packets:
            pts = routes.get(self.edges[ei % len(self.edges)])
            if pts and 0 <= prog < 1:
                x, y = pts[int(prog * len(pts))]
                if (x, y) not in nodecells:
                    scr.put(x, y, "•", mix(bg, th["acc"], 0.8))
        labels = h >= 7
        for i, n in enumerate(self.nodes):
            x, y = pos[i]
            last = n["L"] == ncol - 1
            if i == 0:
                c, col = "■", th["hi"]
            elif n["st"] == 2:
                c, col = ("◆" if last else "●"), (th["hi"] if last else th["pri"])
            elif n["st"] == 1:
                c, col = "◎", th["warn"] if int(t * 6) % 2 else th["hi"]
            else:
                c, col = ("◆" if last else "○"), (th["alert"] if last else th["dim"])
            scr.put(x, y, c, col)
            if labels:
                nm = n["name"][:max(3, int(span) - 1)]
                lx = max(x0, min(x0 + w - len(nm), x - len(nm) // 2))
                lcol = th["txt"] if n["st"] else th["dim"]
                if n["st"] == 1:
                    lcol = th["warn"]
                scr.text(lx, y + 1, nm, lcol)


# ───────────────────────────────── radar ─────────────────────────────────────


class Radar:
    NAME = "RADAR"

    def __init__(self):
        self.a = 0.0
        self.clock = 0.0
        self.targets = [self._tgt() for _ in range(7)]

    def _tgt(self):
        return {"ang": R.uniform(0, math.tau), "r": R.uniform(0.18, 0.92), "lit": -99.0,
                "id": f"{R.choice(['TGT', 'HST', 'NODE', 'SRV'])}-{R.randint(1, 99):02d}",
                "hostile": R.random() < 0.25, "drift": R.uniform(-0.04, 0.04)}

    def update(self, dt, activity=0.0):
        self.clock += dt
        step = dt * 1.4 * (1 + activity * 0.5)
        self.a = (self.a + step) % math.tau
        for tg in self.targets:
            tg["ang"] = (tg["ang"] + tg["drift"] * dt) % math.tau
            if (self.a - tg["ang"]) % math.tau <= step + 1e-9:
                tg["lit"] = self.clock
        if R.random() < dt * 0.06:
            # only respawn a contact that's dark, so blips never pop in mid-glow
            dark = [i for i, tg in enumerate(self.targets) if self.clock - tg["lit"] > 3]
            if dark:
                self.targets[R.choice(dark)] = self._tgt()

    def title(self, t):
        n = sum(1 for tg in self.targets if self.clock - tg["lit"] < 4.5)
        hos = sum(1 for tg in self.targets if tg["hostile"] and self.clock - tg["lit"] < 4.5)
        s = f"{self.NAME} :: SWEEP {int(math.degrees(self.a)) % 360:03d}°  CONTACTS {n}"
        return s + (f"  HOSTILE {hos}" if hos else "")

    def draw(self, scr, x0, y0, w, h, th, t):
        cx, cy = x0 + w / 2 - 0.5, y0 + h / 2 - 0.5
        ry = h / 2 - 0.4
        rx = ry * 2.1
        if rx > w / 2 - 1:
            rx = w / 2 - 1
            ry = rx / 2.1
        if ry < 2:
            return
        bg, pri = th["bg"], th["pri"]
        ringc, faint = mix(bg, th["dim"], 0.6), mix(bg, th["dim"], 0.45)
        icx, icy = int(round(cx)), int(round(cy))
        for yy in range(y0, y0 + h):
            ny = (yy - cy) / ry
            for xx in range(x0, x0 + w):
                nx = (xx - cx) / rx
                r = math.sqrt(nx * nx + ny * ny)
                if r > 1:
                    if r < 1.07:
                        scr.put(xx, yy, "·", th["border"])
                    continue
                d = (self.a - math.atan2(-ny, nx)) % math.tau
                if d < 0.07 + 0.5 / max(1, r * rx):
                    scr.put(xx, yy, "█" if r > 0.05 else "+", mix(pri, th["hi"], 0.5))
                elif d < 1.0:
                    k = 1 - d
                    scr.put(xx, yy, "▒" if k > 0.6 else "░", mix(bg, pri, k * 0.65))
                elif any(abs(r - q) < 0.45 / ry for q in (0.33, 0.66)) or r > 0.97:
                    scr.put(xx, yy, "·", ringc)
                elif xx == icx and yy == icy:
                    scr.put(xx, yy, "+", faint)
        for tg in self.targets:
            age = self.clock - tg["lit"]
            b = max(0.0, 1 - age / 3.8)
            if b <= 0:
                continue
            px = int(round(cx + math.cos(tg["ang"]) * tg["r"] * rx))
            py = int(round(cy - math.sin(tg["ang"]) * tg["r"] * ry))
            col = th["alert"] if tg["hostile"] else th["acc"]
            scr.put(px, py, "◉" if tg["hostile"] else "●", mix(bg, col, 0.25 + 0.75 * b))
            if b > 0.35 and px + 2 + len(tg["id"]) < x0 + w:
                scr.text(px + 2, py, tg["id"], mix(bg, th["txt"], b))


# ─────────────────────────────── traceroute map ──────────────────────────────


class TraceMap:
    NAME = "TRACEROUTE"
    LAT_TOP, LAT_SPAN = 75.0, 130.0

    def __init__(self):
        self.grid_key = None
        self.new()

    def new(self):
        self.route = R.sample(range(len(CITIES)), R.randint(4, 6))
        self.lat = [R.randint(4, 20)]
        self.hop, self.p, self.hold = 0, 0.0, None

    def update(self, dt, activity=0.0):
        if self.hold is not None:
            self.hold -= dt
            if self.hold < 0:
                self.new()
            return
        self.p += dt * (0.7 + activity) / 1.3
        if self.p >= 1:
            self.p = 0.0
            self.hop += 1
            self.lat.append(self.lat[-1] + R.randint(18, 95))
            if self.hop >= len(self.route) - 1:
                self.hold = 4.0

    def title(self, t):
        a, b = CITIES[self.route[0]][0], CITIES[self.route[-1]][0]
        return f"{self.NAME} :: {a} → {b}" + ("  ROUTE LOCKED" if self.hold is not None else "")

    def _grid(self, w, h):
        if self.grid_key != (w, h):
            self.grid_key = (w, h)
            self.grid = []
            for yy in range(h):
                lat = math.radians(self.LAT_TOP - (yy + 0.5) / h * self.LAT_SPAN)
                row = []
                for xx in range(w):
                    v = land(((xx + 0.5) / w * 2 - 1) * math.pi, lat)
                    row.append(None if v <= 0.25 else ":" if v < 0.7 else "+" if v < 1.2 else "#")
                self.grid.append(row)
        return self.grid

    def draw(self, scr, x0, y0, w, h, th, t):
        log = h >= 8
        mh = h - 1 if log else h
        if w < 16 or mh < 4:
            return
        bg = th["bg"]
        landc = mix(bg, th["dim"], 0.75)
        for yy, row in enumerate(self._grid(w, mh)):
            for xx, c in enumerate(row):
                if c:
                    scr.put(x0 + xx, y0 + yy, c, landc)

        def pos(ci):
            _, la, lo = CITIES[ci]
            x = x0 + int((lo + 180) / 360 * (w - 1))
            y = y0 + int(max(0, min(mh - 1, (self.LAT_TOP - la) / self.LAT_SPAN * (mh - 1))))
            return x, y

        for i in range(min(self.hop + 1, len(self.route) - 1)):
            (ax, ay), (bx, by) = pos(self.route[i]), pos(self.route[i + 1])
            pts = line_pts(ax, ay, bx, by)[1:-1]
            if i == self.hop:
                n = int(self.p * len(pts))
                for x, y in pts[:n]:
                    scr.put(x, y, "·", th["acc"])
                if n < len(pts):
                    scr.put(pts[n][0], pts[n][1], "◆", th["hi"])
            else:
                for x, y in pts:
                    scr.put(x, y, "•", th["pri"])
        on = {ci: k for k, ci in enumerate(self.route)}
        for ci, (name, _, _) in enumerate(CITIES):
            x, y = pos(ci)
            if ci in on and on[ci] <= self.hop:
                pulse = 0.5 + 0.5 * math.sin(t * 5 + ci)
                scr.put(x, y, "●", mix(th["warn"], th["hi"], pulse))
                scr.text(x + 1, y, name, th["warn"], maxw=x0 + w - x - 1)
            elif ci in on:
                scr.put(x, y, "○", th["dim"])
            else:
                scr.put(x, y, "·", th["dim"])
        if log:
            parts = [f"{CITIES[self.route[k]][0]} {self.lat[k]}ms" for k in range(min(self.hop + 1, len(self.lat)))]
            if self.hold is None:
                parts.append("…")
            s = " › ".join(parts)
            scr.text(x0, y0 + h - 1, s[-w:], th["txt"])


# ─────────────────────────────── hex dump ────────────────────────────────────

LEAKS = [b"root:x:0:0:root:/root:/bin/bash", b"-----BEGIN RSA PRIVATE KEY-----",
         b"PASSWORD=hunter2", b"AWS_SECRET=wJalrXUtnFEMI/K7MDENG", b"admin@gibson.corp",
         b"GET /admin/backdoor HTTP/1.1", b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5",
         b"BTC:1A1zP1eP5QGefi2DMPTfTL5SLmv7Div"]


class HexDump:
    def __init__(self):
        self.addr = 0x7FFD3A2C0000
        self.rows = []
        self.acc = 0.0
        self.pending = b""

    def _row(self, n):
        if not self.pending and R.random() < 0.06:
            self.pending = R.choice(LEAKS)
        if self.pending:
            data, self.pending = self.pending[:n], self.pending[n:]
            data = bytes(data) + bytes(R.randrange(256) for _ in range(n - len(data)))
            leak = True
        else:
            data = bytes(R.randrange(256) if R.random() < 0.8 else 0 for _ in range(n))
            leak = False
        hot = {R.randrange(n) for _ in range(R.randint(0, 3))}
        row = (self.addr, data, hot, leak)
        self.addr += n
        return row

    def update(self, dt, speed=1.0):
        self.acc += dt * 14 * speed
        self.n = getattr(self, "n", 16)
        while self.acc >= 1:
            self.acc -= 1
            self.rows.append(self._row(self.n))
        del self.rows[:-200]

    def draw(self, scr, x, y, w, h, th, t):
        n = 16 if w >= 76 else 8 if w >= 42 else 4
        self.n = n
        rows = self.rows[-h:]
        for r, (addr, data, hot, leak) in enumerate(rows):
            yy = y + h - len(rows) + r
            age = (len(rows) - 1 - r) / max(1, h)
            base = mix(th["txt"], th["dim"], age)
            cx = scr.text(x, yy, f"{addr & 0xFFFFFFFFFFFF:012x}  ", th["faint"])
            for k, b in enumerate(data[:n]):
                col = th["hi"] if k in hot and age < 0.15 else (th["acc"] if leak else base)
                cx = scr.text(cx, yy, f"{b:02x}", col)
                cx += 2 if k % 8 == 7 else 1
            cx += 1
            asc = "".join(chr(b) if 32 <= b < 127 else "·" for b in data[:n])
            scr.text(cx, yy, asc, th["warn"] if leak else mix(th["bg"], base, 0.7), maxw=x + w - cx)


# ─────────────────────────────── cracker ─────────────────────────────────────

CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%&*?"
TARGETS = ["root@10.13.37.42", "sysop@gibson.corp", "admin@mainframe-07", "svc_backup@vault",
           "jdoe@ellingson-min", "oracle@db-cluster", "ceo@megacorp.biz"]
SECRETS = ["Tr0ub4dor&3x", "god$mode1337", "Sw0rdf1sh!!", "c0rrectH0rse", "Z3r0C00l#95",
           "acidBurn#99", "P@ssw0rd2026", "1nt3rn3tKing", "Mainfr4me!7", "kernelPanic$"]


class Cracker:
    def __init__(self):
        self.new()

    def new(self):
        self.target = R.choice(TARGETS)
        self.secret = R.choice(SECRETS)
        self.locked = 0
        self.prog = 0.0
        self.attempts = R.randint(10 ** 8, 10 ** 9)
        self.salt = "".join(R.choice(CHARSET[:62]) for _ in range(8))
        self.done_t = None
        self.just_done = False

    def boost(self, amt):
        self.prog += amt

    def update(self, dt, t):
        self.just_done = False
        self.attempts += int(R.uniform(2.5e8, 3.1e8) * dt)
        if self.done_t is None:
            self.prog += dt * R.uniform(0.45, 0.9)
            while self.prog >= 1 and self.locked < len(self.secret):
                self.prog -= 1
                self.locked += 1
            if self.locked >= len(self.secret):
                self.done_t = t
                self.just_done = True
        elif t - self.done_t > 3.0:
            self.new()

    def draw(self, scr, x, y, w, h, th, t):
        bg = th["bg"]
        if h < 1:
            return
        scr.text(x, y, "TARGET ", th["dim"])
        cx = scr.text(x + 7, y, self.target, th["hi"])
        scr.text(cx + 2, y, f"sha512crypt $6${self.salt}$" + "".join(
            R.choice("abcdef0123456789") for _ in range(10)) + "…", th["faint"], maxw=x + w - cx - 2)
        if h < 2:
            return
        sx = x
        cy = y + 1 + (h > 4)
        found = self.done_t is not None
        for i, c in enumerate(self.secret):
            if i < self.locked:
                col = th["hi"] if found and int(t * 6) % 2 else th["pri"]
                ch = c
                cbg = mix(bg, th["pri"], 0.18 if not found else 0.35)
            else:
                ch = R.choice(CHARSET)
                col = mix(th["warn"], th["alert"], R.random() * 0.6)
                cbg = mix(bg, th["warn"], 0.06)
            scr.text(sx, cy, f" {ch} ", col, cbg)
            sx += 4
        if found:
            msg = "◄ PASSWORD FOUND"
            if int(t * 4) % 2 == 0:
                scr.text(sx + 1, cy, msg, th["hi"], maxw=x + w - sx - 1)
        ry = cy + 1 + (h > 5)
        if ry < y + h:
            rate = 8.1 + math.sin(t * 1.3) * 0.4 + R.random() * 0.1
            s = f"ATTEMPTS {self.attempts:,}   RATE {rate:.2f} GH/s   MODE dict+mask+rules"
            scr.text(x, ry, s, th["txt"], maxw=w)
        if ry + 1 < y + h:
            total = len(self.secret)
            frac = (self.locked + min(self.prog, 0.99)) / total
            bw = w - 8
            fill = int(bw * frac)
            scr.text(x, ry + 1, "█" * fill, th["pri"], maxw=bw)
            scr.text(x + fill, ry + 1, "░" * (bw - fill), th["faint"])
            scr.text(x + bw + 1, ry + 1, f"{frac * 100:5.1f}%", th["hi"])


# ─────────────────────────────── systems ─────────────────────────────────────

SPARK = "▁▂▃▄▅▆▇█"
PORTS = [(22, "ssh"), (80, "http"), (443, "https"), (3306, "mysql"), (5432, "pgsql"),
         (6379, "redis"), (8080, "proxy"), (31337, "elite")]


class Systems:
    def __init__(self):
        self.cpu = [R.random() for _ in range(80)]
        self.net = [R.random() for _ in range(80)]
        self.acc = 0
        self.layer = 0
        self.lprog = 0.0
        self.port_state = {p: R.choice(["OPEN", "FILTERED", "CLOSED"]) for p, _ in PORTS}
        self.scan_i = 0
        self.reset_t = None
        self.load = 0.5

    def update(self, dt, t, activity):
        self.acc += dt
        self.load += (min(1.0, 0.35 + activity) - self.load) * min(1, dt * 2)
        while self.acc > 0.12:
            self.acc -= 0.12
            self.cpu.append(max(0, min(1, self.load + R.uniform(-0.25, 0.25))))
            self.net.append(max(0, min(1, 0.5 + 0.4 * math.sin(t * 0.7) + R.uniform(-0.3, 0.3))))
            del self.cpu[:-80], self.net[:-80]
            self.scan_i = (self.scan_i + 1) % (len(PORTS) * 3)
            if self.scan_i % 3 == 0 and R.random() < 0.3:
                p = PORTS[R.randrange(len(PORTS))][0]
                self.port_state[p] = R.choice(["OPEN", "OPEN", "FILTERED", "CLOSED"])
        if self.reset_t is None:
            self.lprog += dt * (0.18 + activity * 0.5)
            if self.lprog >= 1:
                self.lprog = 0
                self.layer += 1
                if self.layer >= 5:
                    self.reset_t = t
        elif t - self.reset_t > 4:
            self.reset_t = None
            self.layer = 0

    def draw(self, scr, x, y, w, h, th, t):
        rows = []
        sw = max(4, w - 14)

        def spark(lbl, hist, val, unit):
            def f(yy):
                scr.text(x, yy, lbl, th["dim"])
                hs = hist[-sw:]
                for k, v in enumerate(hs):
                    scr.put(x + 4 + k, yy, SPARK[min(7, int(v * 8))], mix(th["dim"], th["pri"], v))
                scr.text(x + 5 + sw, yy, f"{val}{unit}"[: w - sw - 5], th["hi"])
            return f

        rows.append(spark("CPU", self.cpu, f"{int(self.cpu[-1] * 100):3d}", "%"))
        rows.append(spark("NET", self.net, f"{self.net[-1] * 98:4.1f}", "M"))

        def mem(yy):
            v = 0.62 + 0.05 * math.sin(t)
            bw = w - 10
            scr.text(x, yy, "MEM", th["dim"])
            scr.text(x + 4, yy, "■" * int(bw * v), th["acc"])
            scr.text(x + 4 + int(bw * v), yy, "■" * (bw - int(bw * v)), th["faint"])
            scr.text(x + 5 + bw, yy, f"{int(v * 32)}G", th["hi"])
        rows.append(mem)
        rows.append(None)

        def hdr(s):
            return lambda yy: scr.text(x, yy, s, th["acc"], maxw=w)
        rows.append(hdr("FIREWALL LAYERS"))
        for L in range(5):
            def fw(yy, L=L):
                scr.text(x, yy, f" L{L + 1}", th["dim"])
                bw = max(3, w - 17)
                if L < self.layer:
                    scr.text(x + 4, yy, "█" * bw, th["pri"])
                    scr.text(x + 5 + bw, yy, "BREACHED", th["pri"], maxw=w - bw - 5)
                elif L == self.layer and self.reset_t is None:
                    f = int(bw * self.lprog)
                    scr.text(x + 4, yy, "█" * f, th["warn"])
                    scr.text(x + 4 + f, yy, "░" * (bw - f), th["faint"])
                    if int(t * 4) % 2:
                        scr.text(x + 5 + bw, yy, "BYPASS…", th["warn"], maxw=w - bw - 5)
                else:
                    scr.text(x + 4, yy, "░" * bw, th["faint"])
                    scr.text(x + 5 + bw, yy, "LOCKED", th["dim"], maxw=w - bw - 5)
            rows.append(fw)
        if self.reset_t is not None:
            rows.append(lambda yy: scr.text(x, yy, " >> ALL LAYERS DOWN <<" if int(t * 3) % 2 else "",
                                            th["hi"], maxw=w))
        rows.append(None)
        rows.append(hdr("PORT SCAN"))
        cols = 2 if w >= 34 else 1
        for k in range(0, len(PORTS), cols):
            def pr(yy, k=k):
                for c in range(cols):
                    if k + c >= len(PORTS):
                        break
                    p, svc = PORTS[k + c]
                    st = self.port_state[p]
                    col = {"OPEN": th["pri"], "FILTERED": th["warn"], "CLOSED": th["dim"]}[st]
                    cx = x + c * (w // cols)
                    scanning = (self.scan_i // 3) == k + c
                    scr.text(cx, yy, f"{p:>5}/{svc:<5}", th["hi"] if scanning else th["txt"])
                    scr.text(cx + 12, yy, st[:4], col, maxw=w // cols - 12)
            rows.append(pr)
        rows.append(None)

        def trace(yy):
            scr.text(x, yy, "PROXY CHAIN ", th["dim"])
            for k in range(7):
                scr.put(x + 12 + k * 2, yy, "◆" if (int(t * 8) % 7) == k else "◇", th["acc"])
        rows.append(trace)
        rows.append(lambda yy: scr.text(x, yy, f"UPTIME {int(t) // 3600:02d}:{int(t) // 60 % 60:02d}:{int(t) % 60:02d}"
                                        f"   ENTROPY {7.9 + R.random() * 0.099:.3f}", th["dim"], maxw=w))
        for k, f in enumerate(rows[:h]):
            if f:
                f(y + k)


# ─────────────────────────────── overlays ────────────────────────────────────


class Overlay:
    dur = 3.0

    def __init__(self, t):
        self.t0 = t

    def alive(self, t):
        return t - self.t0 < self.dur

    def center_box(self, scr, w, h, th, col, title=None):
        w = min(w, scr.w - 2)
        h = min(h, scr.h - 2)
        x, y = (scr.w - w) // 2, (scr.h - h) // 2
        scr.fill(x - 1, y - 1, w + 2, h + 2, th["bg"])
        scr.box(x, y, w, h, col, title, th["hi"], bg=mix(th["bg"], col, 0.06))
        return x, y, w, h


class Banner(Overlay):
    def __init__(self, t, big, sub, colkey, dur=2.8, alarm=False):
        super().__init__(t)
        self.big, self.sub, self.colkey, self.dur, self.alarm = big, sub, colkey, dur, alarm

    def draw(self, scr, th, t):
        e = t - self.t0
        col = th[self.colkey]
        if self.alarm and int(e * 6) % 2 == 0:
            col = th["hi"]
        bw = big_width(self.big)
        if bw + 8 <= scr.w - 2:
            w, h = bw + 10, 11
            x, y, w, h = self.center_box(scr, w, h, th, col)
            # wipe-in reveal
            draw_big(scr, x + 5, y + 2, self.big, col, mix(th["bg"], col, 0.35),
                     glitch=0.25 if e < 0.35 else 0.02)
            reveal = min(1, e / 0.4)
            for yy in range(y + 1, y + h - 1):
                for xx in range(x + 1 + int((w - 2) * reveal), x + w - 1):
                    scr.put(xx, yy, " ", col, mix(th["bg"], col, 0.06))
            sub = self.sub[: int(len(self.sub) * min(1, e / 1.0))]
            scr.text(x + (w - len(self.sub)) // 2, y + h - 2, sub, th["hi"])
        else:
            x, y, w, h = self.center_box(scr, len(self.big) + 10, 5, th, col)
            scr.text(x + 5, y + 1, self.big, col)
            scr.text(x + 2, y + 3, self.sub[: w - 4], th["hi"])


class Trace(Overlay):
    dur = 7.5
    HOPS = ["185.220.101.7  DE  tor-exit", "91.219.236.18  UA  relay", "46.165.230.5   NL  bulletproof",
            "103.75.190.12  SG  vps", "200.98.143.77  BR  botnet", "5.188.62.140   RU  relay",
            "198.51.100.66  ?? dark-hop"]

    def draw(self, scr, th, t):
        e = t - self.t0
        x, y, w, h = self.center_box(scr, 54, 14, th, th["alert"], "!! TRACE DETECTED !!")
        if e < 3.0:
            left = 3.0 - e
            col = th["alert"] if int(e * 8) % 2 else th["hi"]
            scr.text(x + 3, y + 2, "INCOMING TRACE FROM: FBI-CYBER/NODE-44", col)
            scr.text(x + 3, y + 4, f"TIME TO LOCATE  00:{int(left):02d}.{int((left % 1) * 100):02d}", th["warn"])
            bw = w - 6
            f = int(bw * e / 3.0)
            scr.text(x + 3, y + 6, "█" * f, th["alert"])
            scr.text(x + 3 + f, y + 6, "░" * (bw - f), th["faint"])
            scr.text(x + 3, y + 8, "triangulating: " + ".".join(str(R.randrange(256)) for _ in range(4)),
                     th["dim"])
        else:
            scr.text(x + 3, y + 1, "REROUTING THROUGH PROXY CHAIN...", th["acc"])
            n = min(len(self.HOPS), int((e - 3.0) / 0.4) + 1)
            for k in range(n):
                scr.text(x + 3, y + 3 + k, f"→ hop {k + 1}  {self.HOPS[k]}", th["txt"], maxw=w - 14)
                scr.text(x + w - 8, y + 3 + k, "[OK]", th["pri"])
            if e > 3.0 + len(self.HOPS) * 0.4 + 0.3:
                if int(e * 4) % 2:
                    scr.text(x + (w - 24) // 2, y + h - 2, "◄◄  TRACE LOST  ►►", th["hi"])


class Exfil(Overlay):
    dur = 7.0
    FILES = ["mainframe.db", "payroll_2026.xlsx", "ssh_host_keys.tar", "board_minutes.pdf",
             "prototype_schematics.cad", "garbage_file.gbs", "satellite_codes.enc", "emails.mbox"]

    def __init__(self, t):
        super().__init__(t)
        self.size = R.uniform(2.0, 9.0)

    def draw(self, scr, th, t):
        e = t - self.t0
        x, y, w, h = self.center_box(scr, 60, 15, th, th["acc"], "EXFILTRATION")
        frac = min(1.0, (e / 5.5) ** 0.85)
        scr.text(x + 3, y + 2, f"DOWNLOADING  /var/core/mainframe.db  ({self.size:.2f} GB)", th["hi"], maxw=w - 6)
        bw = w - 14
        f = int(bw * frac)
        scr.text(x + 3, y + 4, "▓" * f, th["pri"])
        scr.text(x + 3 + f, y + 4, "░" * (bw - f), th["faint"])
        scr.text(x + 4 + bw, y + 4, f"{frac * 100:5.1f}%", th["hi"])
        spd = 0 if frac >= 1 else 80 + 40 * math.sin(e * 3) + R.random() * 15
        eta = 0 if frac >= 1 else (1 - frac) * 5.5
        scr.text(x + 3, y + 5, f"{frac * self.size:6.2f} GB   {spd:6.1f} MB/s   ETA {eta:4.1f}s   "
                               f"tunnel: chacha20/7 hops", th["dim"], maxw=w - 6)
        n = int(frac * len(self.FILES))
        for k in range(min(n, h - 9)):
            fn = self.FILES[k]
            scr.text(x + 3, y + 7 + k, f"  ✓ {fn}", th["txt"])
            scr.text(x + w - 14, y + 7 + k, f"{R.randrange(10, 999)} MB" if k == n - 1 else "done", th["dim"])
        if frac >= 1 and int(e * 4) % 2:
            scr.text(x + (w - 22) // 2, y + h - 2, "TRANSFER COMPLETE", th["hi"])


# ───────────────────────────────── input ─────────────────────────────────────

SEQ = {"[Z": "BTAB", "OP": "F1", "OQ": "F2", "OR": "F3", "OS": "F4",
       "[11~": "F1", "[12~": "F2", "[13~": "F3", "[14~": "F4", "[15~": "F5", "[17~": "F6", "[18~": "F7", "[19~": "F8", "[20~": "F9", "[21~": "F10",
       "[1P": "F1", "[1Q": "F2", "[1R": "F3", "[1S": "F4"}
CSI = re.compile(r"\x1b(\[[0-9;?]*[ -/]*[@-~]|O.)")


def parse_keys(s):
    keys, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\x1b":
            m = CSI.match(s, i)
            if m:
                keys.append(SEQ.get(m.group(1), "TYPE"))
                i = m.end()
                continue
            if i + 1 < len(s):
                keys.append("TYPE")
                i += 2
                continue
            keys.append("ESC")
        elif c == "\t":
            keys.append("TAB")
        elif c == "\x03":
            keys.append("QUIT")
        else:
            keys.append("TYPE")
        i += 1
    return keys


# ───────────────────────────────── app ───────────────────────────────────────

BOOT = [
    "[    0.000000] Linux version 6.6.6-hx (root@ghost) (gcc 14.2.1) #1 SMP PREEMPT_DYNAMIC",
    "[    0.000000] Command line: BOOT_IMAGE=/vmlinuz-hx root=/dev/mapper/void ro quiet stealth=1",
    "[    0.004512] x86/cpu: SGX disabled by BIOS (we disabled it)",
    "[    0.011337] Memory: 32891004K/33554432K available (shadow pages reserved)",
    "[    0.031415] smpboot: CPU0: Neural Co-processor X9 (family: 0x1337)",
    "[    0.120000] Spectre V2 : Mitigation: none. We are the vulnerability.",
    "[    0.322000] tun0: entropy pool seeded from cosmic background radiation",
    "[  OK  ] Started Quantum Entropy Daemon.",
    "[  OK  ] Mounted /dev/shadowfs on /void.",
    "[  OK  ] Reached target Anonymity Layer.",
    "[  OK  ] Started Proxy Chain Orchestrator (7 hops).",
    "[  OK  ] Started Packet Forgery Service.",
    "[ WARN ] Ethics module not found. Continuing.",
    "[  OK  ] Loaded 14,344,392 wordlist entries into GPU memory.",
    "[  OK  ] Reached target Hack The Planet.",
]

# boot logo: a padlock that springs open when the uplink completes
LOCK_SHUT = [
    "",
    "    ▄▄▄▄▄▄▄",
    "   ██▀▀▀▀▀██",
    "   ██     ██",
    "   ██     ██",
    "▄█████████████▄",
    "██████▀ ▀██████",
    "██████▄ ▄██████",
    "███████ ███████",
    "▀█████████████▀",
]
LOCK_OPEN = [
    "    ▄▄▄▄▄▄▄",
    "   ██▀▀▀▀▀██",
    "   ██     ██",
    "   ▀▀     ██",
    "          ██",
    "▄█████████████▄",
    "██████▀ ▀██████",
    "██████▄ ▄██████",
    "███████ ███████",
    "▀█████████████▀",
]

FOOTER_MSGS = ["[*] payload staged in /dev/shm/.x", "[+] session 4 opened (10.13.37.42:31337)",
               "[*] rotating MAC 3c:22:fb:**:**:**", "[+] hash dump: 1,204 entries",
               "[*] heartbeat from c2.void ok", "[+] privilege: uid=0(root) gid=0(root)",
               "[*] clearing /var/log/auth.log", "[!] IDS signature updated — evading",
               "[*] tor circuit rebuilt", "[+] new vector: CVE-2026-31337"]


class App:
    def __init__(self, boot=True):
        self.scr = Screen()
        self.themes = THEMES[:]
        om = omarchy_theme()
        if om:
            self.themes.append(om)
        self.ti = 0
        self.typer = Typer()
        self.globe = Globe()
        self.maps = [self.globe, Topology(), Radar(), TraceMap()]
        self.mi = 0
        self.hex = HexDump()
        self.crack = Cracker()
        self.sys = Systems()
        self.rain = Rain()
        self.overlay = None
        self.alarm_until = 0
        self.flash_until = 0
        self.glitch_until = 0
        self.next_glitch = 3
        self.melt = None       # (start, corner, per-column drip params)
        self.next_melt = R.uniform(45, 90)
        self.matrix_until = 0
        self.last_key = -99
        self.activity = 0.0
        self.esc_t = -99
        self.auto_events = True
        self.next_event = 60
        self.last_popup = -99  # last automatic popup, for the cooldown
        self.hints = True
        self.hint_until = None
        self.phase = "boot" if boot else "main"
        self.t0 = time.monotonic()
        self.boot_end = 6.8
        self.resized = True
        self.typed_auto = 0.0
        self.toast = None
        self.typer.advance(400)
        self.speed = 0.6       # panel animation speed multiplier (F7/F8)
        self.chars = 2         # max characters typed per keypress

    @property
    def th(self):
        return self.themes[self.ti]

    # ── events
    def trigger(self, name, t):
        self.glitch_until = t + 0.25
        if name == "grant":
            self.overlay = Banner(t, "ACCESS GRANTED", "root shell obtained :: uid=0(root)", "pri")
            self.flash_until = t + 0.12
        elif name == "deny":
            self.overlay = Banner(t, "INTRUSION ALERT", "!! countermeasures engaged — hold position !!",
                                  "alert", 3.2, alarm=True)
            self.alarm_until = t + 3.2
        elif name == "trace":
            self.overlay = Trace(t)
            self.alarm_until = t + 3.0
        elif name == "exfil":
            self.overlay = Exfil(t)
        elif name == "matrix":
            self.overlay = None
            self.matrix_until = 0 if self.matrix_until > t else t + 12

    def on_key(self, k, t):
        if self.phase == "boot":
            if k in ("ESC", "QUIT"):
                if k == "QUIT":
                    raise SystemExit
            self.phase = "main"
            self.glitch_until = t + 0.4
            self.hint_until = t + 10
            return
        if k == "QUIT":
            raise SystemExit
        if k == "ESC":
            if t - self.esc_t < 1.0:
                raise SystemExit
            self.esc_t = t
            return
        if k == "TYPE":
            self.typer.advance(R.randint(1, self.chars))
            self.last_key = t
            self.activity = min(1.0, self.activity + 0.06)
            self.crack.boost(0.08)
            if self.matrix_until > t and t - (self.matrix_until - 12) > 1.0:
                self.matrix_until = 0
        elif k == "TAB":
            self.trigger("grant", t)
        elif k == "BTAB":
            self.trigger("deny", t)
        elif k == "F1":
            self.trigger("trace", t)
        elif k == "F2":
            self.trigger("matrix", t)
        elif k == "F3":
            self.trigger("exfil", t)
        elif k == "F4":
            self.ti = (self.ti + 1) % len(self.themes)
            self.scr.prev = None
            self.glitch_until = t + 0.3
            self.toast = (t, f"THEME :: {self.th['name']}")
        elif k == "F5":
            self.auto_events = not self.auto_events
            self.toast = (t, f"AUTO EVENTS :: {'ON' if self.auto_events else 'OFF'}")
        elif k == "F6":
            self.hints = not self.hints
            self.hint_until = None if self.hints else 0
        elif k == "F9":
            self.mi = (self.mi + 1) % len(self.maps)
            self.glitch_until = t + 0.2
            self.toast = (t, f"MAP :: {self.maps[self.mi].NAME}")
        elif k == "F10":
            self.start_melt(t)
        elif k in ("F7", "F8"):
            steps = [0.25, 0.4, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0]
            i = min(range(len(steps)), key=lambda j: abs(steps[j] - self.speed))
            i = max(0, min(len(steps) - 1, i + (1 if k == "F8" else -1)))
            self.speed = steps[i]
            self.toast = (t, f"SPEED :: {self.speed:g}x")

    # ── update
    def update(self, dt, t):
        self.activity = max(0.0, self.activity - dt * 0.25)
        if self.phase != "main":
            self.rain.update(dt)
            if t > self.boot_end:
                self.phase = "main"
                self.glitch_until = t + 0.4
                self.hint_until = t + 10
            return
        pdt = dt * self.speed
        if t - self.last_key > 3.0:
            self.typed_auto += pdt * 14
            n = int(self.typed_auto)
            if n:
                self.typer.advance(n)
                self.typed_auto -= n
        self.maps[self.mi].update(pdt, self.activity)
        self.hex.update(pdt, 1 + self.activity)
        self.crack.update(pdt, t)
        self.sys.update(pdt, t, self.activity)
        if self.matrix_until > t:
            self.rain.update(pdt)
        if self.overlay and not self.overlay.alive(t):
            self.overlay = None
        quiet = not self.overlay and self.matrix_until < t and t - self.last_popup > 90
        if self.crack.just_done and quiet and R.random() < 0.25:
            self.trigger("grant", t)
            self.last_popup = t
            self.next_event = max(self.next_event, t + 60)
        if t > self.next_glitch:
            self.glitch_until = t + R.uniform(0.06, 0.2)
            self.next_glitch = t + R.uniform(4, 11)
        if t > self.next_melt:
            self.next_melt = t + R.uniform(45, 90)
            if not self.overlay and self.matrix_until < t:
                self.start_melt(t)
        if self.melt and t - self.melt[0] > self.MELT_DUR:
            self.melt = None
            self.glitch_until = t + 0.1   # snap back with a quick tear
        if self.auto_events and t > self.next_event:
            self.next_event = t + R.uniform(60, 120)
            if quiet:
                self.trigger(R.choice(["trace", "exfil", "grant", "deny"]), t)
                self.last_popup = t

    # ── draw
    def draw(self, t):
        scr, th = self.scr, self.th
        bgc = th["bg"]
        if t < self.flash_until:
            bgc = mix(th["bg"], th["pri"], 0.5)
        scr.clear(bgc)
        if scr.w < 60 or scr.h < 20:
            msg = "ENLARGE TERMINAL ▸ 60×20 MIN"
            scr.text(max(0, (scr.w - len(msg)) // 2), scr.h // 2, msg, th["pri"])
            return
        if self.phase == "boot":
            self.draw_boot(t)
        elif self.matrix_until > t:
            self.draw_matrix(t)
        else:
            self.draw_main(t)
            if self.overlay:
                self.overlay.draw(scr, th, t)
        if self.toast and t - self.toast[0] < 1.6:
            s = f" {self.toast[1]} "
            scr.text(scr.w - len(s) - 2, 1, s, th["bg"], th["pri"])
        if self.melt and self.phase == "main":
            self.draw_melt(t)
        if t < self.glitch_until:
            self.glitch()

    def draw_boot(self, t):
        scr, th = self.scr, self.th
        if t < 2.6:
            n = int(t / 2.6 * len(BOOT)) + 1
            for k, line in enumerate(BOOT[:n][-(scr.h - 2):]):
                col = th["warn"] if "WARN" in line else th["pri"] if "OK" in line else th["txt"]
                if line.startswith("[  OK  ]"):
                    scr.text(1, 1 + k, "[  ", th["txt"])
                    scr.text(4, 1 + k, "OK", th["pri"])
                    scr.text(6, 1 + k, "  ]" + line[8:], th["txt"], maxw=scr.w - 8)
                else:
                    scr.text(1, 1 + k, line, col, maxw=scr.w - 2)
            return
        self.rain.setup(scr.w, scr.h)
        self.rain.draw(scr, 0, 0, th, min(1.0, (t - 2.6) * 1.5) * 0.55)
        p = max(0.0, min(1.0, (t - 4.0) / 1.9))     # uplink progress; the lock pops at 1
        opened = p >= 1
        art = LOCK_OPEN if opened else LOCK_SHUT
        aw = max(len(r) for r in art)
        bw = 31
        x, y = (scr.w - aw) // 2, max(1, scr.h // 2 - 8)
        bx = (scr.w - bw) // 2
        scr.fill(bx - 3, y - 1, bw + 6, len(art) + 9, th["bg"])
        # glitchy on arrival, steady while locked, then shakes harder as the crack nears
        g = 0.3 if t < 3.2 else 0.04 + (0.25 * (p - 0.7) / 0.3 if 0.7 < p < 1 else 0)
        shake = R.choice([-1, 0, 1]) if 0.8 < p < 1 else 0
        pop = opened and t - (4.0 + 1.9) < 0.25
        col = th["hi"] if pop else th["pri"]
        shadow = mix(th["bg"], th["pri"], 0.35)
        for layer in (0, 1):
            for ry, row in enumerate(art):
                off = shake + (R.randint(-2, 2) if R.random() < g else 0)
                for rx, c in enumerate(row):
                    if c == " " or (layer == 0 and c == "▀"):
                        continue
                    if layer == 0:
                        scr.put(x + rx + off + 1, y + ry + 1, "▒", shadow)
                    else:
                        scr.put(x + rx + off, y + ry, c, th["acc"] if opened and ry < 5 else col)
        ty = y + len(art) + 2
        sub = "h a c k t e r m"
        scr.text((scr.w - len(sub)) // 2, ty, sub, th["dim"])
        if t > 4.0:
            lbl = "ESTABLISHING UPLINK" + "." * (int(t * 4) % 4)
            scr.text(bx, ty + 2, lbl, th["acc"])
            f = int(bw * p)
            scr.text(bx, ty + 3, "█" * f, th["pri"])
            scr.text(bx + f, ty + 3, "░" * (bw - f), th["faint"])
            if opened:
                scr.text(bx, ty + 4, "UPLINK SECURE ✓", th["hi"])
        else:
            tag = f"v{__version__} // intrusion suite"
            scr.text((scr.w - len(tag)) // 2, ty + 2, tag, th["faint"])

    def draw_matrix(self, t):
        scr, th = self.scr, self.th
        self.rain.setup(scr.w, scr.h)
        self.rain.draw(scr, 0, 0, th, 1.0)
        e = t - (self.matrix_until - 12)
        if e > 2.0:
            word = "SYSTEM OVERRIDE"
            if big_width(word) + 6 < scr.w:
                bw = big_width(word)
                x, y = (scr.w - bw) // 2, scr.h // 2 - 3
                scr.fill(x - 3, y - 2, bw + 6, 9, th["bg"])
                draw_big(scr, x, y, word, th["hi"], mix(th["bg"], th["pri"], 0.4), glitch=0.03)

    def draw_main(self, t):
        scr, th = self.scr, self.th
        W, H = scr.w, scr.h
        alarm = t < self.alarm_until and int(t * 6) % 2 == 0
        bcol = th["alert"] if alarm else th["border"]
        tcol = th["hi"] if alarm else th["pri"]
        pbg = th["panel"] if t >= self.flash_until else None

        # header
        scr.fill(0, 0, W, 1, mix(th["bg"], th["pri"], 0.12))
        hb = mix(th["bg"], th["pri"], 0.12)
        cx = scr.text(1, 0, "▓▒░ ", th["pri"], hb)
        cx = scr.text(cx, 0, "HACKTERM", th["hi"], hb)
        cx = scr.text(cx, 0, f" v{__version__} ░▒▓", th["pri"], hb)
        if alarm or t < self.alarm_until:
            mid = "!! INTRUSION COUNTERMEASURES ACTIVE !!"
            mcol = th["alert"] if int(t * 6) % 2 else th["hi"]
        else:
            dot = "●" if int(t * 2) % 2 else "○"
            mid = f"UPLINK {dot} SECURE   PROXIES 7   ENC AES-256-GCM   NODE 10.13.37.42"
            mcol = th["txt"]
        clock = time.strftime("%Y-%m-%d %H:%M:%S")
        if len(mid) + cx + len(clock) + 6 < W:
            scr.text((W - len(mid)) // 2, 0, mid, mcol, hb)
        scr.text(W - len(clock) - 1, 0, clock, th["hi"], hb)

        # layout
        top, bot = 1, H - 1
        body = bot - top
        th_top = max(8, int(body * 0.42))
        gw = max(30, int(W * 0.40))
        lw = max(40, int(W * 0.66))
        rw = W - lw
        crack_h = 7 if body - th_top >= 18 else 5
        term_h = body - th_top - crack_h

        view = self.maps[self.mi]
        scr.box(0, top, gw, th_top, bcol, view.title(t), tcol, bg=pbg)
        view.draw(scr, 1, top + 1, gw - 2, th_top - 2, th, t)

        scr.box(gw, top, W - gw, th_top, bcol, "MEMORY :: 10.13.37.42 /proc/1/mem", tcol, bg=pbg)
        self.hex.draw(scr, gw + 2, top + 1, W - gw - 4, th_top - 2, th, t)

        spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(t * 12) % 10]
        scr.box(0, top + th_top, lw, term_h, bcol, f"TERMINAL :: root@ghost {spin}", tcol, bg=pbg)
        self.typer.draw(scr, 1, top + th_top + 1, lw - 3, term_h - 2, th, t)

        scr.box(0, top + th_top + term_h, lw, crack_h, bcol, "PASSWORD CRACKER :: GPU x8", tcol, bg=pbg)
        self.crack.draw(scr, 2, top + th_top + term_h + 1, lw - 4, crack_h - 2, th, t)

        scr.box(lw, top + th_top, rw, body - th_top, bcol, "SYSTEMS", tcol, bg=pbg)
        self.sys.draw(scr, lw + 2, top + th_top + 1, rw - 4, body - th_top - 2, th, t)

        # footer
        fb = mix(th["bg"], th["pri"], 0.08)
        scr.fill(0, H - 1, W, 1, fb)
        show_hints = self.hints and (self.hint_until is None or t < self.hint_until)
        if show_hints:
            s = " TAB grant  S-TAB alert  F1 trace  F2 matrix  F3 exfil  F4 theme  F5 auto  F6 hints  F7/F8 speed  F9 map  F10 melt  ESC×2 quit"
            scr.text(0, H - 1, s, th["dim"], fb, maxw=W)
        else:
            k = int(t / 2.5)
            msgs = [FOOTER_MSGS[(k + i) % len(FOOTER_MSGS)] for i in range(4)]
            scr.text(1, H - 1, "   ".join(msgs), th["dim"], fb, maxw=W - 2)
            scr.text(1, H - 1, msgs[0], th["txt"], fb, maxw=W - 2)

    def glitch(self):
        scr = self.scr
        W, H = scr.w, scr.h
        for _ in range(R.randint(2, 5)):
            y0 = R.randrange(H)
            hh = R.randint(1, 3)
            off = R.choice([-1, 1]) * R.randint(1, 8)
            for y in range(y0, min(H, y0 + hh)):
                b = y * W
                rc, rf, rb = scr.ch[b:b + W], scr.fg[b:b + W], scr.bg[b:b + W]
                scr.ch[b:b + W] = rc[-off:] + rc[:-off]
                scr.fg[b:b + W] = rf[-off:] + rf[:-off]
                scr.bg[b:b + W] = rb[-off:] + rb[:-off]

    MELT_DUR = 2.4

    def start_melt(self, t):
        cols = [(R.uniform(0.55, 1.0), R.uniform(0, 6.3)) for _ in range(400)]
        self.melt = (t, R.randrange(4), cols)

    def draw_melt(self, t):
        """Drip one corner of the screen downwards, like hot wax, then let it snap back."""
        scr, th = self.scr, self.th
        W, H = scr.w, scr.h - 1          # leave the footer alone
        t0, corner, cols = self.melt
        e = min(1.0, (t - t0) / (self.MELT_DUR * 0.85))
        p = e * e * (3 - 2 * e) * e      # slow start, sags faster as it goes
        rw, rh = int(W * 0.3), int(H * 0.45)
        right, bottom = corner & 1, corner & 2
        for i in range(rw):
            d = 1 - i / rw               # 1 at the screen edge, 0 at the inner edge
            amp, ph = cols[i % len(cols)]
            x = W - 1 - i if right else i
            colh = max(1, int(rh * d ** 0.7))          # rounded corner region
            o = int(rh * 0.7 * d ** 1.4 * amp * p * (0.85 + 0.15 * math.sin(ph + t * 3)))
            if o <= 0:
                continue
            y0 = H - colh if bottom else 0
            col = [(scr.ch[y * scr.w + x], scr.fg[y * scr.w + x], scr.bg[y * scr.w + x])
                   for y in range(y0, y0 + colh)]
            # trail colour: the first visible glyph in the column, faded
            src = next((c for c in col if c[0] != " "), col[0])
            for y in range(y0, min(H, y0 + colh + o)):
                k = y - y0 - o
                if k >= 0:
                    c, f, b = col[k]
                    if y - y0 >= colh:   # sliding past the region's lower edge
                        f = mix(f, th["bg"], min(0.8, (y - y0 - colh) / max(1, o)))
                else:                    # what's left behind: dark, with the odd drip line
                    fade = 0.35 + 0.5 * (1 - (y - y0) / o)
                    c = ("╎" if (y - y0) % 3 else "│") if ph > 4.2 else " "
                    f, b = mix(src[1] or th["dim"], th["bg"], fade), th["bg"]
                scr.put(x, y, c, f, b)

    # ── main loop
    def run(self):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        out = sys.stdout
        signal.signal(signal.SIGWINCH, lambda *_: setattr(self, "resized", True))
        try:
            tty.setraw(fd)
            out.write("\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J")
            out.flush()
            last = time.monotonic()
            while True:
                now = time.monotonic()
                t = now - self.t0
                dt = min(0.1, now - last)
                last = now
                if self.resized:
                    self.resized = False
                    sz = os.get_terminal_size(sys.stdout.fileno())
                    self.scr.resize(sz.columns, sz.lines)
                    os.write(sys.stdout.fileno(), b"\x1b[0m\x1b[2J")
                self.update(dt, t)
                self.draw(t)
                self.scr.render()
                deadline = now + 1 / FPS
                while True:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        break
                    try:
                        r, _, _ = select.select([fd], [], [], left)
                    except InterruptedError:
                        break
                    if r:
                        data = os.read(fd, 4096).decode("utf-8", "ignore")
                        for k in parse_keys(data):
                            self.on_key(k, time.monotonic() - self.t0)
        except (SystemExit, KeyboardInterrupt):
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            out.write("\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l")
            out.flush()


def main():
    if "--version" in sys.argv:
        print(f"hackterm {__version__}")
        return
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        print("Options: --version   print the version and exit\n         --no-boot   skip the boot sequence\n         --theme N   start on theme N (0-4)\n"
              "         --speed X   panel animation speed, 0.25-2 (default 0.6)\n"
              "         --chars N   max characters typed per keypress (default 2)\n"
              "         --map N     start on map N: 0 globe, 1 network, 2 radar, 3 traceroute")
        return
    if not sys.stdin.isatty():
        print("hackterm needs an interactive terminal", file=sys.stderr)
        sys.exit(1)
    app = App(boot="--no-boot" not in sys.argv)
    if "--theme" in sys.argv:
        try:
            app.ti = int(sys.argv[sys.argv.index("--theme") + 1]) % len(app.themes)
        except (IndexError, ValueError):
            pass
    for flag, attr, conv, lo, hi in (("--speed", "speed", float, 0.1, 4.0), ("--chars", "chars", int, 1, 20),
                                     ("--map", "mi", int, 0, len(app.maps) - 1)):
        if flag in sys.argv:
            try:
                setattr(app, attr, max(lo, min(hi, conv(sys.argv[sys.argv.index(flag) + 1]))))
            except (IndexError, ValueError):
                pass
    app.run()


if __name__ == "__main__":
    main()
