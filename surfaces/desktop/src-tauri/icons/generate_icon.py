"""Generate the desktop app's base icon (512px PNG) with the stdlib only.

Run: ``python generate_icon.py`` — writes ``icon.png`` next to this file. Use
Tauri's icon tooling (``cargo tauri icon icons/icon.png`` / ``npm run tauri
icon``) to derive the platform-specific .ico/.icns/png set at build time.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ACCENT = (110, 168, 254)   # #6ea8fe
INK = (10, 14, 26)
SIZE = 512


def _pixels() -> bytes:
    r = SIZE // 6
    bar = SIZE // 8
    rows = bytearray()
    for y in range(SIZE):
        rows.append(0)
        for x in range(SIZE):
            inside = True
            for cx, cy in ((r, r), (SIZE - 1 - r, r), (r, SIZE - 1 - r),
                           (SIZE - 1 - r, SIZE - 1 - r)):
                if ((x < r or x > SIZE - 1 - r) and (y < r or y > SIZE - 1 - r)
                        and (x - cx) ** 2 + (y - cy) ** 2 > r * r):
                    inside = False
                    break
            if not inside:
                rows += bytes((12, 15, 28, 0))
                continue
            glyph = False
            top, bot = SIZE * 0.30, SIZE * 0.72
            if top <= y <= bot:
                t = (y - top) / (bot - top)
                for x0 in (SIZE * 0.30, SIZE * 0.50):
                    if abs(x - (x0 + t * (SIZE * 0.14))) <= bar:
                        glyph = True
            col = INK if glyph else ACCENT
            rows += bytes((col[0], col[1], col[2], 255))
    return bytes(rows)


def main() -> None:
    comp = zlib.compress(_pixels(), 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    out = Path(__file__).resolve().parent / "icon.png"
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
