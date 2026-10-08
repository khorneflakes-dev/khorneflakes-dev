#!/usr/bin/env python3
"""Genera la imagen animada del perfil de GitHub. Solo librería estándar.

Tres estilos, según [perfil] estilo en profile.toml: "kitty" (terminal, este archivo),
"widgets" (tarjetas, scripts/widgets.py) y "pipboy" (CRT de fósforo, scripts/pipboy.py).

Desde la raíz del repo:
    py scripts/generate.py            # stats reales (usa GITHUB_TOKEN o GH_TOKEN si existe)
    py scripts/generate.py --demo     # datos de ejemplo de profile.toml, sin red
    py scripts/generate.py --static   # sin animación, estado final (para previsualizar)

Escribe assets/perfil-dark.svg y assets/perfil-light.svg; el README los alterna con
<picture> + prefers-color-scheme.

En el estilo kitty, todo el texto va sobre una grilla monoespaciada fija: cada <text> lleva
textLength = caracteres x ancho de celda, así el cursor, las barras y los recortes
del tipeo caen en la misma columna aunque el visitante no tenga la fuente.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
import tomllib
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------- #
# temas: misma estructura en todos para que el render no dependa del elegido
# --------------------------------------------------------------------------- #

THEMES = {
    "catppuccin": {
        "dark": dict(name="Catppuccin Mocha", base="#1e1e2e", mantle="#181825", crust="#11111b",
                     surface0="#313244", surface1="#45475a", overlay0="#6c7086", subtext="#a6adc8",
                     text="#cdd6f4", red="#f38ba8", peach="#fab387", yellow="#f9e2af",
                     green="#a6e3a1", teal="#94e2d5", blue="#89b4fa", mauve="#cba6f7", pink="#f5c2e7"),
        "light": dict(name="Catppuccin Latte", base="#eff1f5", mantle="#e6e9ef", crust="#dce0e8",
                      surface0="#ccd0da", surface1="#bcc0cc", overlay0="#9ca0b0", subtext="#6c6f85",
                      text="#4c4f69", red="#d20f39", peach="#fe640b", yellow="#df8e1d",
                      green="#40a02b", teal="#179299", blue="#1e66f5", mauve="#8839ef", pink="#ea76cb"),
    },
    "tokyonight": {
        "dark": dict(name="Tokyo Night", base="#1a1b26", mantle="#16161e", crust="#13131a",
                     surface0="#292e42", surface1="#3b4261", overlay0="#565f89", subtext="#a9b1d6",
                     text="#c0caf5", red="#f7768e", peach="#ff9e64", yellow="#e0af68",
                     green="#9ece6a", teal="#73daca", blue="#7aa2f7", mauve="#bb9af7", pink="#ff9ec7"),
        "light": dict(name="Tokyo Night Day", base="#e1e2e7", mantle="#d5d6db", crust="#c4c8da",
                      surface0="#c4c8da", surface1="#a8aecb", overlay0="#848cb5", subtext="#6172b0",
                      text="#3760bf", red="#f52a65", peach="#b15c00", yellow="#8c6c3e",
                      green="#587539", teal="#118c74", blue="#2e7de9", mauve="#9854f1", pink="#d20065"),
    },
    "gruvbox": {
        "dark": dict(name="Gruvbox Dark", base="#282828", mantle="#1d2021", crust="#161819",
                     surface0="#3c3836", surface1="#504945", overlay0="#7c6f64", subtext="#bdae93",
                     text="#ebdbb2", red="#fb4934", peach="#fe8019", yellow="#fabd2f",
                     green="#b8bb26", teal="#8ec07c", blue="#83a598", mauve="#d3869b", pink="#d3869b"),
        "light": dict(name="Gruvbox Light", base="#fbf1c7", mantle="#f2e5bc", crust="#ebdbb2",
                      surface0="#ebdbb2", surface1="#d5c4a1", overlay0="#a89984", subtext="#665c54",
                      text="#3c3836", red="#9d0006", peach="#af3a03", yellow="#b57614",
                      green="#79740e", teal="#427b58", blue="#076678", mauve="#8f3f71", pink="#8f3f71"),
    },
    "rosepine": {
        "dark": dict(name="Rosé Pine", base="#191724", mantle="#1f1d2e", crust="#12101a",
                     surface0="#26233a", surface1="#403d52", overlay0="#6e6a86", subtext="#908caa",
                     text="#e0def4", red="#eb6f92", peach="#ea9a97", yellow="#f6c177",
                     green="#9ccfd8", teal="#3e8fb0", blue="#9ccfd8", mauve="#c4a7e7", pink="#ebbcba"),
        "light": dict(name="Rosé Pine Dawn", base="#faf4ed", mantle="#fffaf3", crust="#f2e9e1",
                      surface0="#f2e9e1", surface1="#dfdad9", overlay0="#9893a5", subtext="#797593",
                      text="#575279", red="#b4637a", peach="#d7827e", yellow="#ea9d34",
                      green="#56949f", teal="#286983", blue="#286983", mauve="#907aa9", pink="#d7827e"),
    },
}

# --------------------------------------------------------------------------- #
# métricas de la grilla
# --------------------------------------------------------------------------- #

FS = 13                 # tamaño de fuente
CW = FS * 0.6           # ancho de celda
LH = 19                 # alto de línea
TAB_FS = 12
TAB_CW = TAB_FS * 0.6
PAD = 14                # padding interno de cada split
GAP = 8                 # separación entre splits
MARGIN = 26             # wallpaper visible alrededor de la ventana
WIN_PAD = 10
MIN_W = 960
DIM = 0.62              # inactive_text_alpha de kitty
DT = 0.065              # segundos por tecla
FONT_STACK = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"


def esc(s: str) -> str:
    return escape(s, quote=True)


def lerp(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def txt(x: float, y: float, segs, size: int = FS, anchor: str = "") -> str:
    """Una línea de texto. segs = [(texto, color[, negrita])]."""
    cw = size * 0.6
    segs = [list(s) for s in segs if s[0]]
    full = "".join(s[0] for s in segs)
    if not full.strip(" "):
        return ""
    # Los espacios de los bordes no cuentan para textLength (el navegador los recorta
    # y estira el resto): se sacan y se compensan corriendo x.
    lead, trail = len(full) - len(full.lstrip(" ")), len(full) - len(full.rstrip(" "))
    for idx, cut in ((0, lead), (-1, trail)):
        while cut:
            s = segs[idx]
            body = s[0].lstrip(" ") if idx == 0 else s[0].rstrip(" ")
            take = min(cut, len(s[0]) - len(body)) if body else len(s[0])
            s[0] = s[0][take:] if idx == 0 else s[0][: len(s[0]) - take]
            cut -= take
            if not s[0]:
                segs.pop(idx)
    x += lead * cw if anchor != "end" else -trail * cw
    n = sum(len(s[0]) for s in segs)
    spans = []
    for s in segs:
        bold = ' font-weight="700"' if len(s) > 2 and s[2] else ""
        spans.append(f'<tspan fill="{s[1]}"{bold}>{esc(s[0])}</tspan>')
    extra = f' font-size="{size}"' if size != FS else ""
    if anchor:
        extra += f' text-anchor="{anchor}"'
    return (f'<text x="{x:.1f}" y="{y:.1f}"{extra} textLength="{n * cw:.1f}" '
            f'lengthAdjust="spacing">{"".join(spans)}</text>')


def pixels(x: float, y: float, line: str, color: str) -> str:
    """Arte de bloques (█ ▀ ▄ ▌ ▐) como rectángulos: las fuentes de respaldo dibujan
    esos glifos angostos o con huecos. Cada celda ocupa el alto completo de la línea
    para que las filas se peguen."""
    top, half_h, half_w = y - 14, LH / 2, CW / 2
    shapes = {"█": (0, 0, CW, LH), "▀": (0, 0, CW, half_h), "▄": (0, half_h, CW, half_h),
              "▌": (0, 0, half_w, LH), "▐": (half_w, 0, half_w, LH)}
    out, i = [], 0
    while i < len(line):
        ch = line[i]
        if ch not in shapes:
            if ch != " ":
                out.append(txt(x + i * CW, y, [(ch, color)]))
            i += 1
            continue
        j = i + 1
        while ch in "█▀▄" and j < len(line) and line[j] == ch:  # juntar corridas horizontales
            j += 1
        dx, dy, w, h = shapes[ch]
        out.append(f'<rect x="{x + i * CW + dx:.1f}" y="{top + dy:.1f}" width="{w + (j - i - 1) * CW + 0.3:.1f}" '
                   f'height="{h + 0.3:.1f}" fill="{color}"/>')
        i = j
    return "".join(out)


def cells(x: float, y: float, n: int, color) -> str:
    """Barra segmentada estilo btop: n celdas; color puede ser función del índice."""
    return "".join(f'<rect x="{x + k * CW + 1:.1f}" y="{y - 10:.1f}" width="{CW - 2:.1f}" height="11" rx="1" '
                   f'fill="{color(k) if callable(color) else color}"/>' for k in range(n))


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


# --------------------------------------------------------------------------- #
# stats de GitHub
# --------------------------------------------------------------------------- #

GQL = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def _api(url: str, token: str | None, body: dict | None = None):
    headers = {"User-Agent": "kitty-profile", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _top(weights: dict[str, float], n: int) -> list[tuple[str, float]]:
    total = sum(weights.values()) or 1
    ranked = sorted(weights.items(), key=lambda kv: -kv[1])[:n]
    return [(name, 100 * w / total) for name, w in ranked]


def stats_graphql(user: str, token: str, exclude: set[str], n: int) -> dict:
    d = _api("https://api.github.com/graphql", token, {"query": GQL, "variables": {"login": user}})
    if d.get("errors"):
        raise RuntimeError(d["errors"][0]["message"])
    u = d["data"]["user"]
    if u is None:
        raise RuntimeError(f"no existe el usuario '{user}'")
    repos = u["repositories"]
    sizes: Counter[str] = Counter()
    for node in repos["nodes"]:
        for edge in node["languages"]["edges"]:
            name = edge["node"]["name"]
            if name.lower() not in exclude:
                sizes[name] += edge["size"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    return {
        "repos": repos["totalCount"],
        "stars": sum(node["stargazerCount"] for node in repos["nodes"]),
        "followers": u["followers"]["totalCount"],
        "contributions": cal["totalContributions"],
        "weeks": [sum(day["contributionCount"] for day in w["contributionDays"]) for w in cal["weeks"]],
        "days": [(dt.date.fromisoformat(day["date"]), day["contributionCount"])
                 for w in cal["weeks"] for day in w["contributionDays"]],
        "langs": _top(sizes, n),
    }


def stats_rest(user: str, exclude: set[str], n: int) -> dict:
    """Sin token: la API REST no da contribuciones y los lenguajes se cuentan por repo."""
    u = _api(f"https://api.github.com/users/{user}", None)
    repos, page = [], 1
    while True:
        batch = _api(f"https://api.github.com/users/{user}/repos?per_page=100&page={page}&type=owner", None)
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = Counter(r["language"] for r in own if r["language"] and r["language"].lower() not in exclude)
    return {
        "repos": len(own),
        "stars": sum(r["stargazers_count"] for r in own),
        "followers": u["followers"],
        "contributions": None,
        "weeks": None,
        "days": None,
        "langs": _top(dict(langs), n),
    }


def stats_demo(cfg: dict, today: dt.date) -> dict:
    d = cfg["demo"]
    # Días de ejemplo: cada total semanal repartido con un patrón fijo, terminando hoy.
    pattern = [0, 2, 3, 1, 3, 2, 0]
    days, start = [], today - dt.timedelta(days=7 * len(d["semanas"]) - 1)
    for w, total in enumerate(d["semanas"]):
        for k, weight in enumerate(pattern):
            days.append((start + dt.timedelta(days=7 * w + k), round(total * weight / sum(pattern))))
    return {
        "repos": d["repos"], "stars": d["stars"], "followers": d["followers"],
        "contributions": d["contribuciones"], "weeks": d["semanas"], "days": days,
        "langs": [(name, float(p)) for name, p in d["lenguajes"]],
    }


# --------------------------------------------------------------------------- #
# animación
# --------------------------------------------------------------------------- #


class Svg:
    """Acumula <defs> y resuelve las animaciones (o su estado final con --static)."""

    def __init__(self, anim: bool):
        self.anim = anim
        self.defs: list[str] = []
        self.n = 0

    def uid(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}{self.n}"

    def show(self, t: float, body: str) -> str:
        """body aparece en el segundo t."""
        if not body:
            return ""
        if not self.anim or t <= 0:
            return body
        return (f'<g opacity="0"><set attributeName="opacity" to="1" begin="{t:.2f}s" '
                f'fill="freeze"/>{body}</g>')

    def reveal(self, x: float, y: float, n: int, t0: float, step: float, body: str) -> str:
        """Destapa body de a una celda, de izquierda a derecha (tipeo / barras)."""
        if not self.anim or n == 0:
            return body
        cid = self.uid("r")
        widths = ";".join(f"{i * CW + (2 if i == n else 0):.1f}" for i in range(n + 1))
        self.defs.append(
            f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y - LH:.1f}" width="0" height="{LH + 6}">'
            f'<animate attributeName="width" calcMode="discrete" values="{widths}" '
            f'begin="{t0:.2f}s" dur="{(n + 1) * step:.3f}s" fill="freeze"/></rect></clipPath>')
        return f'<g clip-path="url(#{cid})">{body}</g>'

    def switch(self, attr: str, changes: list[tuple[float, str]]) -> tuple[str, str]:
        """Atributo con valor inicial + cambios en el tiempo. Devuelve (valor inicial, <set>s)."""
        if not self.anim:
            return changes[-1][1], ""
        sets = "".join(f'<set attributeName="{attr}" to="{v}" begin="{t:.2f}s" fill="freeze"/>'
                       for t, v in changes[1:])
        return changes[0][1], sets


class Cursor:
    """Cursor de bloque de un split: posición y estilo a lo largo del tiempo.
    solid = ventana con foco, hollow = sin foco (como kitty), none = oculto,
    blink = parpadeo indefinido desde ese momento."""

    def __init__(self):
        self.ev: list[tuple[float, float, float, str]] = []

    def at(self, t: float, x: float, y: float, style: str):
        self.ev.append((t, x, y, style))

    def render(self, sv: Svg, color: str, t_end: float) -> str:
        top = lambda y: y - 13.5
        solid = lambda x, y, extra="": (f'<rect x="{x:.1f}" y="{top(y):.1f}" width="{CW:.1f}" height="17" '
                                         f'fill="{color}"{extra}/>')
        hollow = lambda x, y, extra="": (f'<rect x="{x + 0.6:.1f}" y="{top(y) + 0.6:.1f}" width="{CW - 1.2:.1f}" '
                                          f'height="15.8" fill="none" stroke="{color}" stroke-width="1.2"{extra}/>')
        if not sv.anim:
            _, x, y, st = self.ev[-1]
            return hollow(x, y) if st == "hollow" else solid(x, y) if st in ("solid", "blink") else ""

        # una entrada por instante (gana la última), arrancando en 0 y cerrando en t_end
        by_t: dict[float, tuple[float, float, str]] = {}
        for t, x, y, st in sorted(self.ev, key=lambda e: e[0]):
            by_t[round(t / t_end, 4)] = (x, y, st)
        by_t.setdefault(0.0, (self.ev[0][1], self.ev[0][2], "none"))
        keys = sorted(k for k in by_t if k <= 1)
        if keys[-1] < 1:
            by_t[1.0] = by_t[keys[-1]]
            keys.append(1.0)
        states = [by_t[k] for k in keys]
        kt = ";".join(f"{k:g}" for k in keys)

        def anim(attr, vals):
            return (f'<animate attributeName="{attr}" calcMode="discrete" dur="{t_end:.2f}s" fill="freeze" '
                    f'keyTimes="{kt}" values="{";".join(vals)}"/>')

        xs = [f"{x:.1f}" for x, _, _ in states]
        ys = [f"{top(y):.1f}" for _, y, _ in states]
        out = [
            f'<rect x="{xs[0]}" y="{ys[0]}" width="{CW:.1f}" height="17" fill="{color}" opacity="0">'
            + anim("x", xs) + anim("y", ys)
            + anim("opacity", ["1" if st == "solid" else "0" for *_, st in states]) + "</rect>",
            f'<rect x="{float(xs[0]) + 0.6:.1f}" y="{float(ys[0]) + 0.6:.1f}" width="{CW - 1.2:.1f}" height="15.8" '
            f'fill="none" stroke="{color}" stroke-width="1.2" opacity="0">'
            + anim("x", [f"{float(v) + 0.6:.1f}" for v in xs])
            + anim("y", [f"{float(v) + 0.6:.1f}" for v in ys])
            + anim("opacity", ["1" if st == "hollow" else "0" for *_, st in states]) + "</rect>",
        ]
        blinks = [e for e in self.ev if e[3] == "blink"]
        if blinks:
            t, x, y, _ = blinks[-1]
            out.append(solid(x, y, ' opacity="0"').replace(
                "/>", f'><animate attributeName="opacity" calcMode="discrete" values="1;0" '
                      f'begin="{t:.2f}s" dur="1.1s" repeatCount="indefinite"/></rect>'))
        return "".join(out)


# --------------------------------------------------------------------------- #
# piezas de la terminal
# --------------------------------------------------------------------------- #


@dataclass
class Panel:
    x: float
    y: float
    w: float
    h: float

    def cx(self, col: float) -> float:
        return self.x + PAD + col * CW

    def ry(self, row: int) -> float:
        return self.y + PAD + FS + row * LH - 2


def rows_height(rows: int) -> float:
    return 2 * PAD + FS + (rows - 1) * LH + 4


def prompt(p: Panel, row: int, segs, fg: str) -> tuple[str, int]:
    """Prompt powerline estilo starship. Devuelve (svg, columna donde empieza el comando)."""
    y = p.ry(row)
    top, h = y - 13.5, 17
    out, col = [], 0
    for i, (label, bg) in enumerate(segs):
        x0, w = p.cx(col), len(label) * CW
        if i == 0:
            out.append(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h}" rx="4" fill="{bg}"/>')
            out.append(f'<rect x="{x0 + 4:.1f}" y="{top:.1f}" width="{w - 4:.1f}" height="{h}" fill="{bg}"/>')
        else:
            out.append(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h}" fill="{bg}"/>')
        out.append(txt(x0, y, [(label, fg, True)]))
        col += len(label)
        xa = p.cx(col)
        if i + 1 < len(segs):
            out.append(f'<rect x="{xa:.1f}" y="{top:.1f}" width="{CW:.1f}" height="{h}" fill="{segs[i + 1][1]}"/>')
        out.append(f'<polygon points="{xa:.1f},{top:.1f} {xa + CW:.1f},{top + h / 2:.1f} {xa:.1f},{top + h:.1f}" '
                   f'fill="{bg}"/>')
        col += 1
    return "".join(out), col + 1


def toml_lines(stack: dict, width: int, c: dict) -> list[list]:
    """El stack como TOML resaltado, recortando listas que no entran en width."""
    out: list[list] = []
    for i, (section, kv) in enumerate(stack.items()):
        if i:
            out.append([])
        out.append([("[", c["subtext"]), (section, c["mauve"], True), ("]", c["subtext"])])
        kw = max(len(k) for k in kv)
        for key, val in kv.items():
            segs = [(key.ljust(kw), c["blue"]), (" = ", c["subtext"])]
            used = kw + 3
            if isinstance(val, list):
                segs.append(("[", c["subtext"]))
                used += 1
                for j, item in enumerate(val):
                    sep, piece = (", " if j else ""), f'"{item}"'
                    if used + len(sep) + len(piece) + 1 > width:
                        segs.append((sep + "…", c["overlay0"]))
                        break
                    if sep:
                        segs.append((sep, c["subtext"]))
                    segs.append((piece, c["green"]))
                    used += len(sep) + len(piece)
                segs.append(("]", c["subtext"]))
            else:
                piece = f'"{val}"'
                if used + len(piece) > width:
                    piece = piece[: max(width - used - 2, 1)] + '…"'
                segs.append((piece, c["green"]))
            out.append(segs)
    return out


def sparkline(x: float, y: float, weeks: list[int], n: int, c: dict) -> str:
    """Contribuciones por semana: una barra por celda, apoyadas en la base de la línea."""
    weeks = weeks[-n:]
    peak = max(weeks) or 1
    base, tall = y + 3, LH - 2
    out = []
    for k, w in enumerate(weeks):
        h = 2 if w == 0 else 3 + (tall - 3) * w / peak
        color = c["surface1"] if w == 0 else lerp(c["teal"], c["green"], w / peak)
        out.append(f'<rect x="{x + k * CW + 1:.1f}" y="{base - h:.1f}" width="{CW - 2:.1f}" '
                   f'height="{h:.1f}" rx="1" fill="{color}"/>')
    return "".join(out)


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #


def render(cfg: dict, stats: dict, c: dict, dark: bool, anim: bool, font_css: str, today: dt.date) -> str:
    sv = Svg(anim)
    kitty = cfg["kitty"]
    user, host = cfg["perfil"].get("nombre") or cfg["perfil"]["usuario"], cfg["perfil"].get("host", "github")
    accents = [c["mauve"], c["blue"], c["teal"], c["green"], c["peach"], c["pink"]]

    variables = SafeDict(
        uptime=f'{today.year - int(cfg["perfil"].get("programando_desde", today.year))} years coding',
        theme=c["name"],
        langs=", ".join(name for name, _ in stats["langs"][:3]),
        repos=stats["repos"], stars=stats["stars"], followers=stats["followers"],
    )
    info = [(k, str(v).format_map(variables)) for k, v in cfg["fastfetch"]["info"]]
    logo = cfg["fastfetch"]["logo"].strip("\n").split("\n")
    logo_w = max(len(line) for line in logo)
    head = f"{user}@{host}"
    info_w = max([len(head), 24] + [len(k) + 2 + len(v) for k, v in info])

    left_prompt = [(" ~/profile ", c["blue"]), (" main ", c["mauve"])]
    right_prompt = [(" ~ ", c["blue"])]
    final_cmd = kitty.get("comando_final", "")
    lp_cols = sum(len(s[0]) + 1 for s in left_prompt) + 1
    rp_cols = sum(len(s[0]) + 1 for s in right_prompt) + 1

    # ---- anchos -------------------------------------------------------------
    left_cols = max(logo_w + 3 + info_w, lp_cols + len(final_cmd) + 1)
    right_cols = 48
    left_w = left_cols * CW + 2 * PAD
    right_w = right_cols * CW + 2 * PAD
    W = 2 * MARGIN + 2 * WIN_PAD + left_w + GAP + right_w
    if W < MIN_W:
        right_w += MIN_W - W
        right_cols = int((right_w - 2 * PAD) / CW)
        W = MIN_W

    # ---- contenido de cada split -------------------------------------------
    ff_rows = max(len(logo), 2 + len(info) + 1 + 2)
    left_rows = 1 + 1 + ff_rows + 1 + 1

    gut = 4
    rule = lambda ch: ("─" * gut + ch + "─" * (right_cols - gut - 1), c["overlay0"])
    bat = [[rule("┬")],
           [(" " * gut + "│ ", c["overlay0"]), ("File: ", c["text"]), ("stack.toml", c["text"], True)],
           [rule("┼")]]
    for i, segs in enumerate(toml_lines(cfg["stack"], right_cols - gut - 2, c), 1):
        bat.append([(f"{i:>3} ", c["overlay0"]), ("│ ", c["overlay0"])] + segs)
    bat.append([rule("┴")])
    rt_rows = 1 + len(bat) + 1 + 1

    stat_rows: list[list] = [[
        ("repos ", c["subtext"]), (str(stats["repos"]), c["peach"], True),
        ("  ★ ", c["yellow"]), (str(stats["stars"]), c["peach"], True),
        ("  followers ", c["subtext"]), (str(stats["followers"]), c["peach"], True),
    ]]
    if stats.get("contributions") is not None:
        stat_rows.append([(f'{stats["contributions"]:,}', c["green"], True),
                          (" contributions in the last year", c["subtext"])])
        stat_rows.append("sparkline")
    langs = stats["langs"]
    name_w = max((len(n) for n, _ in langs), default=0)
    bar_w = right_cols - name_w - 2 - 5
    first_bar = len(stat_rows) + 1
    rb_rows = 1 + len(stat_rows) + (1 + len(langs) if langs else 0) + 1 + 1

    # ---- alturas y geometría -------------------------------------------------
    left_h, rt_h, rb_h = rows_height(left_rows), rows_height(rt_rows), rows_height(rb_rows)
    area = max(left_h, rt_h + GAP + rb_h)
    rb_h = area - rt_h - GAP
    win_x = win_y = MARGIN
    tab_y = win_y + 8
    area_y = tab_y + 22 + 8
    win_w = W - 2 * MARGIN
    win_h = area_y - win_y + area + WIN_PAD
    H = win_h + 2 * MARGIN

    L = Panel(win_x + WIN_PAD, area_y, left_w, area)
    RT = Panel(L.x + left_w + GAP, area_y, right_w, rt_h)
    RB = Panel(RT.x, area_y + rt_h + GAP, right_w, rb_h)
    body = {"L": [], "RT": [], "RB": []}
    cur = {"L": Cursor(), "RT": Cursor(), "RB": Cursor()}
    focus = [(0.0, "L")]

    def type_cmd(name, p, row, col, cmd, t0):
        x, y = p.cx(col), p.ry(row)
        body[name].append(sv.reveal(x, y, len(cmd), t0, DT, txt(x, y, [(cmd, c["text"])])))
        for i in range(len(cmd) + 1):
            cur[name].at(t0 + i * DT, p.cx(col + i), y, "solid")
        return t0 + (len(cmd) + 1) * DT

    def move_focus(t, frm, to, frm_pos, to_pos):
        focus.append((t, to))
        cur[frm].at(t, *frm_pos, "hollow")
        cur[to].at(t, *to_pos, "solid")

    # prompts iniciales: las tres ventanas ya están abiertas
    for name, p, segs in (("L", L, left_prompt), ("RT", RT, right_prompt), ("RB", RB, right_prompt)):
        svg, col = prompt(p, 0, segs, c["crust"])
        body[name].append(svg)
        cur[name].at(0, p.cx(col), p.ry(0), "solid" if name == "L" else "hollow")

    # ---- izquierda: fastfetch ----------------------------------------------
    t = type_cmd("L", L, 0, lp_cols, "fastfetch", 0.6)
    cur["L"].at(t, L.cx(lp_cols + 9), L.ry(0), "none")
    t += 0.3
    info_rows: list = [[(user, c["mauve"], True), ("@", c["text"]), (host, c["mauve"], True)],
                       [("-" * len(head), c["subtext"])]]
    info_rows += [[(k, c["blue"], True), (": ", c["text"]), (v, c["text"])] for k, v in info]
    info_rows += [[], "colors0", "colors1"]
    ix = logo_w + 3
    normal = [c["surface1"], c["red"], c["green"], c["yellow"], c["blue"], c["mauve"], c["teal"], c["subtext"]]
    bright = [c["overlay0"], c["red"], c["green"], c["yellow"], c["blue"], c["pink"], c["teal"], c["text"]]
    for r in range(ff_rows):
        row, parts = 2 + r, []
        if r < len(logo):
            color = lerp(c["mauve"], c["blue"], r / max(len(logo) - 1, 1))
            parts.append(pixels(L.cx(0), L.ry(row), logo[r], color))
        if r < len(info_rows):
            item = info_rows[r]
            if isinstance(item, str):
                palette = normal if item == "colors0" else bright
                for k, col in enumerate(palette):
                    parts.append(f'<rect x="{L.cx(ix + 3 * k):.1f}" y="{L.ry(row) - 13:.1f}" '
                                 f'width="{3 * CW:.1f}" height="{LH - 3}" fill="{col}"/>')
            else:
                parts.append(txt(L.cx(ix), L.ry(row), item))
        body["L"].append(sv.show(t + r * 0.035, "".join(parts)))
    t += ff_rows * 0.035 + 0.2
    final_row = 2 + ff_rows + 1
    svg, col = prompt(L, final_row, left_prompt, c["crust"])
    body["L"].append(sv.show(t, svg))
    left_final = (L.cx(col), L.ry(final_row))
    cur["L"].at(t, *left_final, "solid")

    # ---- arriba a la derecha: bat ------------------------------------------
    t += 0.55
    move_focus(t, "L", "RT", left_final, (RT.cx(rp_cols), RT.ry(0)))
    t = type_cmd("RT", RT, 0, rp_cols, "bat stack.toml", t + 0.3)
    cur["RT"].at(t, RT.cx(rp_cols + 14), RT.ry(0), "none")
    t += 0.3
    for r, segs in enumerate(bat):
        body["RT"].append(sv.show(t + r * 0.03, txt(RT.cx(0), RT.ry(1 + r), segs)))
    t += len(bat) * 0.03 + 0.2
    rt_final_row = 1 + len(bat) + 1
    svg, col = prompt(RT, rt_final_row, right_prompt, c["crust"])
    body["RT"].append(sv.show(t, svg))
    rt_final = (RT.cx(col), RT.ry(rt_final_row))
    cur["RT"].at(t, *rt_final, "solid")

    # ---- abajo a la derecha: gh stats --------------------------------------
    t += 0.55
    move_focus(t, "RT", "RB", rt_final, (RB.cx(rp_cols), RB.ry(0)))
    t = type_cmd("RB", RB, 0, rp_cols, "gh stats", t + 0.3)
    cur["RB"].at(t, RB.cx(rp_cols + 8), RB.ry(0), "none")
    t += 0.4
    for r, segs in enumerate(stat_rows):
        x, y = RB.cx(0), RB.ry(1 + r)
        line = sparkline(x, y, stats["weeks"], right_cols, c) if segs == "sparkline" else txt(x, y, segs)
        body["RB"].append(sv.show(t + r * 0.05, line))
    t += len(stat_rows) * 0.05
    for i, (name, pct) in enumerate(langs):
        row = 1 + first_bar + i
        y, color = RB.ry(row), accents[i % len(accents)]
        filled = max(1, round(bar_w * pct / 100)) if pct > 0 else 0
        bx = RB.cx(name_w + 2)
        line = (txt(RB.cx(0), y, [(name, c["text"])])
                + cells(bx, y, bar_w, c["surface0"])
                + txt(RB.cx(name_w + 2 + bar_w), y, [(f"{pct:>4.0f}%", c["subtext"])]))
        shade = lambda k, color=color: lerp(color, c["text"], 0.35 * k / max(bar_w - 1, 1))
        fill = sv.reveal(bx, y, filled, t + 0.15 + i * 0.12, 0.02, cells(bx, y, filled, shade))
        body["RB"].append(sv.show(t + i * 0.05, line + fill))
    t += len(langs) * 0.12 + bar_w * 0.02 + 0.3
    rb_final_row = rb_rows - 1
    svg, col = prompt(RB, rb_final_row, right_prompt, c["crust"])
    body["RB"].append(sv.show(t, svg))
    rb_final = (RB.cx(col), RB.ry(rb_final_row))
    cur["RB"].at(t, *rb_final, "solid")

    # ---- vuelta a la izquierda: comando final con cursor parpadeando --------
    t += 0.6
    move_focus(t, "RB", "L", rb_final, left_final)
    if final_cmd:
        lcol = round((left_final[0] - L.x - PAD) / CW)
        t = type_cmd("L", L, final_row, lcol, final_cmd, t + 0.4)
        left_final = (L.cx(lcol + len(final_cmd)), left_final[1])
    t_end = t + 0.1
    cur["L"].at(t_end, *left_final, "blink")

    # ---- ensamblado ---------------------------------------------------------
    out = []
    out.append(
        f'<linearGradient id="wall" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{c["crust"]}"/>'
        f'<stop offset="1" stop-color="{lerp(c["crust"], c["mauve"], 0.22)}"/></linearGradient>'
        '<filter id="blur" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="55"/></filter>'
        '<filter id="shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="10" '
        f'stdDeviation="14" flood-color="#000" flood-opacity="{0.4 if dark else 0.18}"/></filter>'
        f'<clipPath id="canvas"><rect width="{W:.0f}" height="{H:.0f}" rx="16"/></clipPath>')
    defs_static = "".join(out)

    blob_op = 0.5 if dark else 0.38
    scene = [
        '<g clip-path="url(#canvas)">',
        f'<rect width="{W:.0f}" height="{H:.0f}" fill="url(#wall)"/>',
        f'<g filter="url(#blur)" opacity="{blob_op}">',
        f'<circle cx="{W * 0.12:.0f}" cy="{H * 0.18:.0f}" r="190" fill="{c["mauve"]}"/>',
        f'<circle cx="{W * 0.88:.0f}" cy="{H * 0.86:.0f}" r="220" fill="{c["blue"]}"/>',
        f'<circle cx="{W * 0.62:.0f}" cy="{H * 0.05:.0f}" r="140" fill="{c["pink"]}"/>',
        f'<circle cx="{W * 0.3:.0f}" cy="{H * 1.0:.0f}" r="150" fill="{c["teal"]}"/>',
        '</g>',
        f'<rect x="{win_x}" y="{win_y}" width="{win_w:.1f}" height="{win_h:.1f}" rx="12" fill="{c["base"]}" '
        f'fill-opacity="{0.86 if dark else 0.82}" stroke="{c["surface1"]}" stroke-opacity=".6" filter="url(#shadow)"/>',
    ]

    # barra de pestañas (tab_bar_style powerline, slanted)
    x = win_x + 12
    for i, name in enumerate(kitty.get("pestanas", ["zsh"])):
        label = f" {i + 1} {name} "
        w = len(label) * TAB_CW + 6
        bg, fg = (c["mauve"], c["crust"]) if i == 0 else (c["surface0"], c["subtext"])
        scene.append(f'<polygon points="{x:.1f},{tab_y + 22} {x + 7:.1f},{tab_y} {x + w + 7:.1f},{tab_y} '
                     f'{x + w:.1f},{tab_y + 22}" fill="{bg}"/>')
        scene.append(txt(x + 6, tab_y + 15.5, [(label, fg, i == 0)], size=TAB_FS))
        x += w + 10
    status = f"[splits] · {c['name']} · {today.isoformat()}"
    scene.append(txt(win_x + win_w - 14, tab_y + 15.5, [(status, c["overlay0"])], size=TAB_FS, anchor="end"))

    # splits
    for name, p in (("L", L), ("RT", RT), ("RB", RB)):
        changes = [(tt, c["mauve"] if f == name else c["surface1"]) for tt, f in focus]
        stroke0, stroke_sets = sv.switch("stroke", changes)
        scene.append(f'<rect x="{p.x:.1f}" y="{p.y:.1f}" width="{p.w:.1f}" height="{p.h:.1f}" rx="8" '
                     f'fill="{c["mantle"]}" fill-opacity=".35" stroke="{stroke0}" stroke-width="1.5">'
                     f'{stroke_sets}</rect>')
        dim0, dim_sets = sv.switch("opacity", [(tt, "1" if f == name else str(DIM)) for tt, f in focus])
        scene.append(f'<g opacity="{dim0}">{dim_sets}{"".join(body[name])}'
                     f'{cur[name].render(sv, c["text"], t_end)}</g>')
    scene.append("</g>")

    title = f"{head} — kitty terminal"
    desc = f"kitty terminal with the {c['name']} theme: fastfetch, stack and GitHub stats."
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
            f'viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-labelledby="title desc" '
            f'font-family="{esc(FONT_STACK if not font_css else "ProfileMono, " + FONT_STACK)}" '
            f'font-size="{FS}" xml:space="preserve">'
            f'<title id="title">{esc(title)}</title><desc id="desc">{esc(desc)}</desc>'
            f'{font_css}<defs>{defs_static}{"".join(sv.defs)}</defs>{"".join(scene)}</svg>\n')


def font_css() -> str:
    """Incrusta las fuentes de assets/fonts/ (el SVG va como <img>, no puede pedir nada afuera)."""
    folder = ROOT / "assets" / "fonts"
    faces = []
    for path in sorted(folder.glob("*")) if folder.is_dir() else []:
        fmt = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}.get(path.suffix.lower())
        if not fmt:
            continue
        weight = 700 if "bold" in path.stem.lower() else 400
        b64 = base64.b64encode(path.read_bytes()).decode()
        faces.append(f'@font-face{{font-family:"ProfileMono";font-weight:{weight};'
                     f'src:url(data:font/{fmt};base64,{b64}) format("{fmt}");}}')
    return f"<style>{''.join(faces)}</style>" if faces else ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="usar los datos de [demo] en vez de la API")
    ap.add_argument("--static", action="store_true", help="sin animación: dibuja el estado final")
    ap.add_argument("--out", default="assets", help="carpeta de salida (default: assets)")
    args = ap.parse_args()

    cfg = tomllib.loads((ROOT / "profile.toml").read_text(encoding="utf-8"))
    user = cfg["perfil"]["usuario"]
    st = cfg.get("stats", {})
    exclude = {x.lower() for x in st.get("excluir_lenguajes", [])}
    top_n = int(st.get("top_lenguajes", 4))

    today = dt.datetime.now(dt.timezone.utc).date()
    if args.demo or user in ("", "TU_USUARIO"):
        if not args.demo:
            print("profile.toml no tiene usuario: uso los datos de [demo]", file=sys.stderr)
        stats = stats_demo(cfg, today)
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        try:
            stats = stats_graphql(user, token, exclude, top_n) if token else stats_rest(user, exclude, top_n)
        except (urllib.error.URLError, RuntimeError, KeyError) as e:
            # Sin fallback a [demo]: en el Action eso publicaría datos inventados.
            sys.exit(f"no pude leer las stats de '{user}': {e}")
        if not token:
            print("sin GITHUB_TOKEN: sin contribuciones y lenguajes contados por repo", file=sys.stderr)

    estilo = cfg["perfil"].get("estilo", "kitty")
    if estilo == "widgets":
        import widgets
        draw = lambda mode: widgets.render(cfg, stats, mode, not args.static, today)
    elif estilo == "pipboy":
        import pipboy
        draw = lambda mode: pipboy.render(cfg, stats, mode, not args.static, today)
    elif estilo == "kitty":
        theme = THEMES.get(cfg["kitty"].get("tema", "catppuccin"))
        if theme is None:
            sys.exit(f"tema desconocido; opciones: {', '.join(THEMES)}")
        css = font_css()
        draw = lambda mode: render(cfg, stats, theme[mode], mode == "dark", not args.static, css, today)
    else:
        sys.exit(f"estilo desconocido '{estilo}'; opciones: kitty, widgets, pipboy")

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    for mode in ("dark", "light"):
        svg = draw(mode)
        path = out_dir / f"perfil-{mode}.svg"
        path.write_text(svg, encoding="utf-8")
        print(f"{path.relative_to(ROOT)}  ({len(svg) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
