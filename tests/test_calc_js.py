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


@pytest.mark.parametrize("perfil", ["didactico", "pqs_ref"])
def test_calc_js_reproduce_los_csv(tmp_path, perfil):
    """La misma comprobacion para los dos perfiles: cada uno con sus defectos."""
    out = str(tmp_path / perfil)

    # 1. La fuente de verdad: los escenarios, recien generados.
    gen = subprocess.run(
        [sys.executable, os.path.join(RAIZ, "scenarios.py"),
         "--perfil", perfil, "--out", out, "--no-plots"],
        cwd=RAIZ, capture_output=True, text=True)
    assert gen.returncode == 0, "scenarios.py fallo:\n" + gen.stdout + gen.stderr

    # 2. La calculadora, contra esos CSV y con los defectos del perfil.
    prueba = subprocess.run(
        [NODE, os.path.join(RAIZ, "calc", "test_calc.mjs"), out, perfil],
        cwd=RAIZ, capture_output=True, text=True)
    assert prueba.returncode == 0, (
        "calc.js no reproduce los escenarios (%s):\n%s%s" % (perfil, prueba.stdout, prueba.stderr))

    # 3. Que no se haya saltado ninguna fila por el camino.
    encontrado = re.search(r"(\d+) filas comprobadas", prueba.stdout)
    assert encontrado, "el test de Node no dijo cuantas filas comprobo:\n" + prueba.stdout
    assert int(encontrado.group(1)) == _filas(out)
    assert "OK:" in prueba.stdout


# --- Honestidad de los numeros (punto 5) -------------------------------------

ETIQUETAS_OK = ("SUPUESTO", "SUPUESTO — por citar", "FUENTE")

# Las UNICAS URLs que puede haber en calc.js: las tres fuentes que se
# verificaron a mano (punto 2 de la Fase 4b), listadas aqui una a una.
URLS_PERMITIDAS = (
    "https://extranet.who.int/prequal/sites/default/files/immunization_devices/pdf/e003/E003-066.pdf",
    "https://extranet.who.int/prequal/key-resources/documents/pqs-performance-specification-e003rf021-refrigerator-or-combined",
    "https://www.indexmundi.com/facts/indicators/IC.ELC.OUTG/rankings/central-america",
)


def _urls(texto):
    return re.findall(r"https?://[^\s\"'<>]+", texto or "")


def _campos_de_perfil(perfiles):
    """Los campos que un perfil cambia: {clave: metadata}."""
    return {p["id"]: (p.get("campos") or {}) for p in perfiles.values()}


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
        # Una URL escrita a mano no es una fuente: se prefiere declarar el
        # supuesto. Si hay enlace, va en `fuente` y es una de las tres de arriba.
        for campo in ("etiqueta", "origen", "nota"):
            assert "http" not in (meta[campo] or ""), "%s: %s parece una URL" % (clave, campo)
        if meta.get("fuente"):
            assert meta["fuente"]["url"] in URLS_PERMITIDAS, (
                "%s: enlace no verificado %s" % (clave, meta["fuente"]["url"]))

    # Lo mismo para lo que cambia cada perfil (el a_w del PQS es FUENTE).
    for perfil, campos in _campos_de_perfil(_export("PERFILES")).items():
        for clave, meta in campos.items():
            assert clave in defaults, "%s: el perfil cambia %s, que no existe" % (perfil, clave)
            assert meta.get("etiqueta", "SUPUESTO") in ETIQUETAS_OK, (
                "%s/%s: etiqueta desconocida %r" % (perfil, clave, meta.get("etiqueta")))
            if meta.get("fuente"):
                assert meta["fuente"]["url"] in URLS_PERMITIDAS


def test_solo_se_citan_las_tres_fuentes_verificadas():
    """La regla global: en calc.js solo hay estas tres URLs, y estan en FUENTES."""
    fuentes = _export("FUENTES")
    assert tuple(f["url"] for f in fuentes.values()) == URLS_PERMITIDAS
    for nombre, f in fuentes.items():
        assert f["texto"], "%s: una fuente sin decir que dice no sirve de nada" % nombre

    sueltas = []
    for meta in _export("DEFAULTS").values():
        for campo in ("nombre", "unidad", "etiqueta", "origen", "nota"):
            sueltas += _urls(str(meta.get(campo) or ""))
    perfiles = _export("PERFILES")
    for p in perfiles.values():
        sueltas += _urls(p.get("etiqueta")) + _urls(p.get("nombre"))
        for meta in (p.get("campos") or {}).values():
            for campo in ("nombre", "unidad", "etiqueta", "origen", "nota"):
                sueltas += _urls(str(meta.get(campo) or ""))
    assert sueltas == [], "hay URLs fuera de FUENTES: %s" % sueltas


def test_las_etiquetas_fuente_llevan_enlace():
    campos = dict(_export("DEFAULTS"))
    for perfil, por_clave in _campos_de_perfil(_export("PERFILES")).items():
        for clave, meta in por_clave.items():
            campos["%s/%s" % (perfil, clave)] = meta
    etiquetas = {k: v.get("etiqueta") for k, v in campos.items()}
    assert "FUENTE" in etiquetas.values(), "ya no queda ninguna etiqueta FUENTE"
    for clave, meta in campos.items():
        if meta.get("etiqueta") == "FUENTE":
            assert meta.get("fuente"), "%s dice FUENTE y no trae enlace" % clave


def test_el_perfil_debe_coincidir_con_scenarios_py():
    """Los dos perfiles de calc.js son los de scenarios.py, con los mismos
    numeros: si uno se mueve y el otro no, esta prueba lo dice."""
    sys.path.insert(0, RAIZ)
    import scenarios as sc  # noqa: E402

    perfiles_js = _export("PERFILES")
    assert perfiles_js["didactico"]["campos"] == {}      # el didactico no cambia nada
    for clave, p in sc.PERFILES.items():
        assert clave in perfiles_js, "calc.js no tiene el perfil %s" % clave
        js = perfiles_js[clave]
        assert js["etiqueta"] == p.etiqueta, "%s: la etiqueta visible no coincide" % clave
        assert js["rango_bateria"] == [p.e_min, p.e_max], "%s: cambia el rango de bateria" % clave
        for campo, esperado in (("a_w", p.a_w), ("b_w", p.b_w), ("c_w", p.c_w)):
            if campo in js["campos"]:
                assert js["campos"][campo]["valor"] == esperado, (
                    "%s/%s: calc.js dice %s y scenarios.py %s"
                    % (clave, campo, js["campos"][campo]["valor"], esperado))


def test_el_origen_apunta_a_un_archivo_del_repo():
    campos = dict(_export("DEFAULTS"))
    for por_clave in _campos_de_perfil(_export("PERFILES")).values():
        campos.update(por_clave)
    for clave, meta in campos.items():
        if meta.get("origen"):
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
