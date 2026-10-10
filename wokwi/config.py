# config.py - Parametros de ClinicKeep (compatible con MicroPython).
#
# Todos los valores son SUPUESTOS DE PARTIDA para la maqueta simulada.
# Antes del submit, cada uno debe llevar fuente citada o quedar declarado como supuesto.


class Config:
    # --- Fuente de respaldo ---
    E_UTIL_WH = 96.0          # energia util de la bateria (ej.: 12 V x 8 Ah). SUPUESTO

    # --- Temporizadores (segundos REALES, no simulados) ---
    T_DEBOUNCE_S = 2.0        # red ausente durante este tiempo => corte confirmado
    T_RESTORE_S = 5.0         # red presente durante este tiempo => restauracion
    T_STAGGER_S = 3.0         # espera entre cerrar B y cerrar C al restaurar

    # --- Umbrales de la politica (en horas SIMULADAS) ---
    T_RESERVA_H = 6.0         # si la autonomia total baja de esto, se abre B
    T_ACT_MIN_H = 1.0         # si el tiempo seguro baja de esto, alarma CRITICO

    # --- Gemelo termico de la nevera (modelo de masa concentrada) ---
    TAU_H = 4.0               # constante de tiempo. SUPUESTO: tomar de ficha tecnica
    T_HI_C = 5.0              # temperatura al apagarse A (techo de la banda de control)
    T_LIM_C = 7.5             # limite seguro (8 C menos margen del sensor)
    T_AMB_C = 25.0            # temperatura ambiente por defecto

    # --- Fallo de sensor ---
    FAULT_COUNT = 3           # lecturas malas consecutivas => fallo
    P_FALLBACK_TOTAL_W = 15.0  # carga total conservadora si el sensor falla
    P_FALLBACK_A_W = 8.0       # carga de A conservadora si el sensor falla

    def __init__(self, **kw):
        for k in kw:
            setattr(self, k, kw[k])
