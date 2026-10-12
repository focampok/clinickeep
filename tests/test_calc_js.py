"""test_calc_js.py - Pruebas de pytest sobre la calculadora (Fase 4, puntos 4 y 5).

No reimplementa ninguna formula en Python: lee `calc/calc.js` a traves de Node y
compara con la fuente de verdad (los CSV que regenera `scenarios.py`, el mismo
motor que valida tests/test_scenarios.py).

Node no es dependencia del proyecto: si no esta instalado, estas pruebas se
omiten (el resto de la suite sigue corriendo sin el).
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALC = os.path.join(RAIZ, "calc")
DOC = os.path.join(RAIZ, "docs", "FUENTES_PENDIENTES.md")
NODE = shutil.which("node")
CSV = ("s2a_mejora.csv", "s2b_cobertura.csv", "s3_recarga.csv")

pytestmark = pytest.mark.skipif(
    NODE is None, reason="hace falta node para ejecutar calc/test_calc.mjs")


def _filas(carpeta):
    """Filas de datos de los tres CSV (sin contar las cabeceras)."""
    total = 0
    for nombre in CSV:
        with open(os.path.join(carpeta, nombre), encoding="utf-8") as fh:
            total += sum(1 for _ in fh) - 1
    return total


def test_calc_js_reproduce_los_csv(tmp_path):
    out = str(tmp_path / "out")

    # 1. La fuente de verdad: los escenarios, recien generados.
    gen = subprocess.run(
        [sys.executable, os.path.join(RAIZ, "scenarios.py"), "--out", out, "--no-plots"],
        cwd=RAIZ, capture_output=True, text=True)
    assert gen.returncode == 0, "scenarios.py fallo:\n" + gen.stdout + gen.stderr

    # 2. La calculadora, contra esos CSV.
    prueba = subprocess.run(
        [NODE, os.path.join(RAIZ, "calc", "test_calc.mjs"), out],
        cwd=RAIZ, capture_output=True, text=True)
    assert prueba.returncode == 0, (
        "calc.js no reproduce los escenarios:\n" + prueba.stdout + prueba.stderr)

    # 3. Que no se haya saltado ninguna fila por el camino.
    encontrado = re.search(r"(\d+) filas comprobadas", prueba.stdout)
    assert encontrado, "el test de Node no dijo cuantas filas comprobo:\n" + prueba.stdout
    assert int(encontrado.group(1)) == _filas(out)
    assert "OK:" in prueba.stdout


# --- Honestidad de los numeros (punto 5) -------------------------------------

ETIQUETAS_OK = ("SUPUESTO", "SUPUESTO — por citar")


def _export(nombre):
    """Lee un export de calc/calc.js, tal cual, a traves de Node."""
    url = pathlib.Path(CALC, "calc.js").as_uri()
    codigo = ("import(%s).then(m => process.stdout.write(JSON.stringify(m.%s)))"
              % (json.dumps(url), nombre))
    res = subprocess.run([NODE, "--input-type=module", "-e", codigo],
                         cwd=RAIZ, capture_output=True, text=True)
    assert res.returncode == 0, "no se pudo leer %s de calc.js:\n%s" % (nombre, res.stderr)
    return json.loads(res.stdout)


def test_cada_defecto_lleva_su_etiqueta():
    """Ni un valor por defecto sin decir de donde sale."""
    defaults = _export("DEFAULTS")
    assert defaults, "calc.js no declara DEFAULTS"
    for clave, meta in defaults.items():
        for campo in ("nombre", "unidad", "etiqueta", "nota", "valor"):
            assert meta.get(campo) not in (None, ""), "%s no tiene %s" % (clave, campo)
        assert meta["etiqueta"] in ETIQUETAS_OK, (
            "%s: etiqueta desconocida %r" % (clave, meta["etiqueta"]))
        # Una URL escrita a mano no es una fuente: se prefiere declarar el supuesto.
        for campo in ("etiqueta", "origen", "nota"):
            assert "http" not in (meta[campo] or ""), "%s: %s parece una URL" % (clave, campo)


def test_el_origen_apunta_a_un_archivo_del_repo():
    for clave, meta in _export("DEFAULTS").items():
        if meta["origen"]:
            archivo = meta["origen"].split(":")[0].strip()
            assert os.path.exists(os.path.join(RAIZ, archivo)), (
                "%s dice venir de %s, que no existe" % (clave, archivo))


def test_los_supuestos_por_citar_estan_listados():
    """Todo defecto esta en docs/FUENTES_PENDIENTES.md, y los 'por citar' como tales."""
    with open(DOC, encoding="utf-8") as fh:
        lineas = fh.read().splitlines()
    for clave, meta in _export("DEFAULTS").items():
        marca = "`%s`" % clave
        fila = next((l for l in lineas if marca in l), None)
        assert fila is not None, "%s no aparece en docs/FUENTES_PENDIENTES.md" % clave
        if meta["etiqueta"] == "SUPUESTO — por citar":
            assert "por citar" in fila, (
                "%s esta 'por citar' y en el documento no se ve" % clave)


def test_el_pie_es_el_que_dice_que_es_esto():
    pie = _export("PIE")
    assert "no es predicción de cortes ni datos medidos" in pie
    assert "sensibilidad" in pie
