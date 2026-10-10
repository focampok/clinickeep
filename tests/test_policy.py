import math
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config  # noqa: E402
import policy  # noqa: E402

P_A, P_B, P_C = 8.0, 4.0, 3.0


def loads(st):
    """Potencia total y de A segun los reles actuales (maqueta de 3 zonas)."""
    total = P_A + (P_B if st.b_on else 0.0) + (P_C if st.c_on else 0.0)
    return total, P_A


def run(st, cfg, grid, steps, k=1.0, dt=1.0, **kw):
    out = None
    for _ in range(steps):
        total, pa = loads(st)
        out = policy.step(st, cfg, grid, total, pa, dt, k=k, **kw)
    return out


def test_normal_all_on():
    cfg, st = Config(), policy.new_state()
    out = run(st, cfg, True, 10)
    assert out["mode"] == policy.NORMAL
    assert out["relay_a"] and out["relay_b"] and out["relay_c"]
    assert not out["alarm"]


def test_grid_down_needs_debounce():
    cfg, st = Config(), policy.new_state()
    out = run(st, cfg, False, 1)
    assert out["mode"] == policy.NORMAL and out["relay_c"]
    out = run(st, cfg, False, 2)
    assert out["mode"] == policy.CORTE
    assert not out["relay_c"] and out["relay_b"] and out["relay_a"]


def test_shed_b_by_autonomy_and_a_stays():
    cfg, st = Config(), policy.new_state()
    run(st, cfg, False, 3)
    out = None
    for _ in range(60):
        out = run(st, cfg, False, 1, k=600)
        if out["mode"] == policy.AHORRO:
            break
    assert out["mode"] == policy.AHORRO
    assert not out["relay_b"] and not out["relay_c"] and out["relay_a"]


def test_shedding_is_monotonic_during_outage():
    cfg, st = Config(), policy.new_state()
    run(st, cfg, False, 3)
    for _ in range(60):
        out = run(st, cfg, False, 1, k=600)
        if out["mode"] == policy.AHORRO:
            break
    # aunque la carga baje, B no se reabre mientras no haya red
    out = policy.step(st, cfg, False, 1.0, 1.0, 1.0, k=1.0)
    assert not out["relay_b"]


def test_critical_alarm_and_a_never_cut():
    cfg, st = Config(), policy.new_state()
    run(st, cfg, False, 3)
    out = None
    for _ in range(400):
        out = run(st, cfg, False, 1, k=600)
        if out["mode"] == policy.CRITICO:
            break
    assert out["mode"] == policy.CRITICO
    assert out["alarm"]
    assert out["safe_h"] < cfg.T_ACT_MIN_H
    assert out["relay_a"] and not out["relay_b"] and not out["relay_c"]


def test_staggered_restoration():
    cfg, st = Config(), policy.new_state()
    run(st, cfg, False, 3)
    for _ in range(60):
        out = run(st, cfg, False, 1, k=600)
        if out["mode"] == policy.AHORRO:
            break
    out = run(st, cfg, True, 4)
    assert not out["grid_ok"]                      # aun sin confirmar (T_RESTORE_S = 5)
    out = run(st, cfg, True, 1)
    assert out["mode"] == policy.RESTAURACION
    assert out["relay_b"] and not out["relay_c"]   # primero B
    out = run(st, cfg, True, 3)
    assert out["mode"] == policy.NORMAL
    assert out["relay_c"]                          # despues C
    assert out["soc"] == pytest.approx(1.0)


def test_grid_flicker_does_not_restore():
    cfg, st = Config(), policy.new_state()
    run(st, cfg, False, 3)
    run(st, cfg, True, 3)      # menos que T_RESTORE_S
    out = run(st, cfg, False, 2)
    assert out["mode"] == policy.CORTE and not out["grid_ok"]


def test_power_sensor_fault_during_outage_is_conservative():
    cfg, st = Config(), policy.new_state()
    run(st, cfg, False, 3)
    out = None
    for _ in range(3):
        out = policy.step(st, cfg, False, 0.0, 0.0, 1.0, power_ok=False)
    assert out["mode"] == policy.FALLO_SENSOR
    assert not out["relay_b"] and not out["relay_c"] and out["relay_a"]
    assert out["alarm"]


def test_power_sensor_fault_with_grid_only_alarms():
    cfg, st = Config(), policy.new_state()
    out = None
    for _ in range(3):
        out = policy.step(st, cfg, True, 0.0, 0.0, 1.0, power_ok=False)
    assert out["mode"] == policy.NORMAL
    assert out["relay_b"] and out["relay_c"]
    assert out["alarm"]


def test_temp_sensor_fault_only_disables_holdover():
    cfg, st = Config(), policy.new_state()
    run(st, cfg, False, 3)
    total, pa = loads(st)
    out = policy.step(st, cfg, False, total, pa, 1.0, temp_ok=False)
    assert out["holdover_h"] is None
    assert out["safe_h"] == pytest.approx(out["aut_a_h"])
    assert out["relay_a"]


def test_holdover_formula():
    cfg = Config(TAU_H=4.0, T_HI_C=5.0, T_LIM_C=7.5)
    expected = 4.0 * math.log(20.0 / 17.5)
    assert policy.holdover_h(cfg, 25.0) == pytest.approx(expected, abs=1e-6)
    assert policy.holdover_h(cfg, 25.0) == pytest.approx(0.534, abs=1e-3)


def test_holdover_unbounded_when_ambient_is_cool():
    cfg = Config()
    assert policy.holdover_h(cfg, 6.0) == policy.MAX_H


def test_sim_clock_scales_energy():
    cfg, st = Config(), policy.new_state()
    run(st, cfg, False, 2)                       # confirma el corte (k = 1)
    e0 = st.e_used_wh
    total, pa = loads(st)
    policy.step(st, cfg, False, total, pa, 1.0, k=3600.0)
    assert st.e_used_wh - e0 == pytest.approx(total, abs=0.05)   # 1 s x 3600 = 1 h


def test_relay_a_always_on_random():
    rnd = random.Random(1234)
    cfg, st = Config(), policy.new_state()
    for _ in range(5000):
        grid = rnd.random() > 0.3
        out = policy.step(st, cfg, grid,
                          rnd.uniform(0, 30), rnd.uniform(0, 12), rnd.uniform(0.1, 5),
                          k=rnd.choice([1, 60, 600]),
                          power_ok=rnd.random() > 0.1, temp_ok=rnd.random() > 0.1)
        assert out["relay_a"] is True
