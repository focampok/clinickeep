"""Las copias de policy.py y config.py dentro de wokwi/ deben ser identicas a las de la raiz.

Si wokwi/ no existe (por ejemplo, en un checkout parcial), la prueba se omite.
"""
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


@pytest.mark.parametrize("name", ["policy.py", "config.py"])
def test_wokwi_copy_is_identical(name):
    wokwi = os.path.join(ROOT, "wokwi", name)
    if not os.path.exists(wokwi):
        pytest.skip("no existe wokwi/%s" % name)
    with open(os.path.join(ROOT, name), "rb") as a, open(wokwi, "rb") as b:
        assert a.read() == b.read(), "wokwi/%s difiere de la raiz: copia la raiz (cp %s wokwi/)" % (name, name)
