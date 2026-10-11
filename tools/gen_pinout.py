#!/usr/bin/env python3
"""Genera docs/PINOUT.md leyendo wokwi/diagram.json.

El GPIO, el componente y el pin del componente se DERIVAN del diagrama: si mueves
un cable, la tabla cambia. El nombre de la senal y la nota son intencion de diseno,
por eso viven en SIGNALS aqui abajo.

Si hay un GPIO cableado que no esta en SIGNALS (o al reves), el script lo avisa y
sale con codigo 1: asi la tabla y el circuito no se pueden desincronizar en silencio.

Uso:
  python3 tools/gen_pinout.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAM = ROOT / "wokwi" / "diagram.json"
OUT = ROOT / "docs" / "PINOUT.md"
SCHEMA = ROOT / "docs" / "SCHEMA.md"
CIRKIT_URL = "https://app.cirkitdesigner.com/project/4e224752-621d-45eb-b841-17e5f0f924d7"

# GPIO -> (senal, nota). El orden de esta lista es el orden de la tabla.
SIGNALS = [
    (34, "Red: hay red / corte", "Interruptor deslizante. Nivel alto = hay red."),
    (35, "Potencia de la zona A", "Potenciómetro. **Emula el INA219 (hardware FUTURO).**"),
    (4, "Temperatura de la nevera", "DS18B20 por OneWire, con pull-up de 4.7 kΩ."),
    (26, "Relé zona B (luces de pasillo)", "1 = abierto = carga **sin** energía."),
    (27, "Relé zona C (sala de espera)", "1 = abierto = carga **sin** energía."),
    (25, "Buzzer (alarma)", "PWM. Suena en CRITICO y con fallo del sensor."),
    (13, "Botón k (reloj SIM)", "Pulsador azul o tecla K: cicla k = 1 / 60 / 600."),
    (14, "Botón CORTE manual", "Pulsador rojo o tecla G. Solo manual; el CI usa GRID0/GRID1."),
    (21, "I2C SDA (OLED)", "SSD1306 128x64 en la dirección 0x3C."),
    (22, "I2C SCL (OLED)", "SSD1306 128x64 en la dirección 0x3C."),
]

# Partes que aparecen en el diagrama y no son el ESP32 ni un bus de alimentación.
NOT_A_SIGNAL = {"esp"}


def load_diagram():
    with DIAGRAM.open(encoding="utf-8") as fh:
        return json.load(fh)


def part_label(diagram, part_id):
    for part in diagram.get("parts", []):
        if part.get("id") == part_id:
            label = (part.get("attrs") or {}).get("label")
            kind = part.get("type", "?")
            return f"{part_id} ({label})" if label else f"{part_id} ({kind})"
    return part_id


def wired_pins(diagram):
    """GPIO del ESP32 -> (part_id, pin del componente) segun las conexiones."""
    found = {}
    for conn in diagram.get("connections", []):
        if len(conn) < 2:
            continue
        a, b = conn[0], conn[1]
        for here, other in ((a, b), (b, a)):
            if not here.startswith("esp:"):
                continue
            gpio = here.split(":", 1)[1]
            if not gpio.isdigit():
                continue          # alimentacion / GND / TX-RX
            part, _, pin = other.partition(":")
            if part in NOT_A_SIGNAL:
                continue
            found[int(gpio)] = (part, pin)
    return found


def build_rows(diagram):
    wired = wired_pins(diagram)
    rows = []
    for gpio, name, note in SIGNALS:
        if gpio in wired:
            part, pin = wired[gpio]
            rows.append((name, gpio, part_label(diagram, part), pin, note, True))
        else:
            rows.append((name, gpio, "—", "—", note, False))
    extra = sorted(set(wired) - {g for g, _, _ in SIGNALS})
    return rows, extra


def render(rows, extra):
    lines = [
        "# Pinout del banco de pruebas",
        "",
        "Generado por `tools/gen_pinout.py` a partir de `wokwi/diagram.json`. No lo edites",
        "a mano: cambia el diagrama (o `SIGNALS` en el script) y vuelve a correrlo.",
        "",
        "Niveles de los relés: `1` = abierto (carga sin energía, estado seguro),",
        "`0` = cerrado (carga con energía). Ver `docs/RELAY_CHECK.md`.",
        "",
        "| Señal | GPIO | Componente | Pin | Nota |",
        "|---|---|---|---|---|",
    ]
    for name, gpio, part, pin, note, ok in rows:
        mark = "" if ok else " **(sin cablear!)**"
        lines.append(f"| {name} | GPIO{gpio} | {part}{mark} | {pin} | {note} |")

    lines += [
        "",
        "La zona A (nevera de vacunas) **no tiene relé**: es la carga crítica y el software",
        "nunca la corta (`relay_a` siempre es `true`). Por eso no aparece un GPIO de salida para A.",
        "",
        "## INA219: hardware futuro, no está en la simulación",
        "",
        "El **INA219** (sensor de corriente y voltaje de la zona A) es **hardware FUTURO**.",
        "**Wokwi no tiene ese componente.** En la simulación la medición de potencia de A se",
        "**emula con un potenciómetro** en GPIO35, siempre detrás de la capa de abstracción",
        "(`read_power_a_w()` en `wokwi/main.py`): cuando exista el INA219 real, se reemplaza",
        "solo esa función y la política no se toca.",
    ]
    if extra:
        lines += [
            "",
            "## GPIO cableados que no están en la tabla",
            "",
            "Aparecen en `diagram.json` pero no en `SIGNALS`: " +
            ", ".join(f"GPIO{g}" for g in extra) + ". Revisa `tools/gen_pinout.py`.",
        ]
    lines.append("")
    return "\n".join(lines)


def render_schema(diagram):
    wired = wired_pins(diagram)
    lines = [
        "# Esquema del circuito",
        "",
        "Generado por `tools/gen_pinout.py` a partir de `wokwi/diagram.json`.",
        "",
        "> El esquema de Cirkit no se puede editar desde este repo; el proyecto real está en",
        f"> <{CIRKIT_URL}>",
        "> (protoboard, con el INA219 en lugar del potenciómetro). Este archivo es la",
        "> exportación en texto, para revisar que las etiquetas coincidan con `docs/PINOUT.md`.",
        "",
        "## Señales del ESP32",
        "",
        "```mermaid",
        "graph LR",
        '  ESP["ESP32 DevKit C V4"]',
    ]
    for gpio, name, _ in SIGNALS:
        if gpio in wired:
            lines.append(f'  P{gpio}["{name}"] ---|GPIO{gpio}| ESP')
    lines += [
        "```",
        "",
        "## Todas las conexiones",
        "",
        "Fuente: `wokwi/diagram.json` (incluye alimentación, GND y el cableado relé→LED).",
        "",
        "| Desde | Hasta | Color |",
        "|---|---|---|",
    ]
    for conn in diagram.get("connections", []):
        if len(conn) < 3:
            continue
        lines.append(f"| `{conn[0]}` | `{conn[1]}` | {conn[2] or '—'} |")
    lines += [
        "",
        "## Hardware real: INA219 (futuro)",
        "",
        "En la maqueta real el potenciómetro se reemplaza por el **INA219**, compartiendo el bus",
        "I²C de la OLED (SDA GPIO21, SCL GPIO22) en la dirección **0x40**, con VIN+/VIN− en serie",
        "con la carga de la zona A (puntos A3/A4 de la protoboard). Wokwi no tiene ese componente,",
        "así que la simulación usa el potenciómetro en GPIO35.",
        "",
    ]
    return "\n".join(lines)


def main():
    diagram = load_diagram()
    rows, extra = build_rows(diagram)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(rows, extra), encoding="utf-8")
    SCHEMA.write_text(render_schema(diagram), encoding="utf-8")
    print(f"OK: {OUT}")
    print(f"OK: {SCHEMA}")

    missing = [g for _, g, _, _, _, ok in rows if not ok]
    if missing:
        print("AVISO: en SIGNALS pero sin cablear en el diagrama: " +
              ", ".join(f"GPIO{g}" for g in missing), file=sys.stderr)
    if extra:
        print("AVISO: cableados en el diagrama pero fuera de SIGNALS: " +
              ", ".join(f"GPIO{g}" for g in extra), file=sys.stderr)
    return 1 if (missing or extra) else 0


if __name__ == "__main__":
    raise SystemExit(main())
