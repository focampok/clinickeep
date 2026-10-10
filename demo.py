"""demo.py - Corre un corte simulado y compara CON vs SIN ClinicKeep.

Uso:  python3 demo.py            (corte con reloj SIM x600)
      python3 demo.py --k 1200   (otro factor)

Es el embrion del motor de escenarios: la misma politica que ira en el ESP32.
"""
import argparse

from config import Config
import policy

P_A, P_B, P_C = 8.0, 4.0, 3.0   # W por zona (SUPUESTOS)


def loads(st):
    total = P_A + (P_B if st.b_on else 0.0) + (P_C if st.c_on else 0.0)
    return total, P_A


def with_clinickeep(cfg, k, verbose=True):
    st = policy.new_state()
    t_cut_s = None          # reloj simulado desde que cae la red
    a_dead_h = None
    sim_s = 0.0
    rows = []
    for i in range(100000):
        grid = i < 5   # red presente 5 s reales y luego se corta
        total, pa = loads(st)
        out = policy.step(st, cfg, grid, total, pa, 1.0, k=k)
        if not out["grid_ok"] and t_cut_s is None:
            t_cut_s = 0.0
        if t_cut_s is not None:
            t_cut_s += k
            if verbose and (out["events"] or i % 10 == 0):
                rows.append((t_cut_s / 3600.0, out))
            if out["e_rest_wh"] <= 0.0:
                a_dead_h = t_cut_s / 3600.0
                break
    return a_dead_h, rows


def without_clinickeep(cfg):
    """Sin priorizacion: A, B y C comparten la bateria hasta agotarla."""
    return cfg.E_UTIL_WH / (P_A + P_B + P_C)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=float, default=600.0)
    args = ap.parse_args()

    cfg = Config()
    a_dead_h, rows = with_clinickeep(cfg, args.k)

    print("t_sim(h)  modo          B  C  SoC   aut_A(h)  holdover(h)  seguro(h)  eventos")
    for t_h, o in rows:
        print("%7.2f   %-12s  %d  %d  %3.0f%%  %8.2f  %11.2f  %9.2f  %s" % (
            t_h, o["mode"], o["relay_b"], o["relay_c"], o["soc"] * 100,
            o["aut_a_h"], o["holdover_h"], o["safe_h"], ",".join(o["events"])))

    hold = policy.holdover_h(cfg, cfg.T_AMB_C)
    base_h = without_clinickeep(cfg)
    base_total = base_h + hold
    ck_total = a_dead_h + hold
    print()
    print("Bateria util: %.0f Wh | cargas: A=%.0f W, B=%.0f W, C=%.0f W" % (cfg.E_UTIL_WH, P_A, P_B, P_C))
    print("SIN ClinicKeep: A sin energia a las %.1f h; con holdover, %.1f h protegidas" % (base_h, base_total))
    print("CON ClinicKeep: A sin energia a las %.1f h; con holdover, %.1f h protegidas" % (a_dead_h, ck_total))
    print("Mejora: %.0f %%  (depende de cuanta carga no critica exista)" % ((ck_total / base_total - 1) * 100))


if __name__ == "__main__":
    main()
