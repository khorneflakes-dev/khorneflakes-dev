"""Estilo "pipboy": pantalla CRT de fósforo con la estética de las interfaces de Fallout.

Lo llama scripts/generate.py cuando profile.toml tiene [perfil] estilo = "pipboy".
Fondo oscuro, scanlines, brillo de fósforo, la franja de refresco que baja por la pantalla,
pestañas STAT / INV / DATA, una lista S.P.E.C.I.A.L. con tus habilidades y barra de estado
abajo. Reutiliza las piezas de widgets.py.
"""

from __future__ import annotations

import base64
import calendar
import datetime as dt
import json
import struct
from pathlib import Path

from widgets import Anim, derive, esc, pixel_art, text

ROOT = Path(__file__).resolve().parents[1]

W, H = 960, 600

PHOSPHOR = {
    "verde": dict(fg="#2bff88", bg="#04140a", deep="#010703"),
    "ambar": dict(fg="#ffb83f", bg="#170e03", deep="#070401"),
    "azul": dict(fg="#2ee6ff", bg="#03111a", deep="#01060a"),
    "blanco": dict(fg="#e8f4ec", bg="#0c100e", deep="#040605"),
}

COND = "'Roboto Condensed', 'Arial Narrow', 'Liberation Sans Narrow', 'Helvetica Neue', Arial, sans-serif"


def label(x, y, s, size, color, **kw):
    kw.setdefault("font", COND)
    kw.setdefault("weight", 700)
    return text(x, y, s, size, color, **kw)


def slant_bar(x, y, w, h, frac, fg, bg) -> str:
    """Barra inclinada como las del reloj: contorno + relleno proporcional."""
    k = h * 0.6
    outline = f'<path d="M{x + k} {y} L{x + w} {y} L{x + w - k} {y + h} L{x} {y + h} Z" fill="none" ' \
              f'stroke="{fg}" stroke-width="2"/>'
    fw = max(min(frac, 1), 0) * (w - k)
    fill = f'<path d="M{x + k} {y} L{x + k + fw} {y} L{x + fw} {y + h} L{x} {y + h} Z" fill="{fg}"/>' if fw else ""
    return outline + fill


def vault_boy(fg: str, bg: str) -> str:
    """Vault Boy guiñando y con el pulgar arriba (fan art), en coordenadas locales 240 x 300.
    Relleno de fósforo con líneas oscuras, como los dibujos de la interfaz del juego."""
    line = f'stroke="{bg}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"'
    solid = f'fill="{fg}" {line}'
    hollow = f'fill="none" {line}'
    return "".join([
        # torso con el traje del refugio: cuello en V, cierre y costuras
        f'<path d="M34 300 C34 246 62 214 120 208 C178 214 204 246 204 300 Z" {solid}/>',
        f'<path d="M92 210 L120 240 L148 210" {hollow}/>',
        f'<path d="M120 240 L120 300 M70 236 C64 256 62 278 62 300" {hollow}/>',
        # cuello y orejas, debajo de la cabeza
        f'<path d="M104 182 L104 214 L136 214 L136 182 Z" {solid}/>',
        f'<ellipse cx="63" cy="130" rx="11" ry="17" {solid}/>',
        f'<ellipse cx="177" cy="130" rx="11" ry="17" {solid}/>',
        f'<path d="M60 124 C66 128 66 136 61 140 M180 124 C174 128 174 136 179 140" {hollow}/>',
        # cabeza
        f'<ellipse cx="120" cy="124" rx="58" ry="66" {solid}/>',
        # jopo con el rulo característico
        f'<path d="M63 118 C54 62 88 34 132 36 C176 38 190 72 179 118 C174 96 162 84 146 80 '
        f'C154 70 152 56 138 54 C126 70 104 78 86 82 C74 88 66 100 63 118 Z" {solid}/>',
        f'<path d="M98 50 C112 40 132 44 136 58 M84 64 C98 54 116 56 120 68 M150 46 C166 54 174 70 172 90" '
        f'{hollow}/>',
        # cejas, ojo abierto, guiño, nariz
        f'<path d="M86 104 Q98 96 110 103 M132 104 Q146 97 158 105" {hollow}/>',
        f'<ellipse cx="99" cy="120" rx="5.5" ry="8.5" fill="{bg}"/>',
        f'<path d="M134 122 Q146 112 158 122" {hollow}/>',
        f'<path d="M122 124 Q115 142 127 144" {hollow}/>',
        # sonrisa grande con hoyuelos
        f'<path d="M86 152 Q120 192 158 150 Q122 166 86 152 Z" fill="{bg}" {line}/>',
        f'<path d="M80 148 Q84 152 86 158 M164 146 Q160 150 158 156" {hollow}/>',
        # brazo y puño con el pulgar arriba
        f'<path d="M172 300 L202 300 C216 262 218 226 212 196 L184 196 C188 228 184 262 172 300 Z" {solid}/>',
        f'<path d="M196 156 L196 120 C196 108 212 108 212 120 L212 156" {solid}/>',
        f'<path d="M182 198 L182 164 C182 154 190 150 200 152 L228 156 C236 158 236 170 228 172 '
        f'C236 174 236 186 228 188 C236 190 236 200 226 202 L190 202 Z" {solid}/>',
        f'<path d="M228 172 L206 170 M228 188 L206 186 M184 204 L214 204" {hollow}/>',
    ])


def render(cfg: dict, stats: dict, mode: str, animate: bool, today: dt.date) -> str:
    pcfg = cfg.get("pipboy", {})
    tint = pcfg.get("color_oscuro" if mode == "dark" else "color_claro", "verde")
    c = PHOSPHOR.get(tint, PHOSPHOR["verde"])
    fg, bg = c["fg"], c["bg"]
    a = Anim(animate)
    d = derive(stats, today)
    user = cfg["perfil"].get("nombre") or cfg["perfil"]["usuario"]
    level = today.year - int(cfg["perfil"].get("programando_desde", today.year))
    out: list[str] = []

    # ---- encabezado ---------------------------------------------------------
    out.append(a.show(0.4, label(40, 48, pcfg.get("titulo", "DEV-BOY 3000"), 28, fg, spacing=4)
                      + label(42, 70, pcfg.get("subtitulo", "DATA INDUSTRIES"), 13, fg, spacing=3,
                              weight=400)))
    date_box = (f'<rect x="742" y="24" width="186" height="38" fill="none" stroke="{fg}" stroke-width="2"/>'
                + label(835, 52, today.strftime("%m.%d.%Y"), 24, fg, anchor="middle", spacing=2))
    out.append(a.show(0.5, date_box))

    # pestañas: la activa queda entre corchetes, como en el Pip-Boy
    tabs = ["STAT", "INV", "DATA", "MAP", "RADIO"]
    tx, ty, line_y = 290, 104, 110
    tab_svg, positions = [], []
    for i, name in enumerate(tabs):
        w = len(name) * 13 + 4
        positions.append((tx, tx + w))
        tab = label(tx + w / 2, ty, name, 20, fg, anchor="middle", spacing=1, weight=700 if i == 0 else 400)
        tab_svg.append(tab if i == 0 else tab.replace("<text ", '<text opacity=".55" '))
        tx += w + 46
    xa, xb = positions[0][0] - 10, positions[0][1] + 10
    tab_svg.append(f'<path d="M30 {line_y} L{xa} {line_y} L{xa} {line_y - 22} M{xb} {line_y - 22} L{xb} '
                   f'{line_y} L930 {line_y}" fill="none" stroke="{fg}" stroke-width="2"/>')
    out.append(a.show(0.55, "".join(tab_svg)))
    sub = [("STATUS", False), ("S.P.E.C.I.A.L.", True), ("PERKS", False)]
    sx, sub_svg = 44, []
    for name, active in sub:
        sub_svg.append(label(sx, 140, name, 16, fg, weight=700 if active else 400, spacing=1.5)
                       .replace("<text ", f'<text opacity="{1 if active else .45}" '))
        sx += len(name) * 10 + 34
    out.append(a.show(0.65, "".join(sub_svg)))

    # ---- S.P.E.C.I.A.L. -------------------------------------------------------
    special = pcfg.get("special", [])[:7]
    rows_y0, row_h, lx0, lx1 = 162, 40, 36, 330
    normal, high = [], []
    for i, (name, val) in enumerate(special):
        y = rows_y0 + i * row_h
        normal.append(label(lx0 + 12, y + 27, name.upper(), 20, fg, max_w=220, spacing=1)
                      + label(lx1 - 12, y + 27, str(val), 20, fg, anchor="end"))
        high.append(f'<rect x="{lx0}" y="{y + 4}" width="{lx1 - lx0}" height="{row_h - 6}" fill="{fg}"/>'
                    + label(lx0 + 12, y + 27, name.upper(), 20, bg, max_w=220, spacing=1)
                    + label(lx1 - 12, y + 27, str(val), 20, bg, anchor="end"))
    sp = ["".join(normal)]
    # la selección recorre la lista sola, como si alguien girara la ruedita
    n = len(high)
    for i, h_svg in enumerate(high):
        if not a.on:
            if i == 0:
                sp.append(h_svg)
            continue
        vals = ";".join("1" if k == i else "0" for k in range(n))
        sp.append(f'<g opacity="0"><animate attributeName="opacity" calcMode="discrete" values="{vals}" '
                  f'dur="{n * 1.6:.1f}s" begin="1.6s" repeatCount="indefinite"/>{h_svg}</g>')
    langs = " · ".join(name for name, _ in stats["langs"][:3])
    sp.append(label(lx0 + 2, rows_y0 + 7 * row_h + 30, f"PERKS ▸ {langs}", 15, fg, weight=400,
                    max_w=lx1 - lx0).replace("<text ", '<text opacity=".75" '))
    out.append(a.show(0.8, "".join(sp)))

    # ---- personaje: imagen, Vault Boy dibujado o el gato del logo -------------
    personaje = pcfg.get("personaje", "logo")
    bob = True
    if personaje == "animacion":
        # cuadros de scripts/trazar.py, alternados con opacidad discreta a los tiempos del GIF
        folder = ROOT / pcfg["animacion"]
        files = sorted(folder.glob("*.png"))
        durs = json.loads((folder / "frames.json").read_text(encoding="utf-8"))["duraciones_ms"][:len(files)]
        iw, ih = struct.unpack(">II", files[0].read_bytes()[16:24])
        hgt = 255
        wid = hgt * iw / ih
        total = sum(durs)
        kt = ";".join(f"{sum(durs[:i]) / total:.4f}" for i in range(len(files)))
        imgs = []
        for i, f in enumerate(files if a.on else files[:1]):
            img = (f'<image href="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}" '
                   f'x="{480 - wid / 2:.1f}" y="148" width="{wid:.1f}" height="{hgt}" filter="url(#tint)"')
            if a.on:
                vals = ";".join("1" if k == i else "0" for k in range(len(files)))
                img += (f' opacity="0"><animate attributeName="opacity" calcMode="discrete" values="{vals}" '
                        f'keyTimes="{kt}" dur="{total / 1000:.2f}s" repeatCount="indefinite"/></image>')
            else:
                img += "/>"
            imgs.append(img)
        cat = "".join(imgs)
        cat_y1 = 148 + hgt
        bob = False
    elif personaje == "imagen":
        # PNG con fondo transparente; el filtro lo pinta del color del fósforo
        data = (ROOT / pcfg["imagen"]).read_bytes()
        iw, ih = struct.unpack(">II", data[16:24])
        hgt = 255
        wid = hgt * iw / ih
        cat = (f'<image href="data:image/png;base64,{base64.b64encode(data).decode()}" x="{480 - wid / 2:.1f}" '
               f'y="148" width="{wid:.1f}" height="{hgt}" filter="url(#tint)"/>')
        cat_y1 = 148 + hgt
    elif personaje == "vaultboy":
        scale = 0.8
        cat = (f'<g transform="translate({480 - 120 * scale:.1f} 145) scale({scale})">'
               f'{vault_boy(fg, bg)}</g>')
        cat_y1 = 145 + 300 * scale
    else:
        logo = cfg.get("fastfetch", {}).get("logo", "").strip("\n").split("\n")
        px = 13
        lw = max(len(line) for line in logo) * px
        cx0, cy0 = 480 - lw / 2, 180
        cat = pixel_art(logo, cx0, cy0, px, fg)
        cat_y1 = cy0 + len(logo) * 2 * px
    if a.on and bob:
        cat = (f'<g>{cat}<animateTransform attributeName="transform" type="translate" '
               f'values="0 0;0 -5;0 0" dur="2.4s" begin="1.4s" repeatCount="indefinite"/></g>')
    under = label(480, cat_y1 + 46, user.upper(), 22, fg, anchor="middle", spacing=3, max_w=260)
    cursor = f'<rect x="{480 + 52}" y="{cat_y1 + 62}" width="11" height="18" fill="{fg}"/>'
    if a.on:
        cursor = cursor.replace("/>", '><animate attributeName="opacity" values="1;0" calcMode="discrete" '
                                      'dur="1s" repeatCount="indefinite"/></rect>')
    online = label(476, cat_y1 + 78, "> ONLINE", 16, fg, anchor="middle", weight=400, spacing=2) + cursor
    out.append(a.show(0.95, cat + under + online))

    # ---- columna derecha: contribuciones grandes + medidores -----------------
    rx = 640
    total = stats.get("contributions")
    big = [label(rx + 20, 255, "CONTRIB", 15, fg, spacing=3)
           .replace("<text ", f'<text transform="rotate(-90 {rx + 20} 255)" '),
           label(rx + 36, 250, "—" if total is None else str(total), 92, fg, max_w=250, spacing=-1),
           label(rx + 40, 278, "LAST YEAR", 13, fg, weight=400, spacing=2)
           .replace("<text ", '<text opacity=".75" ')]
    out.append(a.show(1.0, "".join(big)))
    gauges = [
        ("STREAK", d["streak"], 30, "" if d["streak"] is None else f'{d["streak"]}d'),
        ("ACTIVE", d["active_pct"], 100, "" if d["active_pct"] is None else f'{d["active_pct"]}%'),
        ("STARS", stats["stars"], 100, str(stats["stars"])),
        ("FOLLOWERS", stats["followers"], 100, str(stats["followers"])),
    ]
    for i, (name, val, ref, shown) in enumerate(gauges):
        y = 312 + i * 50
        g = [label(rx + 20, y, name, 16, fg, spacing=1.5)]
        bar = slant_bar(rx + 20, y + 9, 190, 16, (val or 0) / ref, fg, bg)
        g.append(a.wipe(rx + 14, y + 4, 200, 26, 1.3 + i * 0.15, 0.7, bar))
        g.append(label(rx + 290, y + 25, shown or "—", 26, fg, anchor="end"))
        out.append(a.show(1.1 + i * 0.1, "".join(g)))

    # ---- barra de estado (HP / LEVEL / AP) -----------------------------------
    year_len = 366 if calendar.isleap(today.year) else 365
    xp = today.timetuple().tm_yday / year_len
    by, bh = 522, 42
    status = [
        f'<rect x="30" y="{by}" width="270" height="{bh}" fill="{fg}" opacity=".16"/>',
        label(46, by + 29, f'REPOS {stats["repos"]}', 20, fg, spacing=1),
        f'<rect x="310" y="{by}" width="340" height="{bh}" fill="{fg}" opacity=".16"/>',
        label(326, by + 29, f"LEVEL {level}", 20, fg, spacing=1),
        f'<rect x="436" y="{by + 15}" width="196" height="12" fill="none" stroke="{fg}" stroke-width="2"/>',
        a.wipe(436, by + 13, 196 * xp + 2, 16, 1.6, 1.0,
               f'<rect x="436" y="{by + 15}" width="{196 * xp:.1f}" height="12" fill="{fg}"/>'),
        f'<rect x="660" y="{by}" width="270" height="{bh}" fill="{fg}" opacity=".16"/>',
        label(914, by + 29, "WEEK " + ("—" if d["week_active"] is None else f'{d["week_active"]}/7'),
              20, fg, anchor="end", spacing=1),
    ]
    out.append(a.show(0.7, "".join(status)))

    # ---- pantalla CRT ----------------------------------------------------------
    defs = (
        f'<clipPath id="screen"><rect x="12" y="12" width="{W - 24}" height="{H - 24}" rx="30"/></clipPath>'
        f'<pattern id="lines" width="4" height="4" patternUnits="userSpaceOnUse">'
        f'<rect width="4" height="1.3" fill="{fg}" opacity=".07"/></pattern>'
        f'<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse">'
        f'<rect width="4" height="1.2" fill="#000" opacity=".35"/></pattern>'
        f'<radialGradient id="vignette" cx=".5" cy=".5" r=".8"><stop offset=".7" stop-color="#000" '
        f'stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".5"/></radialGradient>'
        f'<radialGradient id="bloom" cx=".5" cy=".45" r=".6"><stop stop-color="{fg}" stop-opacity=".09"/>'
        f'<stop offset="1" stop-color="{fg}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="roll" x1="0" y1="0" x2="0" y2="1"><stop stop-color="{fg}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{fg}" stop-opacity=".07"/><stop offset="1" stop-color="{fg}" '
        f'stop-opacity="0"/></linearGradient>'
        f'<filter id="tint"><feFlood flood-color="{fg}"/><feComposite in2="SourceAlpha" operator="in"/></filter>'
        '<filter id="glow" x="-5%" y="-5%" width="110%" height="110%">'
        '<feGaussianBlur stdDeviation="2.4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        + "".join(a.defs)
    )
    content = "".join(out)
    if a.on:
        # parpadeo leve del fósforo + encendido: la imagen se abre desde una línea al centro
        content = (f'<g><animate attributeName="opacity" values="1;1;.86;1;.95;1;1" '
                   f'keyTimes="0;.55;.56;.58;.6;.62;1" dur="6s" repeatCount="indefinite"/>{content}</g>')
        content = (f'<g transform="translate({W / 2} {H / 2})"><g><animateTransform attributeName="transform" '
                   f'type="scale" values="1 .004;1 .004;1 1" keyTimes="0;.3;1" dur=".55s" fill="freeze" '
                   f'calcMode="spline" keySplines="0 0 1 1;.2 .8 .3 1"/>'
                   f'<g transform="translate({-W / 2} {-H / 2})">{content}</g></g></g>')
    roll = ""
    if a.on:
        roll = (f'<rect x="0" y="-160" width="{W}" height="160" fill="url(#roll)">'
                f'<animateTransform attributeName="transform" type="translate" values="0 0;0 {H + 160}" '
                f'dur="7s" repeatCount="indefinite"/></rect>')

    title = f"{user} — phosphor terminal"
    desc = "Fallout-style green CRT screen with skills, GitHub contributions, streak and level."
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-labelledby="title desc"><title id="title">{esc(title)}</title>'
            f'<desc id="desc">{esc(desc)}</desc><defs>{defs}</defs>'
            f'<rect width="{W}" height="{H}" rx="40" fill="{c["deep"]}"/>'
            f'<g clip-path="url(#screen)">'
            f'<rect width="{W}" height="{H}" fill="{bg}"/><rect width="{W}" height="{H}" fill="url(#lines)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#bloom)"/>'
            f'<g filter="url(#glow)">{content}</g>{roll}'
            f'<rect width="{W}" height="{H}" fill="url(#scan)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#vignette)"/></g>'
            f'<rect x="12" y="12" width="{W - 24}" height="{H - 24}" rx="30" fill="none" stroke="{fg}" '
            f'stroke-opacity=".25" stroke-width="2"/></svg>\n')
