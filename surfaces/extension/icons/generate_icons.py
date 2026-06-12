"""Generate the extension's PNG icons with the stdlib only (no Pillow).

Run: ``python generate_icons.py`` — writes icon16/48/128.png next to this file.
A flat brand-accent rounded square; deterministic, so the committed PNGs are
reproducible. Kept in-repo so the binaries are never opaque.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ACCENT = (110, 168, 254)   # #6ea8fe — matches the editor accent
INK = (10, 14, 26)         # dark glyph
BG = (12, 15, 28)          # transparent corners fill (alpha 0)


def _rounded(size: int) -> bytes:
    """RGBA pixel rows for a rounded square with a simple 'W' notch glyph."""
    r = max(2, size // 6)            # corner radius
    bar = max(1, size // 8)          # glyph stroke width
    rows = bytearray()
    for y in range(size):
        rows.append(0)               # PNG filter type 0 per row
        for x in range(size):
            # rounded-corner alpha mask
            inside = True
            for cx, cy in ((r, r), (size - 1 - r, r), (r, size - 1 - r),
                           (size - 1 - r, size - 1 - r)):
                if ((x < r or x > size - 1 - r) and (y < r or y > size - 1 - r)
                        and (x - cx) ** 2 + (y - cy) ** 2 > r * r):
                    inside = False
                    break
            if not inside:
                rows += bytes((BG[0], BG[1], BG[2], 0))
                continue
            # a minimal 'W' drawn as two V strokes in the lower-middle band
            glyph = False
            top, bot = size * 0.30, size * 0.72
            if top <= y <= bot:
                t = (y - top) / max(1e-6, (bot - top))
                for x0 in (size * 0.30, size * 0.50):
                    cxp = x0 + t * (size * 0.14)
                    if abs(x - cxp) <= bar:
                        glyph = True
            col = INK if glyph else ACCENT
            rows += bytes((col[0], col[1], col[2], 255))
    return bytes(rows)


def _png(size: int) -> bytes:
    raw = _rounded(size)
    comp = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main() -> None:
    here = Path(__file__).resolve().parent
    for size in (16, 48, 128):
        (here / f"icon{size}.png").write_bytes(_png(size))
        print(f"wrote icon{size}.png")


if __name__ == "__main__":
    main()
