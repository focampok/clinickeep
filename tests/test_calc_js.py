"""test_calc_js.py - Prueba de pytest que enlaza la calculadora con la fuente
de verdad (Fase 4, punto 4).

No reimplementa ninguna formula en Python: regenera los CSV con `scenarios.py`
(el mismo motor que valida tests/test_scenarios.py) y le pide a Node que
compare fila a fila contra `calc/calc.js`.

Node no es dependencia del proyecto: si no esta instalado, esta prueba se omite
(el resto de la suite sigue corriendo sin el).
"""

import os
import re
import shutil
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
