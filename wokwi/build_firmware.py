#!/usr/bin/env python3
"""Empaqueta main.py + modulos en una imagen flash con MicroPython + LittleFS.

Uso:
  python3 build_firmware.py              # sincroniza desde la raiz y empaqueta
  python3 build_firmware.py --sync-only  # solo sincroniza, sin empaquetar

Antes de empaquetar copia policy.py y config.py desde la raiz del repo: esos dos
archivos NO se editan a mano en wokwi/, la raiz es la fuente de verdad
(lo comprueba tests/test_sync.py).

Genera firmware.bin listo para wokwi.toml / wokwi-cli / MCP.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

try:
    from littlefs import LittleFS
except ImportError as e:
    raise SystemExit(
        "Falta littlefs-python. Instala con: pip install littlefs-python"
    ) from e

DIR = Path(__file__).resolve().parent
ROOT = DIR.parent  # raiz del repo: fuente de verdad de policy.py y config.py
FW_NAME = "ESP32_GENERIC-20251209-v1.27.0.bin"
FW_URL = f"https://micropython.org/resources/firmware/{FW_NAME}"
FW_STOCK = DIR / FW_NAME
OUT = DIR / "firmware.bin"

FIRMWARE_OFFSET = 0x1000
FLASH_SIZE = 0x400000
FS_OFFSET = 0x200000
FS_SIZE = 0x200000

SYNC_FILES = ("policy.py", "config.py")   # se copian desde la raiz; no editar aqui
LOCAL_FILES = ("main.py", "ssd1306.py")   # exclusivos del firmware
PY_FILES = SYNC_FILES + LOCAL_FILES


def sync_from_root() -> None:
    """Copia policy.py y config.py de la raiz del repo a wokwi/.

    La raiz manda: si wokwi/ difiere, se sobrescribe sin preguntar.
    """
    for name in SYNC_FILES:
        src = ROOT / name
        if not src.exists():
            raise SystemExit(f"Falta {src} (fuente de verdad del repo)")
        data = src.read_bytes()
        dst = DIR / name
        if dst.exists() and dst.read_bytes() == data:
            print(f"  = {name} (ya sincronizado)")
        else:
            dst.write_bytes(data)
            print(f"  ^ {name} <- raiz")


def main() -> None:
    print("Sincronizando desde la raiz…")
    sync_from_root()
    if "--sync-only" in sys.argv:
        print("OK: solo sincronizacion")
        return

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
