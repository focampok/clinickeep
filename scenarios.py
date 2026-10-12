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
      python3 scenarios.py --perfil pqs_ref        # salidas en out/pqs_ref/
"""
import argparse
import csv
import os

from config import Config
import policy


# --- Perfiles de supuestos de partida ---------------------------------------
#
# Un perfil es un juego completo de numeros de partida. Hay dos:
#
#   didactico  el de siempre: A/B/C = 8/4/3 W y baterias de 24 a 300 Wh. Es la
#              maqueta de demo, no una nevera de ningun catalogo.
#   pqs_ref    una nevera PQS de un solo modelo AC, la E003-066 (0.85 kWh/24 h
#              continuos = 35 W de media, con fuente) y baterias de 200 a
#              2000 Wh. B y C son SUPUESTOS por medir: no hay medida del sitio.
#
# Siguen siendo supuestos de partida: esto es analisis de sensibilidad, no
# prediccion de cortes.


class Perfil:
    """Juego de supuestos de partida para los barridos S2 y S3."""

    def __init__(self, clave, nombre, etiqueta, a_w, b_w, c_w, e_min, e_max, e_paso,
                 e_default_wh, d_h=12.0):
        self.clave = clave
        self.nombre = nombre           # corto: cabe en el subtitulo de un mapa
        self.etiqueta = etiqueta       # largo: es el que se enseña entero
        self.a_w, self.b_w, self.c_w = a_w, b_w, c_w
        self.e_min, self.e_max, self.e_paso = e_min, e_max, e_paso
        self.e_default_wh = e_default_wh   # bateria del perfil para el barrido S3
        self.d_h = d_h
        # proporcion de la carga no critica que es B (el resto es C)
        self.b_share = b_w / (b_w + c_w)

    def energias(self):
        """Baterias del barrido, de e_min a e_max en pasos de e_paso."""
        pasos = int(round((self.e_max - self.e_min) / self.e_paso)) + 1
        return [self.e_min + self.e_paso * i for i in range(pasos)]


PERFIL_DEFECTO = "didactico"

PERFILES = {
    # La maqueta de siempre. Es el perfil por defecto: los tests y el firmware
    # siguen viendo exactamente los numeros de antes.
    "didactico": Perfil(
        "didactico",
        nombre="Didáctico (demo)",
        etiqueta="perfil didáctico de demo, no representa una nevera PQS",
        a_w=8.0, b_w=4.0, c_w=3.0,
        e_min=24.0, e_max=300.0, e_paso=12.0,
        e_default_wh=Config.E_UTIL_WH),
    # Nevera PQS de referencia: un solo modelo AC, 0.85 kWh/24 h continuos.
    # 0.85 kWh/24 h = 35.4 W de media; se usa 35 W (redondeo a favor).
    "pqs_ref": Perfil(
        "pqs_ref",
        nombre="PQS de referencia",
        etiqueta="perfil PQS de referencia (E003-066, 0.85 kWh/24 h); B y C por medir",
        a_w=35.0, b_w=25.0, c_w=20.0,
        e_min=200.0, e_max=2000.0, e_paso=100.0,
        e_default_wh=200.0),
}


def _perfil(perfil):
    """Acepta una clave de PERFILES, un Perfil o None (el perfil por defecto)."""
    if perfil is None:
        return PERFILES[PERFIL_DEFECTO]
    if isinstance(perfil, str):
        return PERFILES[perfil]
    return perfil


# El perfil didactico, con los nombres de siempre: son los que usan los tests.
A_W = PERFILES[PERFIL_DEFECTO].a_w    # potencia por zona (W). SUPUESTO
B_W = PERFILES[PERFIL_DEFECTO].b_w
C_W = PERFILES[PERFIL_DEFECTO].c_w
B_SHARE = PERFILES[PERFIL_DEFECTO].b_share

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


def _loads_from_share(a_w, share, b_share=B_SHARE):
    """share = fraccion de la carga TOTAL que es no critica (B + C)."""
    n = a_w * share / (1.0 - share)
    return n * b_share, n * (1.0 - b_share)


def sweep_s2a(d_h=None, energies=None, shares=None, perfil=None):
    """Mejora (%) en horas protegidas segun bateria y proporcion de carga no critica."""
    p = _perfil(perfil)
    if d_h is None:
        d_h = p.d_h
    if energies is None:
        energies = p.energias()
    if shares is None:
        shares = [0.05 * i for i in range(0, 17)]                # 0 ... 80 %
    hold = holdover()
    rows = []
    for e in energies:
        for f in shares:
            b, c = _loads_from_share(p.a_w, f, p.b_share)
            ck = outage_clinickeep(e, p.a_w, b, c, d_h)
            base = outage_baseline(e, p.a_w, b, c, d_h)
            p_ck = ck["hours_a"] + hold
            p_base = base["hours_a"] + hold
            rows.append({
                "d_h": d_h, "e_wh": round(e, 1), "no_critica_pct": round(f * 100, 1),
                "b_w": round(b, 2), "c_w": round(c, 2),
                "prot_sin_h": round(p_base, 3), "prot_con_h": round(p_ck, 3),
                "mejora_pct": round((p_ck / p_base - 1.0) * 100.0, 2),
            })
    return rows


def sweep_s2b(energies=None, durations=None, b_w=None, c_w=None, perfil=None):
    """Cobertura de un corte de d_h horas: ninguno / solo con ClinicKeep / ambos."""
    p = _perfil(perfil)
    if energies is None:
        energies = p.energias()
    if durations is None:
        durations = list(range(8, 21))                           # 8 ... 20 h
    if b_w is None:
        b_w = p.b_w
    if c_w is None:
        c_w = p.c_w
    hold = holdover()
    rows = []
    for e in energies:
        for d in durations:
            ck = outage_clinickeep(e, p.a_w, b_w, c_w, float(d))
            base = outage_baseline(e, p.a_w, b_w, c_w, float(d))
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


def sweep_s3(e_wh=None, durations=None, chargers=None, b_w=None, c_w=None, perfil=None):
    """Chequeo de recarga: un corte de d_h al dia, red el resto (24 - d_h)."""
    pf = _perfil(perfil)          # (no se llama `p`: `p` es el cargador del bucle)
    if e_wh is None:
        e_wh = pf.e_default_wh
    if durations is None:
        durations = list(range(8, 21))
    if chargers is None:
        chargers = [5.0 * i for i in range(1, 13)]               # 5 ... 60 W
    if b_w is None:
        b_w = pf.b_w
    if c_w is None:
        c_w = pf.c_w
    rows = []
    for d in durations:
        ck = outage_clinickeep(e_wh, pf.a_w, b_w, c_w, float(d))
        base = outage_baseline(e_wh, pf.a_w, b_w, c_w, float(d))
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


def assumptions_text(perfil=None):
    """El pie "Supuestos" de los mapas. Empieza diciendo de que perfil es."""
    p = _perfil(perfil)
    return ("%s. Supuestos (NO medidos): A=%.0f W, B=%.0f W, C=%.0f W "
            "(B es el %.0f %% de la carga no critica); ambiente %.0f C; "
            "holdover %.2f h (tau=%.1f h, T_HI=%.1f, T_LIM=%.1f); eficiencia de carga %.2f; "
            "T_RESERVA = duracion del corte" % (
                p.etiqueta, p.a_w, p.b_w, p.c_w, p.b_share * 100, T_AMB_C, holdover(),
                Config().TAU_H, Config().T_HI_C, Config().T_LIM_C, ETA_CHARGE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", default=PERFIL_DEFECTO, choices=sorted(PERFILES),
                    help="juego de supuestos de partida (por defecto: %(default)s)")
    ap.add_argument("--out", default=None,
                    help="carpeta de salida (por defecto: out/ el didactico, "
                         "out/<perfil> los demas)")
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args()
    # Cada perfil tiene su carpeta: asi el didactico (out/) y el PQS (out/pqs_ref/)
    # no se pisan.
    out = args.out or ("out" if args.perfil == PERFIL_DEFECTO
                       else os.path.join("out", args.perfil))
    os.makedirs(out, exist_ok=True)

    p = PERFILES[args.perfil]
    s2a = sweep_s2a(perfil=p)
    s2b = sweep_s2b(perfil=p)
    s3 = sweep_s3(perfil=p)
    write_csv(os.path.join(out, "s2a_mejora.csv"), s2a)
    write_csv(os.path.join(out, "s2b_cobertura.csv"), s2b)
    write_csv(os.path.join(out, "s3_recarga.csv"), s3)
    print("CSV escritos en", out)
    print(assumptions_text(p))

    if not args.no_plots:
        try:
            import plots
        except ImportError:
            print("matplotlib no esta instalado: se omiten los mapas (pip install matplotlib)")
            return
        plots.make_all(out, s2a, s2b, s3, assumptions_text(p), perfil=p.nombre)
        print("Mapas escritos en", out)


if __name__ == "__main__":
    main()
