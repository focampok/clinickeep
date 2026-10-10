# policy.py - Nucleo de politica de ClinicKeep.
#
# Escrito para correr igual en MicroPython (ESP32 en Wokwi) y en Python normal
# (pruebas y motor de escenarios). Por eso: sin dataclasses, sin typing, sin
# librerias externas; solo `math`.
#
# Reglas de diseno:
#   1. La zona A (nevera) NUNCA se corta por software. out["relay_a"] siempre es True.
#   2. Durante un corte el shedding es MONOTONO: una vez abierto B, no se reabre
#      hasta que la red vuelva. Asi no hay oscilaciones ni necesidad de histeresis.
#   3. Los temporizadores usan tiempo REAL; la energia usa tiempo SIMULADO (x k).
#   4. "Tiempo seguro" = autonomia de A + holdover termico, ambos en el mismo reloj.
#
# Zonas: A = nevera de vacunas (critica), B = luces de pasillo, C = sala de espera.

import math

NORMAL = "NORMAL"
CORTE = "CORTE"
AHORRO = "AHORRO"
CRITICO = "CRITICO"
RESTAURACION = "RESTAURACION"
FALLO_SENSOR = "FALLO_SENSOR"

MAX_H = 999.0  # tope para "infinito" (serializa bien en JSON)


def _hours(energy_wh, power_w):
    """Horas que dura `energy_wh` a `power_w`, con tope MAX_H."""
    if power_w < 0.05:
        return MAX_H
    h = energy_wh / power_w
    if h > MAX_H:
        return MAX_H
    return h


def holdover_h(cfg, t_amb_c):
    """Horas hasta que la caja pasa de T_HI a T_LIM sin energia (modelo de Newton).

    T(t) = Ta + (T_HI - Ta) * exp(-t/tau)  =>  t = tau * ln((Ta - T_HI) / (Ta - T_LIM))
    Si el ambiente no supera el limite, la caja nunca lo alcanza.
    """
    if t_amb_c <= cfg.T_LIM_C:
        return MAX_H
    h = cfg.TAU_H * math.log((t_amb_c - cfg.T_HI_C) / (t_amb_c - cfg.T_LIM_C))
    if h > MAX_H:
        return MAX_H
    return h


def _metrics(cfg, e_rest, p_total_w, p_a_w, t_amb_c, temp_ok):
    """Autonomias, holdover y tiempo seguro (todo en horas simuladas)."""
    aut_total_h = _hours(e_rest, p_total_w)
    aut_a_h = _hours(e_rest, p_a_w)
    if temp_ok:
        amb = cfg.T_AMB_C if t_amb_c is None else t_amb_c
        hold_h = holdover_h(cfg, amb)
        safe_h = aut_a_h + hold_h
        if safe_h > MAX_H:
            safe_h = MAX_H
    else:
        hold_h = None            # sin sensor no hay holdover: el tiempo seguro es solo la bateria
        safe_h = aut_a_h
    return aut_total_h, aut_a_h, hold_h, safe_h


class State:
    def __init__(self):
        self.mode = NORMAL
        self.grid_ok = True      # red ya filtrada (con antirrebote)
        self.cand_s = 0.0        # segundos reales que la lectura cruda difiere de grid_ok
        self.e_used_wh = 0.0     # energia consumida de la bateria en este corte
        self.b_on = True
        self.c_on = True
        self.stagger_s = 0.0
        self.power_fail = 0      # lecturas malas consecutivas del sensor de potencia
        self.fault = False
        self.critical = False


def new_state():
    return State()


def step(st, cfg, grid_raw, p_total_w, p_a_w, dt_real_s,
         k=1.0, t_amb_c=None, power_ok=True, temp_ok=True):
    """Avanza la politica un paso. Devuelve un dict con salidas y metricas.

    grid_raw   : lectura cruda de la red (True = hay red)
    p_total_w  : potencia total medida (W); p_a_w: potencia de A (W)
    dt_real_s  : segundos reales desde el paso anterior
    k          : factor del reloj de simulacion (1 = tiempo real)
    power_ok   : False si el sensor de potencia fallo en esta lectura
    temp_ok    : False si el sensor de temperatura fallo
    """
    events = []

    # 1. Fallo del sensor de potencia (si falla, se usa una carga conservadora)
    if power_ok:
        st.power_fail = 0
    else:
        st.power_fail += 1
        p_total_w = cfg.P_FALLBACK_TOTAL_W
        p_a_w = cfg.P_FALLBACK_A_W
    fault = st.power_fail >= cfg.FAULT_COUNT
    if fault != st.fault:
        events.append("sensor_fault" if fault else "sensor_ok")
        st.fault = fault

    # 2. Filtro de la red (antirrebote distinto para caer y para volver)
    grid_raw = bool(grid_raw)
    if grid_raw != st.grid_ok:
        st.cand_s += dt_real_s
        need = cfg.T_DEBOUNCE_S if st.grid_ok else cfg.T_RESTORE_S
        if st.cand_s >= need:
            st.grid_ok = grid_raw
            st.cand_s = 0.0
            if grid_raw:
                events.append("grid_up")
            else:
                events.append("grid_down")
                st.mode = CORTE
                st.critical = False
                if st.c_on:
                    st.c_on = False
                    events.append("shed_c")
    else:
        st.cand_s = 0.0

    # 3. Energia (solo se consume bateria con la red caida; usa tiempo simulado)
    if not st.grid_ok:
        st.e_used_wh += p_total_w * dt_real_s * k / 3600.0
    e_rest = cfg.E_UTIL_WH - st.e_used_wh
    if e_rest < 0.0:
        e_rest = 0.0

    # 4. Metricas
    aut_total_h, aut_a_h, hold_h, safe_h = _metrics(
        cfg, e_rest, p_total_w, p_a_w, t_amb_c, temp_ok)

    # 5. Maquina de estados
    if not st.grid_ok:
        if st.fault:
            if st.mode != FALLO_SENSOR:
                st.mode = FALLO_SENSOR
                events.append("fault_mode")
            if st.b_on:
                st.b_on = False
                events.append("shed_b_fault")
            st.c_on = False
        else:
            if st.mode == FALLO_SENSOR:
                st.mode = CORTE if st.b_on else AHORRO
            if st.mode == CORTE and aut_total_h < cfg.T_RESERVA_H:
                st.b_on = False
                st.mode = AHORRO
                events.append("shed_b")
            if st.mode == AHORRO and safe_h < cfg.T_ACT_MIN_H:
                st.mode = CRITICO
                st.critical = True
                events.append("critical")
    else:
        if st.mode in (CORTE, AHORRO, CRITICO, FALLO_SENSOR):
            st.mode = RESTAURACION
            st.stagger_s = 0.0
            st.b_on = True
            st.critical = False
            events.append("restore_b")
        elif st.mode == RESTAURACION:
            st.stagger_s += dt_real_s
            if st.stagger_s >= cfg.T_STAGGER_S:
                st.c_on = True
                st.mode = NORMAL
                st.e_used_wh = 0.0   # simplificacion: la bateria vuelve a 100 %
                e_rest = cfg.E_UTIL_WH
                aut_total_h, aut_a_h, hold_h, safe_h = _metrics(
                    cfg, e_rest, p_total_w, p_a_w, t_amb_c, temp_ok)
                events.append("restore_c")

    return {
        "mode": st.mode,
        "grid_ok": st.grid_ok,
        "relay_a": True,                 # A nunca se corta por software
        "relay_b": st.b_on,
        "relay_c": st.c_on,
        "alarm": st.critical or st.fault,
        "soc": e_rest / cfg.E_UTIL_WH,
        "e_rest_wh": e_rest,
        "aut_total_h": aut_total_h,
        "aut_a_h": aut_a_h,
        "holdover_h": hold_h,
        "safe_h": safe_h,
        "events": events,
    }
