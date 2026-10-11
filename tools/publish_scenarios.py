#!/usr/bin/env python3
"""publish_scenarios.py - publica los mapas y CSV de out/ en el dashboard.

Copia lo que genera `scenarios.py` (y `plots.py`) a la carpeta estatica del
servidor y escribe un manifiesto para que el dashboard no tenga que adivinar
nombres ni repetir los supuestos:

    out/s2a_mejora.png     -> server/static/img/s2a_mejora.png
    out/s2b_cobertura.png  -> server/static/img/s2b_cobertura.png
    out/s3_recarga.png     -> server/static/img/s3_recarga.png
    out/*.csv              -> server/static/csv/*.csv
    (nuevo)                -> server/static/scenarios.json

El manifiesto lleva los titulos, el numero de filas de cada CSV y el texto de
`scenarios.assumptions_text()`, que es el pie "Supuestos" de la pestana de
Escenarios. Asi el HTML es un solo archivo y no duplica texto de Python.

Uso:
    python3 scenarios.py                 # primero, para generar out/
    python3 tools/publish_scenarios.py   # despues, para publicar
"""

import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

# id -> (titulo, pie de imagen). Los titulos coinciden con los de plots.py.
ESCENARIOS = [
    ("s2a_mejora", "S2a - Cuanto ayuda priorizar la nevera",
     "Mejora del tiempo protegido frente a no hacer nada, segun bateria y % de carga no critica (corte de 12 h)."),
    ("s2b_cobertura", "S2b - La nevera aguanta todo el corte?",
     "Si el tiempo protegido cubre la duracion del corte, segun bateria y duracion."),
    ("s3_recarga", "S3 - Alcanza a recargarse entre cortes?",
     "Estado tras un corte diario segun cargador y duracion del corte (eficiencia 0.85)."),
]


def contar_filas(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return sum(1 for _ in csv.reader(fh)) - 1    # menos la cabecera


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publica out/ en server/static/.")
    ap.add_argument("--out", default=os.path.join(RAIZ, "out"),
                    help="carpeta con lo generado por scenarios.py (por defecto: out/)")
    ap.add_argument("--dest", default=os.path.join(RAIZ, "server", "static"),
                    help="carpeta estatica del servidor (por defecto: server/static)")
    args = ap.parse_args(argv)

    img_dest = os.path.join(args.dest, "img")
    csv_dest = os.path.join(args.dest, "csv")
    os.makedirs(img_dest, exist_ok=True)
    os.makedirs(csv_dest, exist_ok=True)

    faltan = []
    items = []
    for nombre, titulo, nota in ESCENARIOS:
        png_src = os.path.join(args.out, nombre + ".png")
        csv_src = os.path.join(args.out, nombre + ".csv")
        ausentes = [os.path.relpath(s, RAIZ) for s in (png_src, csv_src)
                    if not os.path.exists(s)]
        if ausentes:
            faltan.extend(ausentes)
            continue
        shutil.copyfile(png_src, os.path.join(img_dest, nombre + ".png"))
        shutil.copyfile(csv_src, os.path.join(csv_dest, nombre + ".csv"))
        items.append({
            "id": nombre,
            "titulo": titulo,
            "nota": nota,
            "png": "static/img/%s.png" % nombre,
            "csv": "static/csv/%s.csv" % nombre,
            "filas": contar_filas(csv_src),
        })

    if faltan:
        print("Faltan archivos: %s" % ", ".join(faltan), file=sys.stderr)
        print("Corre primero:  python3 scenarios.py", file=sys.stderr)
        return 1

    import scenarios    # importa config.py de la raiz; no necesita matplotlib

    manifiesto = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "simulado": True,
        "supuestos": scenarios.assumptions_text(),
        "escenarios": items,
    }
    ruta = os.path.join(args.dest, "scenarios.json")
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(manifiesto, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    for it in items:
        print("%-14s %2d filas -> %s" % (it["id"], it["filas"], it["png"]))
    print("manifiesto -> %s" % os.path.relpath(ruta, RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
