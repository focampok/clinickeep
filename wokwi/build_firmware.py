#!/usr/bin/env python3
"""Empaqueta main.py + modulos en una imagen flash con MicroPython + LittleFS.

Uso:
  python3 build_firmware.py

Genera firmware.bin listo para wokwi.toml / wokwi-cli / MCP.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

try:
    from littlefs import LittleFS
except ImportError as e:
    raise SystemExit(
        "Falta littlefs-python. Instala con: pip install littlefs-python"
    ) from e

DIR = Path(__file__).resolve().parent
FW_NAME = "ESP32_GENERIC-20251209-v1.27.0.bin"
FW_URL = f"https://micropython.org/resources/firmware/{FW_NAME}"
FW_STOCK = DIR / FW_NAME
OUT = DIR / "firmware.bin"

FIRMWARE_OFFSET = 0x1000
FLASH_SIZE = 0x400000
FS_OFFSET = 0x200000
FS_SIZE = 0x200000

PY_FILES = ("main.py", "config.py", "policy.py", "ssd1306.py")


def main() -> None:
    if not FW_STOCK.exists():
        print(f"Descargando {FW_NAME}…")
        urllib.request.urlretrieve(FW_URL, FW_STOCK)
        print(f"  -> {FW_STOCK} ({FW_STOCK.stat().st_size} bytes)")

    stock = FW_STOCK.read_bytes()
    image = bytearray(FLASH_SIZE)
    image[FIRMWARE_OFFSET : FIRMWARE_OFFSET + len(stock)] = stock

    lfs = LittleFS(block_size=4096, block_count=FS_SIZE // 4096, prog_size=256)
    for name in PY_FILES:
        src = DIR / name
        if not src.exists():
            raise SystemExit(f"Falta {src}")
        with lfs.open(name, "w") as fh:
            fh.write(src.read_text(encoding="utf-8"))
        print(f"  + {name}")

    image[FS_OFFSET : FS_OFFSET + FS_SIZE] = lfs.context.buffer
    OUT.write_bytes(bytes(image))
    print(f"OK: {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
