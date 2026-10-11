"""scenarios.py - Motor de escenarios de ClinicKeep (S2 y S3).

Reutiliza policy.py: es LA MISMA politica que corre en el ESP32 simulado.
Solo Python estandar (el dibujo de los mapas esta en plots.py).

TODOS los numeros de entrada son SUPUESTOS DE PARTIDA, no datos medidos.
Son analisis de sensibilidad, no prediccion de cortes.

Convenciones:
  * Un corte de d_h horas; la politica se configura con T_RESERVA_H = d_h
    ("horas de A que quiero garantizar" = duracion del corte esperada).
  * "Horas protegidas" = horas con energia en A + holdover termico de la caja.
  * Sin ClinicKeep, A, B y C comparten la bateria hasta agotarla.

Uso:  python3 scenarios.py --out out
"""
import argparse
import csv
import os

from config import Config
import policy

# --- Supuestos de partida (editar con datos citados antes del submit) ---
A_W, B_W, C_W = 8.0, 4.0, 3.0   # potencia por zona (W). SUPUESTO
B_SHARE = 4.0 / 7.0             # proporcion de la carga no critica que es B (resto es C)
T_AMB_C = 25.0                  # ambiente. SUPUESTO
ETA_CHARGE = 0.85               # eficiencia de carga. SUPUESTO
DT_H = 0.02                     # paso de simulacion (horas simuladas)


def make_cfg(e_wh, d_h):
    # T_DEBOUNCE_S = 0: el corte se confirma al instante (el antirrebote real es de ~2 s
    # y aqui solo distorsionaria la escala de horas)
    return Config(E_UTIL_WH=e_wh, T_DEBOUNCE_S=0.0, T_RESERVA_H=d_h, T_AMB_C=T_AMB_C)


def holdover():
    return policy.holdover_h(Config(T_AMB_C=T_AMB_C), T_AMB_C)


def outage_clinickeep(e_wh, a_w, b_w, c_w, d_h, dt_h=DT_H):
    """Corte con ClinicKeep, ejecutando policy.step.

    Devuelve hours_a (horas con energia en A si el corte no terminara),
    e_used_d (Wh sacados de la bateria durante el corte de d_h horas) y t_shed_b.
    """
    cfg = make_cfg(e_wh, d_h)
    st = policy.new_state()
    # t = 0: cae la red. Con dt = 0 se confirma el corte y se abre C antes de contar energia;
    # la potencia ya excluye a C porque se abre en ese mismo instante.
    policy.step(st, cfg, False, a_w + b_w, a_w, 0.0)
    k = dt_h * 3600.0          # dt_real = 1 s  =>  cada paso equivale a dt_h horas simuladas
    t = 0.0
    e_used_d = None
    died = False
    t_prev = 0.0
    e_prev = 0.0
    while st.b_on:
        total = a_w + b_w
        e_prev = st.e_used_wh
        t_prev = t
        out = policy.step(st, cfg, False, total, a_w, 1.0, k=k)
        t = t_prev + dt_h
        if e_used_d is None and t >= d_h:
            e_used_d = e_prev + (st.e_used_wh - e_prev) * (d_h - t_prev) / dt_h
        if out["e_rest_wh"] <= 0.0 and st.b_on:
            died = True
            break
    if died:
        # la bateria se agoto con B encendida: el potencia fue constante dentro del paso
        hours_a = t_prev + (e_wh - e_prev) / (a_w + b_w)
        t_shed = None
        if e_used_d is None:
            e_used_d = e_wh
    else:
        t_shed = t
        rest = e_wh - st.e_used_wh
        if rest < 0.0:
            rest = 0.0
        hours_a = t + rest / a_w
        if e_used_d is None:
            e_used_d = st.e_used_wh + a_w * (d_h - t)
    if e_used_d > e_wh:
        e_used_d = e_wh
    return {"hours_a": hours_a, "e_used_d": e_used_d, "t_shed_b": t_shed}


def outage_baseline(e_wh, a_w, b_w, c_w, d_h):
    """Sin ClinicKeep: A, B y C comparten la bateria hasta agotarla."""
    p = a_w + b_w + c_w
    used = p * d_h
    if used > e_wh:
        used = e_wh
    return {"hours_a": e_wh / p, "e_used_d": used}


def _loads_from_share(a_w, share):
    """share = fraccion de la carga TOTAL que es no critica (B + C)."""
    n = a_w * share / (1.0 - share)
    return n * B_SHARE, n * (1.0 - B_SHARE)


def sweep_s2a(d_h=12.0, energies=None, shares=None):
    """Mejora (%) en horas protegidas segun bateria y proporcion de carga no critica."""
    if energies is None:
        energies = [24.0 + 12.0 * i for i in range(24)]          # 24 ... 300 Wh
    if shares is None:
        shares = [0.05 * i for i in range(0, 17)]                # 0 ... 80 %
    hold = holdover()
    rows = []
    for e in energies:
        for f in shares:
            b, c = _loads_from_share(A_W, f)
            ck = outage_clinickeep(e, A_W, b, c, d_h)
            base = outage_baseline(e, A_W, b, c, d_h)
            p_ck = ck["hours_a"] + hold
            p_base = base["hours_a"] + hold
            rows.append({
                "d_h": d_h, "e_wh": round(e, 1), "no_critica_pct": round(f * 100, 1),
                "b_w": round(b, 2), "c_w": round(c, 2),
                "prot_sin_h": round(p_base, 3), "prot_con_h": round(p_ck, 3),
                "mejora_pct": round((p_ck / p_base - 1.0) * 100.0, 2),
            })
    return rows


def sweep_s2b(energies=None, durations=None, b_w=B_W, c_w=C_W):
    """Cobertura de un corte de d_h horas: ninguno / solo con ClinicKeep / ambos."""
    if energies is None:
        energies = [24.0 + 12.0 * i for i in range(24)]
    if durations is None:
        durations = list(range(8, 21))                           # 8 ... 20 h
    hold = holdover()
    rows = []
    for e in energies:
        for d in durations:
            ck = outage_clinickeep(e, A_W, b_w, c_w, float(d))
            base = outage_baseline(e, A_W, b_w, c_w, float(d))
            cov_ck = (ck["hours_a"] + hold) >= d
            cov_base = (base["hours_a"] + hold) >= d
            rows.append({
                "d_h": d, "e_wh": round(e, 1),
                "prot_sin_h": round(base["hours_a"] + hold, 3),
                "prot_con_h": round(ck["hours_a"] + hold, 3),
                "cubre_sin": int(cov_base), "cubre_con": int(cov_ck),
                "estado": 2 if cov_base else (1 if cov_ck else 0),
            })
    return rows


def sweep_s3(e_wh=96.0, durations=None, chargers=None, b_w=B_W, c_w=C_W):
    """Chequeo de recarga: un corte de d_h al dia, red el resto (24 - d_h)."""
    if durations is None:
        durations = list(range(8, 21))
    if chargers is None:
        chargers = [5.0 * i for i in range(1, 13)]               # 5 ... 60 W
    rows = []
    for d in durations:
        ck = outage_clinickeep(e_wh, A_W, b_w, c_w, float(d))
        base = outage_baseline(e_wh, A_W, b_w, c_w, float(d))
        t_red = 24.0 - d
        for p in chargers:
            ok_ck = ck["e_used_d"] / ETA_CHARGE <= p * t_red
            ok_base = base["e_used_d"] / ETA_CHARGE <= p * t_red
            rows.append({
                "d_h": d, "t_red_h": t_red, "cargador_w": p, "e_wh": e_wh,
                "e_usada_sin_wh": round(base["e_used_d"], 2),
                "e_usada_con_wh": round(ck["e_used_d"], 2),
                "recarga_sin": int(ok_base), "recarga_con": int(ok_ck),
                "estado": 2 if ok_base else (1 if ok_ck else 0),
            })
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def assumptions_text():
    return ("Supuestos (NO medidos): A=%.0f W, B+C repartidos %.0f/%.0f; ambiente %.0f C; "
            "holdover %.2f h (tau=%.1f h, T_HI=%.1f, T_LIM=%.1f); eficiencia de carga %.2f; "
            "T_RESERVA = duracion del corte" % (
                A_W, B_SHARE * 100, (1 - B_SHARE) * 100, T_AMB_C, holdover(),
                Config().TAU_H, Config().T_HI_C, Config().T_LIM_C, ETA_CHARGE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    s2a = sweep_s2a()
    s2b = sweep_s2b()
    s3 = sweep_s3()
    write_csv(os.path.join(args.out, "s2a_mejora.csv"), s2a)
    write_csv(os.path.join(args.out, "s2b_cobertura.csv"), s2b)
    write_csv(os.path.join(args.out, "s3_recarga.csv"), s3)
    print("CSV escritos en", args.out)
    print(assumptions_text())

    if not args.no_plots:
        try:
            import plots
        except ImportError:
            print("matplotlib no esta instalado: se omiten los mapas (pip install matplotlib)")
            return
        plots.make_all(args.out, s2a, s2b, s3, assumptions_text())
        print("Mapas escritos en", args.out)


if __name__ == "__main__":
    main()
