"""docs/PINOUT.md y docs/SCHEMA.md deben estar al dia con wokwi/diagram.json.

Se re-ejecuta el generador (tools/gen_pinout.py) y se compara con lo que hay en el
repo: si alguien mueve un cable y no regenera, la prueba falla.
"""
import importlib.util
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _load_gen():
    path = os.path.join(ROOT, "tools", "gen_pinout.py")
    spec = importlib.util.spec_from_file_location("gen_pinout", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("attr", ["OUT", "SCHEMA"])
def test_docs_match_diagram(attr):
    gen = _load_gen()
    diagram = gen.load_diagram()
    rows, extra = gen.build_rows(diagram)
    if attr == "OUT":
        expected = gen.render(rows, extra)
    else:
        expected = gen.render_schema(diagram)
    with open(getattr(gen, attr), encoding="utf-8") as fh:
        actual = fh.read()
    assert actual == expected, (
        "%s esta desactualizado: corre python3 tools/gen_pinout.py" % getattr(gen, attr)
    )


def test_no_unlisted_gpio():
    gen = _load_gen()
    _, extra = gen.build_rows(gen.load_diagram())
    assert not extra, "GPIO cableados fuera de SIGNALS en tools/gen_pinout.py: %s" % extra
