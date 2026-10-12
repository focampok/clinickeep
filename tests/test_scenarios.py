import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scenarios as sc  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def closed_form_hours_a(e, a, b, d):
    """Con T_RESERVA = d: C se abre al instante; B se abre cuando e_rest/(a+b) < d."""
    if e / (a + b) < d:
        return e / a
    t_shed = e / (a + b) - d
    return t_shed + d * (a + b) / a


@pytest.mark.parametrize("e,d", [(96, 12), (96, 8), (150, 12), (300, 12), (300, 20), (40, 10)])
def test_engine_matches_closed_form(e, d):
    r = sc.outage_clinickeep(e, 8.0, 4.0, 3.0, float(d))
    assert r["hours_a"] == pytest.approx(closed_form_hours_a(e, 8.0, 4.0, d), abs=0.05)


def test_baseline_formula():
    r = sc.outage_baseline(96.0, 8.0, 4.0, 3.0, 12.0)
    assert r["hours_a"] == pytest.approx(96.0 / 15.0)
    assert r["e_used_d"] == pytest.approx(96.0)          # 15 W x 12 h = 180 Wh > 96 Wh


def test_clinickeep_never_worse_than_baseline():
    for e in (24, 60, 96, 200, 300):
        for d in (8, 12, 20):
            ck = sc.outage_clinickeep(float(e), 8.0, 4.0, 3.0, float(d))
            base = sc.outage_baseline(float(e), 8.0, 4.0, 3.0, float(d))
            assert ck["hours_a"] >= base["hours_a"] - 1e-6
            assert ck["e_used_d"] <= base["e_used_d"] + 1e-6


def test_no_noncritical_load_means_no_gain():
    rows = sc.sweep_s2a(shares=[0.0, 0.4])
    for r in rows:
        if r["no_critica_pct"] == 0.0:
            assert r["mejora_pct"] == pytest.approx(0.0, abs=0.01)
        else:
            assert r["mejora_pct"] > 0.0


def test_gain_grows_with_noncritical_share():
    rows = [r for r in sc.sweep_s2a(energies=[96.0], shares=[0.1, 0.3, 0.5, 0.7])]
    gains = [r["mejora_pct"] for r in rows]
    assert gains == sorted(gains)


def test_s2b_state_ordering():
    rows = sc.sweep_s2b(energies=[24.0, 96.0, 300.0], durations=[8, 14, 20])
    for r in rows:
        assert r["cubre_sin"] <= r["cubre_con"]          # lo que cubre sin ClinicKeep, cubre con ClinicKeep
        assert r["estado"] in (0, 1, 2)
    # una bateria enorme cubre todo; una diminuta no cubre nada
    assert [r for r in rows if r["e_wh"] == 300.0 and r["d_h"] == 8][0]["estado"] == 2
    assert [r for r in rows if r["e_wh"] == 24.0 and r["d_h"] == 20][0]["estado"] == 0


def test_s3_more_charger_never_hurts():
    rows = sc.sweep_s3(durations=[12], chargers=[5.0, 20.0, 60.0])
    states = [r["estado"] for r in sorted(rows, key=lambda r: r["cargador_w"])]
    assert states == sorted(states)
    assert states[-1] == 2                               # 60 W recarga 96 Wh en 12 h de red


def test_s3_longer_outage_is_harder():
    rows = sc.sweep_s3(durations=[8, 20], chargers=[10.0])
    by_d = {r["d_h"]: r["estado"] for r in rows}
    assert by_d[8] >= by_d[20]


def test_csv_roundtrip(tmp_path):
    rows = sc.sweep_s3(durations=[10], chargers=[10.0, 20.0])
    p = tmp_path / "x.csv"
    sc.write_csv(str(p), rows)
    assert p.read_text().splitlines()[0].startswith("d_h,")
    assert len(p.read_text().splitlines()) == 3


# --- Perfiles (Fase 4b, punto 1) ---------------------------------------------
# El perfil por defecto tiene que dejar todo como estaba: los tests de arriba y
# el firmware no se enteran de que existen los perfiles.


def test_sin_perfil_todo_sigue_igual():
    assert sc.PERFIL_DEFECTO == "didactico"
    assert (sc.A_W, sc.B_W, sc.C_W) == (8.0, 4.0, 3.0)
    assert sc.B_SHARE == pytest.approx(4.0 / 7.0)
    filas = sc.sweep_s2a(shares=[0.0])
    assert min(r["e_wh"] for r in filas) == 24.0
    assert max(r["e_wh"] for r in filas) == 300.0
    # El perfil didactico tiene que seguir siendo el que se genera por defecto.
    assert sc.PERFILES[sc.PERFIL_DEFECTO] is not sc.PERFILES["pqs_ref"]
    assert sc._perfil(None).clave == "didactico"


def test_el_perfil_pqs_es_la_nevera_e003_066():
    p = sc.PERFILES["pqs_ref"]
    assert p.a_w == 35.0                        # 0.85 kWh/24 h = 35.4 W de media
    assert p.b_w == 25.0 and p.c_w == 20.0      # SUPUESTO por medir
    assert (p.e_min, p.e_max) == (200.0, 2000.0)
    assert "no representa una nevera PQS" in sc.PERFILES["didactico"].etiqueta


def test_los_barridos_aceptan_un_perfil():
    p = sc.PERFILES["pqs_ref"]
    filas = sc.sweep_s2a(shares=[0.4], perfil=p)
    assert {r["e_wh"] for r in filas} == set(p.energias())
    # B es la parte b_share de la carga no critica (25 de 25+20 W).
    assert filas[0]["b_w"] == pytest.approx(35.0 * 0.4 / 0.6 * p.b_share, abs=0.01)
    # A carga las filas con las constantes del perfil, no con las del modulo.
    assert sc.sweep_s2b(energies=[200.0], durations=[12], perfil=p)[0]["e_wh"] == 200.0
    assert sc.sweep_s3(perfil=p)[0]["e_wh"] == p.e_default_wh


def test_el_pie_dice_de_que_perfil_es():
    assert "didáctico" in sc.assumptions_text()
    assert "PQS" in sc.assumptions_text("pqs_ref")
    assert "0.85 kWh" in sc.assumptions_text(sc.PERFILES["pqs_ref"])


@pytest.mark.parametrize("perfil,carpeta", [("didactico", "out"), ("pqs_ref", "out/pqs_ref")])
def test_el_cli_escribe_cada_perfil_en_su_carpeta(tmp_path, perfil, carpeta):
    """Sin --out, el didactico va a out/ y el PQS a out/<perfil>/: no se pisan."""
    res = subprocess.run([sys.executable, os.path.join(RAIZ, "scenarios.py"),
                          "--perfil", perfil, "--no-plots"],
                         cwd=tmp_path, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    destino = tmp_path / carpeta
    for nombre in ("s2a_mejora.csv", "s2b_cobertura.csv", "s3_recarga.csv"):
        assert (destino / nombre).exists(), "falta %s" % nombre
    assert sc.PERFILES[perfil].etiqueta.startswith(sc.assumptions_text(perfil).split(".")[0])
