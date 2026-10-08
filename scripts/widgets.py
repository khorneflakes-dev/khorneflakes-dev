"""Estilo "widgets": tarjetas monocromáticas tipo pantalla de inicio, en un solo SVG.

Lo llama scripts/generate.py cuando profile.toml tiene [perfil] estilo = "widgets".
Los números grandes son de 7 segmentos dibujados con polígonos, así que no dependen
de ninguna fuente; el resto del texto usa las fuentes del sistema del visitante.
"""

from __future__ import annotations

import calendar
import datetime as dt
import math
from html import escape

W, H = 960, 600

PALETTES = {
    "light": dict(bg="#e3e3df", card="#f5f5f2", ink="#283130", on_ink="#f5f5f2", shadow="#283130",
                  soft="#c4c7c1", muted="#69706e", accent="#3b4f86"),
    "dark": dict(bg="#151918", card="#252b2a", ink="#e8e8e3", on_ink="#1c2120", shadow="#070909",
                 soft="#3d4544", muted="#9aa19f", accent="#a3b6ee"),
}

SANS = "ui-rounded, 'SF Pro Rounded', Nunito, 'Varela Round', 'Segoe UI', system-ui, sans-serif"
HAND = "'Segoe Print', 'Bradley Hand', 'Comic Neue', 'Comic Sans MS', cursive"
DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

SEGMENTS = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg",
            "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g"}


def esc(s: str) -> str:
    return escape(str(s), quote=True)


def pts(points) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def text(x, y, s, size, color, *, weight=400, anchor="start", font=SANS, max_w=None, spacing=0):
    """Texto suelto. max_w comprime si la estimación de ancho se pasa (fuentes ajenas)."""
    fit = ""
    if max_w and len(s) * size * 0.6 > max_w:
        fit = f' textLength="{max_w:.0f}" lengthAdjust="spacingAndGlyphs"'
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{esc(font)}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}"{ls}{fit}>{esc(s)}</text>')


class Anim:
    def __init__(self, on: bool):
        self.on = on
        self.n = 0
        self.defs: list[str] = []

    def uid(self, p: str) -> str:
        self.n += 1
        return f"{p}{self.n}"

    def pop(self, t: float, body: str) -> str:
        """Entrada de tarjeta: aparece subiendo unos píxeles."""
        if not self.on:
            return f"<g>{body}</g>"
        return (f'<g opacity="0"><animate attributeName="opacity" values="0;1" begin="{t:.2f}s" dur=".45s" '
                f'fill="freeze"/><animateTransform attributeName="transform" type="translate" values="0 14;0 0" '
                f'begin="{t:.2f}s" dur=".55s" calcMode="spline" keyTimes="0;1" keySplines=".2 .9 .3 1" '
                f'fill="freeze"/>{body}</g>')

    def show(self, t: float, body: str) -> str:
        if not self.on:
            return body
        return f'<g opacity="0"><set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/>{body}</g>'

    def wipe(self, x, y, w, h, t, dur, body) -> str:
        """Destapa body de izquierda a derecha (tipeo a mano, barras que crecen)."""
        if not self.on:
            return body
        cid = self.uid("w")
        self.defs.append(f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y:.1f}" width="0" height="{h:.1f}">'
                         f'<animate attributeName="width" values="0;{w:.1f}" begin="{t:.2f}s" dur="{dur:.2f}s" '
                         f'calcMode="spline" keyTimes="0;1" keySplines=".4 0 .4 1" fill="freeze"/></rect></clipPath>')
        return f'<g clip-path="url(#{cid})">{body}</g>'


# --------------------------------------------------------------------------- #
# piezas
# --------------------------------------------------------------------------- #


def card(x, y, w, h, p, *, fill=None, r=22) -> str:
    """Tarjeta con borde grueso y sombra sólida desplazada, como un widget de juguete."""
    return (f'<rect x="{x + 3}" y="{y + 5}" width="{w}" height="{h}" rx="{r}" fill="{p["shadow"]}"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or p["card"]}" '
            f'stroke="{p["ink"]}" stroke-width="2.5"/>')


def seven(x, y, w, h, ch, on, ghost=None, ghost_op=0.12) -> str:
    """Un dígito de 7 segmentos con los segmentos apagados como fantasma, inclinado como un LCD."""
    t = w * 0.2
    g = t * 0.2
    hx0, hx1 = x + t / 2, x + w - t / 2
    vy0, vm, vy1 = y + t / 2, y + h / 2, y + h - t / 2

    def hseg(cy):
        a, b = hx0 + g, hx1 - g
        return [(a, cy), (a + t / 2, cy - t / 2), (b - t / 2, cy - t / 2), (b, cy), (b - t / 2, cy + t / 2),
                (a + t / 2, cy + t / 2)]

    def vseg(cx, y0, y1):
        a, b = y0 + g, y1 - g
        return [(cx, a), (cx + t / 2, a + t / 2), (cx + t / 2, b - t / 2), (cx, b), (cx - t / 2, b - t / 2),
                (cx - t / 2, a + t / 2)]

    shapes = {"a": hseg(vy0), "g": hseg(vm), "d": hseg(vy1), "f": vseg(hx0, vy0, vm),
              "b": vseg(hx1, vy0, vm), "e": vseg(hx0, vm, vy1), "c": vseg(hx1, vm, vy1)}
    lit = SEGMENTS.get(ch, "")
    out = []
    for name, poly in shapes.items():
        if name in lit:
            out.append(f'<polygon points="{pts(poly)}" fill="{on}"/>')
        elif ghost:
            out.append(f'<polygon points="{pts(poly)}" fill="{ghost}" opacity="{ghost_op}"/>')
    cx, cy = x + w / 2, y + h / 2
    return f'<g transform="translate({cx:.1f} {cy:.1f}) skewX(-7) translate({-cx:.1f} {-cy:.1f})">{"".join(out)}</g>'


def boat(cx, base, color, fill) -> str:
    return (f'<path d="M{cx - 24} {base} L{cx + 24} {base} L{cx + 16} {base + 10} L{cx - 16} {base + 10} Z" '
            f'fill="{fill}" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
            f'<path d="M{cx} {base - 34} L{cx} {base}" stroke="{color}" stroke-width="2"/>'
            f'<path d="M{cx - 2} {base - 31} L{cx - 2} {base - 4} L{cx - 19} {base - 4} Z" fill="{fill}" '
            f'stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
            f'<path d="M{cx + 2} {base - 27} L{cx + 2} {base - 4} L{cx + 15} {base - 4} Z" fill="{fill}" '
            f'stroke="{color}" stroke-width="2" stroke-linejoin="round"/>')


def waves(x0, x1, y, color, rows=3) -> str:
    out = []
    for r in range(rows):
        yy, d = y + r * 12, ""
        x = x0 + (r % 2) * 8
        d = f"M{x} {yy}"
        while x < x1 - 16:
            d += " q 8 -5 16 0"
            x += 16
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" '
                   f'opacity="{1 - r * 0.25:.2f}"/>')
    return "".join(out)


def pixel_art(lines: list[str], x, y, px, color) -> str:
    """Arte de bloques (█ ▀ ▄) a píxeles cuadrados: cada carácter son 1 x 2 píxeles."""
    out = []
    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            top = ch in "█▀"
            bottom = ch in "█▄"
            if top:
                out.append(f'<rect x="{x + c * px:.1f}" y="{y + 2 * r * px:.1f}" width="{px + .3:.1f}" '
                           f'height="{px + .3:.1f}" fill="{color}"/>')
            if bottom:
                out.append(f'<rect x="{x + c * px:.1f}" y="{y + (2 * r + 1) * px:.1f}" width="{px + .3:.1f}" '
                           f'height="{px + .3:.1f}" fill="{color}"/>')
    return "".join(out)


LEAF = "M0 -11 C7 -6 7 6 0 11 C-7 6 -7 -6 0 -11 Z"


def leaves(anim: Anim, p, area) -> str:
    """Hojas cayendo en loop. Con begin negativo cada una arranca a mitad de camino."""
    x0, y0, x1, y1 = area
    specs = [(0.10, 9.0, -1.0), (0.32, 11.0, -6.5), (0.55, 8.5, -3.2), (0.78, 10.0, -8.0),
             (0.92, 12.0, -4.6), (0.22, 10.5, -9.4), (0.66, 9.5, -0.4)]
    out = []
    for i, (fx, dur, begin) in enumerate(specs):
        sx = x0 + (x1 - x0) * fx
        fill = p["ink"] if i % 2 else p["soft"]
        body = (f'<path d="{LEAF}" fill="{fill}" stroke="{p["ink"]}" stroke-width="1.4"/>'
                f'<path d="M0 -9 L0 9" stroke="{p["card"] if i % 2 else p["ink"]}" stroke-width="1"/>')
        if not anim.on:
            yy = y0 + (y1 - y0) * ((i * 0.37) % 1)
            out.append(f'<g transform="translate({sx:.0f} {yy:.0f}) rotate({(i * 47) % 360})">{body}</g>')
            continue
        path = (f"M{sx:.0f} {y0} C{sx - 60:.0f} {y0 + (y1 - y0) * .3:.0f} {sx + 50:.0f} "
                f"{y0 + (y1 - y0) * .6:.0f} {sx - 30:.0f} {y1}")
        out.append(
            f'<g opacity="0"><animateMotion path="{path}" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.12;.85;1" dur="{dur}s" '
            f'begin="{begin}s" repeatCount="indefinite"/>'
            f'<g><animateTransform attributeName="transform" type="rotate" values="-40;35;-40" '
            f'dur="{dur / 3:.2f}s" begin="{begin}s" repeatCount="indefinite"/>{body}</g></g>')
    return "".join(out)


# --------------------------------------------------------------------------- #
# datos derivados
# --------------------------------------------------------------------------- #


def derive(stats: dict, today: dt.date) -> dict:
    days = stats.get("days")
    if not days:
        return dict(last7=None, streak=None, active_pct=None, week_active=None)
    days = sorted(d for d in days if d[0] <= today)
    last7 = days[-7:]
    # racha: días seguidos con contribuciones; si hoy todavía no hubo, se cuenta hasta ayer
    seq = days[:-1] if days and days[-1][1] == 0 else days
    streak = 0
    for _, n in reversed(seq):
        if n == 0:
            break
        streak += 1
    this_year = [n for d, n in days if d.year == today.year]
    active_pct = round(100 * sum(1 for n in this_year if n) / max(len(this_year), 1))
    return dict(last7=last7, streak=streak, active_pct=active_pct,
                week_active=sum(1 for _, n in last7 if n))


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #


def render(cfg: dict, stats: dict, mode: str, animate: bool, today: dt.date) -> str:
    p = PALETTES[mode]
    a = Anim(animate)
    wcfg = cfg.get("widgets", {})
    d = derive(stats, today)
    parts: list[str] = []

    # ---- calendario --------------------------------------------------------
    x, y, w, h = 28, 28, 360, 168
    c = [card(x, y, w, h, p)]
    c.append(f'<rect x="{x + 14}" y="{y + 12}" width="{w - 28}" height="26" rx="13" fill="{p["ink"]}"/>')
    sw = (w - 40) / 7
    wd = (today.weekday() + 1) % 7
    for i, name in enumerate(DAYS):
        cx = x + 20 + sw * i + sw / 2
        if i == wd:
            c.append(f'<rect x="{cx - 21:.1f}" y="{y + 15}" width="42" height="20" rx="10" fill="{p["card"]}"/>')
        c.append(text(cx, y + 30, name, 12, p["ink"] if i == wd else p["on_ink"], weight=700, anchor="middle"))
    c.append(f'<rect x="{x + 14}" y="{y + 50}" width="76" height="70" rx="14" fill="{p["ink"]}"/>')
    for k, ch in enumerate(f"{today.day:02d}"):
        c.append(seven(x + 24 + k * 30, y + 60, 24, 50, ch, p["on_ink"], p["on_ink"], 0.1))
    c.append(text(x + 106, y + 70, today.strftime("%m/%d"), 18, p["ink"], weight=600, spacing=1.5))
    c.append(text(x + w - 18, y + 70, WEEKDAYS[today.weekday()], 17, p["ink"], anchor="end"))
    c.append(text(x + 105, y + 110, wcfg.get("titulo", "HOLA"), 32, p["ink"], weight=800,
                  max_w=w - 125, spacing=1))
    c.append(f'<rect x="{x + 14}" y="{y + h - 36}" width="{w - 28}" height="24" rx="12" fill="{p["ink"]}"/>')
    last7 = d["last7"] or [(today - dt.timedelta(days=6 - i), None) for i in range(7)]
    peak = max([n or 0 for _, n in last7] + [1])
    for i, (day, n) in enumerate(last7):
        cx = x + 20 + sw * i + sw / 2
        c.append(text(cx, y + h - 19, f"{day.day:02d}", 12, p["on_ink"], weight=600, anchor="middle"))
        if n:
            c.append(f'<circle cx="{cx:.1f}" cy="{y + h - 44}" r="{2 + 2.5 * n / peak:.1f}" fill="{p["ink"]}"/>')
    pin_x = x + 20 + sw * 6 + sw / 2
    pin = (f'<path d="M{pin_x:.1f} {y + h - 39} L{pin_x - 5:.1f} {y + h - 47} A6.5 6.5 0 1 1 {pin_x + 5:.1f} '
           f'{y + h - 47} Z" fill="{p["accent"]}"/><circle cx="{pin_x:.1f}" cy="{y + h - 50}" r="2.2" '
           f'fill="{p["card"]}"/>')
    if a.on:
        pin = (f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" '
               f'dur="1.6s" begin="1.2s" repeatCount="indefinite"/>{pin}</g>')
    c.append(pin)
    parts.append(a.pop(0.1, "".join(c)))

    # ---- frase escrita a mano ----------------------------------------------
    x, y, w, h = 404, 28, 320, 168
    lines = wcfg.get("frase", [])[:4]
    c = [card(x, y, w, h, p)]
    cursor = f'<rect x="{x + 20}" y="{y + 30}" width="6" height="22" rx="3" fill="{p["ink"]}"/>'
    if a.on:
        cursor = cursor.replace("/>", '><animate attributeName="opacity" values="1;0" calcMode="discrete" '
                                      'dur="1s" repeatCount="indefinite"/></rect>')
    c.append(cursor)
    t = 0.7
    for i, line in enumerate(lines):
        ly = y + 50 + i * 33
        body = text(x + 38, ly, line, 21, p["ink"], font=HAND, max_w=w - 54)
        dur = 0.05 * len(line) + 0.15
        c.append(a.wipe(x + 30, ly - 28, w - 40, 40, t, dur, body))
        t += dur + 0.1
    parts.append(a.pop(0.2, "".join(c)))

    # ---- racha (tarjeta oscura) --------------------------------------------
    x, y, w, h = 740, 28, 192, 76
    c = [card(x, y, w, h, p, fill=p["ink"])]
    fx, fy = x + 34, y + 38
    c.append(f'<path d="M{fx} {fy + 20} C{fx - 12} {fy + 20} {fx - 15} {fy + 9} {fx - 10} {fy} C{fx - 8} '
             f'{fy + 6} {fx - 4} {fy + 7} {fx - 4} {fy + 7} C{fx - 5} {fy - 1} {fx} {fy - 9} {fx + 6} {fy - 14} '
             f'C{fx + 5} {fy - 6} {fx + 13} {fy - 1} {fx + 13} {fy + 8} C{fx + 13} {fy + 16} {fx + 8} {fy + 20} '
             f'{fx} {fy + 20} Z" fill="{p["on_ink"]}"/>')
    c.append(text(x + w - 16, y + 30, "Current streak", 14, p["on_ink"], anchor="end"))
    streak = "—" if d["streak"] is None else f'{d["streak"]} days'
    c.append(text(x + w - 16, y + 60, streak, 26, p["on_ink"], weight=700, anchor="end", spacing=1))
    parts.append(a.pop(0.3, "".join(c)))

    # ---- icono de barras: top 3 lenguajes ----------------------------------
    x, y, w, h = 740, 120, 88, 76
    c = [card(x, y, w, h, p)]
    langs = stats["langs"][:3] or [("", 30), ("", 60), ("", 45)]
    top = max(pct for _, pct in langs) or 1
    for i, (_, pct) in enumerate(langs):
        bh = 18 + 32 * pct / top
        bx, by = x + 18 + i * 19, y + h - 12 - bh
        c.append(f'<rect x="{bx}" y="{by:.1f}" width="14" height="{bh:.1f}" rx="7" '
                 f'fill="{p["ink"] if i == 0 else p["soft"]}" stroke="{p["ink"]}" stroke-width="2"/>')
        c.append(f'<circle cx="{bx + 7}" cy="{y + h - 20}" r="3.2" fill="{p["card"] if i == 0 else p["ink"]}"/>')
    parts.append(a.pop(0.35, "".join(c)))

    # ---- play ---------------------------------------------------------------
    x, y, w, h = 844, 120, 88, 76
    c = [card(x, y, w, h, p),
         f'<path d="M{x + 36} {y + 20} L{x + 56} {y + 38} L{x + 36} {y + 56}" fill="none" stroke="{p["ink"]}" '
         f'stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>',
         f'<path d="M{x + 36} {y + 20} L{x + 56} {y + 38} L{x + 36} {y + 56}" fill="none" stroke="{p["soft"]}" '
         f'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>']
    parts.append(a.pop(0.4, "".join(c)))

    # ---- LCD: contribuciones del último año -------------------------------
    x, y, w, h = 28, 212, 696, 96
    c = [card(x, y, w, h, p)]
    total = stats.get("contributions")
    digits = f"{total:05d}" if total is not None else "-----"
    for k, ch in enumerate(digits):
        dx = x + 26 + k * 58
        body = seven(dx, y + 16, 40, 64, ch, p["ink"], p["ink"], 0.08)
        c.append(a.show(0.8 + k * 0.12, body) if a.on else body)
    lx = x + 26 + len(digits) * 58 + 4
    c.append(text(lx, y + 34, "CONTRIB", 17, p["ink"], weight=700, spacing=1.5))
    c.append(text(lx, y + 54, "in the last year", 13, p["muted"]))
    weeks = (stats.get("weeks") or [])[-26:]
    if weeks:
        wpk = max(weeks) or 1
        sx0, base = x + w - 22 - len(weeks) * 9, y + h - 18
        bars = "".join(f'<rect x="{sx0 + i * 9:.1f}" y="{base - (3 + 44 * n / wpk):.1f}" width="6" '
                       f'height="{3 + 44 * n / wpk:.1f}" rx="2" fill="{p["ink"] if n else p["soft"]}"/>'
                       for i, n in enumerate(weeks))
        c.append(a.wipe(sx0 - 2, y + 10, len(weeks) * 9 + 4, h - 20, 1.3, 1.0, bars))
    parts.append(a.pop(0.5, "".join(c)))

    # ---- cuenta regresiva --------------------------------------------------
    x, y, w, h = 740, 212, 192, 96
    cr = wcfg.get("cuenta_regresiva", {"fecha": f"{today.year + 1}-01-01", "evento": str(today.year + 1)})
    left = max((dt.date.fromisoformat(cr["fecha"]) - today).days, 0)
    c = [card(x, y, w, h, p)]
    c.append(f'<text x="{x + w / 2}" y="{y + 32}" font-family="{esc(SANS)}" font-size="15" text-anchor="middle" '
             f'fill="{p["ink"]}">Days until <tspan font-size="20" font-weight="700" fill="{p["accent"]}">'
             f'{esc(cr["evento"])}</tspan></text>')
    num = str(left)
    bw, gap = 32, 8
    total_w = len(num) * bw + (len(num) - 1) * gap + 30
    bx0 = x + (w - total_w) / 2
    for k, ch in enumerate(num):
        bx = bx0 + k * (bw + gap)
        box = (f'<rect x="{bx:.1f}" y="{y + 44}" width="{bw}" height="38" rx="9" fill="{p["ink"]}"/>'
               + text(bx + bw / 2, y + 71, ch, 22, p["on_ink"], weight=700, anchor="middle"))
        c.append(a.show(1.0 + k * 0.15, box) if a.on else box)
    c.append(text(bx0 + len(num) * (bw + gap) - gap + 6, y + 80, "days", 13, p["ink"]))
    parts.append(a.pop(0.6, "".join(c)))

    # ---- pastillas con ilustración -----------------------------------------
    # oscura: noche, % de días activos en el año
    x, y, w, h = 28, 324, 104, 240
    c = [card(x, y, w, h, p, fill=p["ink"], r=44)]
    c.append(text(x + 16, y + 34, "Active", 15, p["on_ink"]))
    c.append(text(x + 16, y + 56, "—" if d["active_pct"] is None else f'{d["active_pct"]}%', 17, p["on_ink"],
                  weight=700))
    c.append(f'<circle cx="{x + 72}" cy="{y + 92}" r="17" fill="{p["on_ink"]}"/>'
             f'<circle cx="{x + 66}" cy="{y + 87}" r="4" fill="{p["ink"]}" opacity=".35"/>'
             f'<circle cx="{x + 77}" cy="{y + 99}" r="2.6" fill="{p["ink"]}" opacity=".35"/>')
    for sx, sy, r in ((x + 22, y + 82, 1.6), (x + 38, y + 108, 1.2), (x + 26, y + 128, 1.8), (x + 86, y + 130, 1.3),
                      (x + 52, y + 74, 1.1)):
        star = f'<circle cx="{sx}" cy="{sy}" r="{r}" fill="{p["on_ink"]}"/>'
        if a.on:
            star = star.replace("/>", f'><animate attributeName="opacity" values="1;.2;1" dur="{2 + r:.1f}s" '
                                      f'repeatCount="indefinite"/></circle>')
        c.append(star)
    c.append(f'<line x1="{x + 14}" y1="{y + 166}" x2="{x + w - 14}" y2="{y + 166}" stroke="{p["on_ink"]}" '
             f'stroke-width="1.6"/>')
    c.append(boat(x + 52, y + 160, p["on_ink"], p["ink"]))
    c.append(waves(x + 14, x + w - 12, y + 184, p["on_ink"]))
    parts.append(a.pop(0.7, "".join(c)))

    # clara: día, días activos en la semana
    x = 148
    c = [card(x, y, w, h, p, r=44)]
    c.append(text(x + 16, y + 34, "Week", 15, p["ink"]))
    c.append(text(x + 16, y + 56, "—" if d["week_active"] is None else f'{d["week_active"]}/7', 17, p["ink"],
                  weight=700))
    sun = [f'<circle cx="{x + 74}" cy="{y + 92}" r="13" fill="{p["ink"]}"/>']
    for k in range(10):
        ang = k * math.pi / 5
        sun.append(f'<line x1="{x + 74 + 17 * math.cos(ang):.1f}" y1="{y + 92 + 17 * math.sin(ang):.1f}" '
                   f'x2="{x + 74 + 22 * math.cos(ang):.1f}" y2="{y + 92 + 22 * math.sin(ang):.1f}" '
                   f'stroke="{p["ink"]}" stroke-width="2" stroke-linecap="round"/>')
    sun_g = "".join(sun)
    if a.on:
        sun_g = (f'<g>{sun_g}<animateTransform attributeName="transform" type="rotate" '
                 f'values="0 {x + 74} {y + 92};360 {x + 74} {y + 92}" dur="24s" repeatCount="indefinite"/></g>')
    c.append(sun_g)
    c.append(f'<path d="M{x + 20} {y + 120} q 10 -8 20 0 q 6 -6 12 0" fill="none" stroke="{p["ink"]}" '
             f'stroke-width="1.6" stroke-linecap="round"/>')
    c.append(f'<line x1="{x + 14}" y1="{y + 166}" x2="{x + w - 14}" y2="{y + 166}" stroke="{p["ink"]}" '
             f'stroke-width="1.6"/>')
    c.append(boat(x + 52, y + 160, p["ink"], p["card"]))
    c.append(waves(x + 14, x + w - 12, y + 184, p["ink"]))
    parts.append(a.pop(0.8, "".join(c)))

    # ---- barras de mes y año + lenguajes ------------------------------------
    x, bw = 278, 280
    days_month = calendar.monthrange(today.year, today.month)[1]
    year_len = 366 if calendar.isleap(today.year) else 365
    year_day = today.timetuple().tm_yday
    rows = [(today.day / days_month, f"This month: {days_month - today.day:02d} days left"),
            (year_day / year_len, f"This year: {year_len - year_day} days left")]
    c = []
    for i, (frac, label) in enumerate(rows):
        by = 340 + i * 82
        c.append(f'<rect x="{x + 2}" y="{by + 4}" width="{bw}" height="26" rx="13" fill="{p["shadow"]}"/>'
                 f'<rect x="{x}" y="{by}" width="{bw}" height="26" rx="13" fill="{p["card"]}" '
                 f'stroke="{p["ink"]}" stroke-width="2.5"/>')
        fill = f'<rect x="{x}" y="{by}" width="{bw * frac:.1f}" height="26" rx="13" fill="{p["ink"]}"/>'
        c.append(a.wipe(x - 2, by - 2, bw * frac + 4, 30, 1.2 + i * 0.25, 0.9, fill))
        c.append(text(x + 4, by + 56, label, 19, p["ink"], weight=500, max_w=bw))
    cx, cy = x, 512
    for name, _ in stats["langs"]:
        cw = len(name) * 7.8 + 26
        if cx + cw > x + bw + 10:
            break
        c.append(f'<rect x="{cx:.1f}" y="{cy}" width="{cw:.1f}" height="28" rx="14" fill="{p["card"]}" '
                 f'stroke="{p["ink"]}" stroke-width="2"/>'
                 + text(cx + cw / 2, cy + 19, name, 13, p["ink"], weight=600, anchor="middle"))
        cx += cw + 8
    parts.append(a.pop(0.9, "".join(c)))

    # ---- personaje: el gato del logo, con hojas cayendo ---------------------
    logo = cfg.get("fastfetch", {}).get("logo", "").strip("\n").split("\n")
    px = 13
    lw = max(len(line) for line in logo) * px
    lh = len(logo) * 2 * px
    lx, ly = 600 + (332 - lw) / 2, 572 - lh
    cat = pixel_art(logo, lx, ly, px, p["ink"])
    if a.on:
        cat = (f'<g>{cat}<animateTransform attributeName="transform" type="translate" values="0 0;0 -3;0 0" '
               f'dur="3.2s" begin="1.5s" repeatCount="indefinite"/></g>')
    greet = wcfg.get("saludo", "")
    bubble = ""
    if greet:
        bx, by = lx + lw - 75, ly - 62
        bwid = len(greet) * 11 + 30
        bubble = (f'<path d="M{bx + 18} {by + 40} L{bx + 8} {by + 56} L{bx + 34} {by + 40} Z" fill="{p["card"]}" '
                  f'stroke="{p["ink"]}" stroke-width="2.5" stroke-linejoin="round"/>'
                  f'<rect x="{bx}" y="{by}" width="{bwid}" height="42" rx="21" fill="{p["card"]}" '
                  f'stroke="{p["ink"]}" stroke-width="2.5"/>'
                  f'<rect x="{bx + 14}" y="{by + 36}" width="22" height="6" fill="{p["card"]}"/>'
                  + text(bx + bwid / 2, by + 28, greet, 20, p["ink"], font=HAND, anchor="middle"))
    parts.append(a.pop(1.0, cat))
    if bubble:
        parts.append(a.pop(1.6, bubble))

    # ---- ensamblado ----------------------------------------------------------
    title = f'{cfg["perfil"].get("nombre") or cfg["perfil"]["usuario"]} — profile'
    desc = "Cards with the date, GitHub contributions, streak, languages and an illustration."
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-labelledby="title desc"><title id="title">{esc(title)}</title>'
            f'<desc id="desc">{esc(desc)}</desc>'
            f'<defs><clipPath id="canvas"><rect width="{W}" height="{H}" rx="24"/></clipPath>{"".join(a.defs)}</defs>'
            f'<g clip-path="url(#canvas)"><rect width="{W}" height="{H}" fill="{p["bg"]}"/>'
            f'{leaves(a, p, (560, 300, 950, 600))}{"".join(parts)}</g></svg>\n')
