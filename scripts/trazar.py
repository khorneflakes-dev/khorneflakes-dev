#!/usr/bin/env python3
"""Convierte un GIF (o PNG) de una figura clara sobre fondo oscuro en cuadros listos para el SVG.

Cada cuadro queda como PNG blanco con fondo transparente: el generador lo pinta del color del
fósforo. Los trazos oscuros de adentro del dibujo quedan transparentes, así se ven las líneas.

Necesita Pillow (solo este script; el generador sigue sin dependencias):
    uv run --with pillow python scripts/trazar.py ~/Downloads/vaultboywalking.gif assets/source/walk

Escribe <salida>/00.png, 01.png, ... y <salida>/frames.json con la duración de cada cuadro.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageSequence


def largest_component(mask: Image.Image) -> Image.Image:
    """La mancha clara más grande: la figura, sin ruido ni textos sueltos alrededor."""
    w, h = mask.size
    px = mask.load()
    seen: set[tuple[int, int]] = set()
    best: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if not px[x, y] or (x, y) in seen:
                continue
            comp, q = [], deque([(x, y)])
            seen.add((x, y))
            while q:
                cx, cy = q.popleft()
                comp.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        n = (cx + dx, cy + dy)
                        if 0 <= n[0] < w and 0 <= n[1] < h and px[n] and n not in seen:
                            seen.add(n)
                            q.append(n)
            if len(comp) > len(best):
                best = comp
    out = Image.new("L", (w, h), 0)
    for p in best:
        out.putpixel(p, 255)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", help="GIF o PNG")
    ap.add_argument("salida", help="carpeta donde dejar los cuadros")
    ap.add_argument("--umbral", type=int, default=70, help="brillo mínimo del relleno (0-255); "
                    "más alto = trazos más gruesos")
    ap.add_argument("--fondo", type=int, default=15, help="brillo mínimo para considerar algo parte de la figura")
    ap.add_argument("--escala", type=int, default=2, help="aumento antes de recortar el borde (suaviza)")
    args = ap.parse_args()

    src = Image.open(args.entrada)
    frames = [f.convert("RGB") for f in ImageSequence.Iterator(src)]
    durations = [f.info.get("duration", 100) or 100 for f in ImageSequence.Iterator(Image.open(args.entrada))]

    # canal más brillante: sirve para fósforo verde, ámbar o lo que sea
    lum = [ImageChops.lighter(ImageChops.lighter(f.getchannel("R"), f.getchannel("G")), f.getchannel("B"))
           for f in frames]
    regions = [largest_component(l.point(lambda v: 255 if v > args.fondo else 0)) for l in lum]

    # mismo recorte para todos los cuadros, así la figura no salta de lugar
    boxes = [r.getbbox() for r in regions]
    box = (min(b[0] for b in boxes) - 2, min(b[1] for b in boxes) - 2,
           max(b[2] for b in boxes) + 2, max(b[3] for b in boxes) + 2)

    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    k = args.escala
    for i, (l, r) in enumerate(zip(lum, regions)):
        size = ((box[2] - box[0]) * k, (box[3] - box[1]) * k)
        up = l.crop(box).resize(size, Image.BICUBIC)
        reg = r.crop(box).resize(size, Image.BILINEAR)
        alpha = ImageChops.multiply(up.point(lambda v: 255 if v > args.umbral else 0),
                                    reg.point(lambda v: 255 if v > 100 else 0))
        frame = Image.new("RGBA", size, (255, 255, 255, 0))
        frame.putalpha(alpha)
        frame.save(out / f"{i:02d}.png", optimize=True)
    (out / "frames.json").write_text(json.dumps({"duraciones_ms": durations}, indent=2), encoding="utf-8")
    print(f"{len(frames)} cuadros de {size[0]}x{size[1]} en {out}")


if __name__ == "__main__":
    main()
