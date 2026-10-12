#!/usr/bin/env python3
"""publish_calc.py - publica la calculadora de dimensionamiento en el servidor.

Copia `calc/` a la carpeta estatica del servicio, igual que
`publish_scenarios.py` hace con los mapas y los CSV:

    calc/index.html -> server/static/calc/index.html
    calc/calc.js    -> server/static/calc/calc.js

Asi `server/` sigue siendo autocontenido: no lee nada de `calc/` en tiempo de
ejecucion, solo sirve la copia. La pagina se sirve en `/calc`.

Antes de copiar compara los valores por defecto de `calc.js` con los de
`scenarios.py` y `config.py`, que son la fuente de verdad. Si alguien mueve uno
y no el otro, lo dice: es un aviso, no un error (puede ser a proposito).

Uso:
    python3 tools/publish_calc.py
    python3 tools/publish_calc.py --origen calc --dest server/static
"""

import argparse
import inspect
import os
import re
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

FICHEROS = ("index.html", "calc.js")

# clave en calc.js -> (modulo, constante) de la fuente de verdad
ESPEJO = (
    ("a_w", "scenarios", "A_W"),
    ("b_w", "scenarios", "B_W"),
    ("c_w", "scenarios", "C_W"),
    ("eta", "scenarios", "ETA_CHARGE"),
    ("t_amb_c", "scenarios", "T_AMB_C"),
    ("tau_h", "config", "TAU_H"),
    ("t_hi_c", "config", "T_HI_C"),
    ("t_lim_c", "config", "T_LIM_C"),
)


def valor_defecto(js, clave):
    """El `valor:` de un campo de DEFAULTS en calc.js (None si no se puede leer)."""
    campo = re.search(r"\n  %s: \{(.*?)\n  \}," % clave, js, re.S)
    if not campo:
        return None
    numero = re.search(r"valor:\s*(-?[\d.]+)", campo.group(1))
    return float(numero.group(1)) if numero else None


def comparar_con_la_fuente(js):
    """Compara los defectos de calc.js con scenarios.py/config.py."""
    import config
    import scenarios

    def esperado_de(modulo, constante):
        # config.py es una clase; scenarios.py, constantes sueltas.
        return getattr(config.Config if modulo == "config" else scenarios, constante)

    avisos = []
    print("%-12s %-10s %-10s %s" % ("campo", "calc.js", "fuente", "origen"))
    for clave, modulo, constante in ESPEJO:
        esperado = esperado_de(modulo, constante)
        obtenido = valor_defecto(js, clave)
        origen = "%s.py: %s" % (modulo, constante)
        if obtenido is None:
            avisos.append("%s: no se pudo leer de calc.js" % clave)
        elif abs(obtenido - esperado) > 1e-9:
            avisos.append("%s: calc.js dice %s y %s dice %s" % (clave, obtenido, origen, esperado))
        print("%-12s %-10s %-10s %s" % (clave, obtenido, esperado, origen))

    # La energia util (nominal x profundidad) tiene que dar la E_UTIL_WH del firmware.
    nominal = valor_defecto(js, "nominal_wh")
    dod = valor_defecto(js, "dod_pct")
    if nominal is not None and dod is not None:
        util = nominal * dod / 100.0
        print("%-12s %-10s %-10s %s" % ("E_UTIL_WH", util, config.Config.E_UTIL_WH,
                                        "nominal_wh x dod_pct / 100"))
        if abs(util - config.Config.E_UTIL_WH) > 1e-9:
            avisos.append("E_UTIL_WH: calc.js da %s Wh y config.py dice %s Wh"
                          % (util, config.Config.E_UTIL_WH))

    # La duracion de corte por defecto sale del barrido S2a.
    d_calc = valor_defecto(js, "d_h")
    d_sc = inspect.signature(scenarios.sweep_s2a).parameters["d_h"].default
    print("%-12s %-10s %-10s %s" % ("d_h", d_calc, d_sc, "scenarios.py: sweep_s2a(d_h=...)"))
    if d_calc is not None and abs(d_calc - d_sc) > 1e-9:
        avisos.append("d_h: calc.js dice %s y el barrido S2a usa %s" % (d_calc, d_sc))

    return avisos


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publica calc/ en la carpeta estatica del servidor.")
    ap.add_argument("--origen", default=os.path.join(RAIZ, "calc"),
                    help="carpeta con la calculadora (por defecto: calc/)")
    ap.add_argument("--dest", default=os.path.join(RAIZ, "server", "static"),
                    help="carpeta estatica del servidor (por defecto: server/static)")
    args = ap.parse_args(argv)

    faltan = [f for f in FICHEROS if not os.path.exists(os.path.join(args.origen, f))]
    if faltan:
        print("Faltan archivos en %s: %s" % (args.origen, ", ".join(faltan)), file=sys.stderr)
        return 1

    with open(os.path.join(args.origen, "calc.js"), encoding="utf-8") as fh:
        js = fh.read()
    avisos = comparar_con_la_fuente(js)
    print()

    destino = os.path.join(args.dest, "calc")
    os.makedirs(destino, exist_ok=True)
    for nombre in FICHEROS:
        shutil.copyfile(os.path.join(args.origen, nombre), os.path.join(destino, nombre))
        print("%-12s -> %s" % (nombre, os.path.relpath(os.path.join(destino, nombre), RAIZ)))
    print("La calculadora queda servida en /calc")

    if avisos:
        print("\nAvisos (calc.js y la fuente de verdad no coinciden):", file=sys.stderr)
        for a in avisos:
            print("  - " + a, file=sys.stderr)
        print("  Revisa si es a proposito antes de dar por buena la publicacion.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
