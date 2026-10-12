/* calc/calc.js - Calculadora de dimensionamiento de ClinicKeep (Fase 4).
 *
 * JavaScript puro: sin framework, sin build, sin dependencias.
 *
 * Es un modulo ES. Lo carga `calc/index.html` con <script type="module"> y lo
 * importa `calc/test_calc.mjs` desde Node (el `package.json` de esta carpeta no
 * declara dependencias: solo marca los .js como modulos ES).
 *
 * Aqui NO se toca el DOM ni la red: todo son funciones puras con numeros, para
 * poder contrastarlas desde Node con lo que genera el motor de escenarios.
 *
 * Fuente de verdad:
 *   * formulas  -> policy.py:holdover_h() y la forma cerrada que valida
 *                  tests/test_scenarios.py:closed_form_hours_a().
 *   * defectos  -> scenarios.py (A_W, B_W, C_W, ETA_CHARGE, T_AMB_C, d_h) y
 *                  config.py (E_UTIL_WH, TAU_H, T_HI_C, T_LIM_C).
 *
 * Todos los valores de entrada son SUPUESTOS de partida, no datos medidos:
 * esto es un analisis de sensibilidad, no una prediccion de cortes.
 */

/* Tope de "infinito" en horas: el mismo MAX_H de policy.py, para que la
 * calculadora y el motor de escenarios no discrepen en el caso limite. */
export const MAX_H = 999.0;

/* Grupos del formulario, en orden de pintado. */
export const GRUPOS = [
  { id: "cargas", titulo: "Cargas de la clinica" },
  { id: "bateria", titulo: "Bateria y respaldo" },
  { id: "red", titulo: "Corte de red y recarga" },
  { id: "termico", titulo: "Nevera (modelo termico)" },
];

/* Valores por defecto de la calculadora.
 *
 * Cada campo lleva: nombre (etiqueta visible), unidad, grupo, min/max/paso y
 * `origen`, que dice de donde sale el numero:
 *   "scenarios.py: A_W"  -> copiado del motor de escenarios (supuesto de partida)
 *   null                 -> elegido para esta calculadora; no esta en ningun
 *                           archivo del repo (ver docs/FUENTES_PENDIENTES.md)
 */
export const DEFAULTS = {
  // --- Cargas de la clinica ---
  a_w: {
    nombre: "Nevera de vacunas (zona A)", unidad: "W", grupo: "cargas",
    valor: 8.0, min: 0, max: 2000, paso: 0.5,
    origen: "scenarios.py: A_W",
  },
  b_w: {
    nombre: "Luces de pasillo (zona B)", unidad: "W", grupo: "cargas",
    valor: 4.0, min: 0, max: 2000, paso: 0.5,
    origen: "scenarios.py: B_W",
  },
  c_w: {
    nombre: "Sala de espera (zona C)", unidad: "W", grupo: "cargas",
    valor: 3.0, min: 0, max: 2000, paso: 0.5,
    origen: "scenarios.py: C_W",
  },

  // --- Bateria y respaldo ---
  nominal_wh: {
    nombre: "Bateria nominal", unidad: "Wh", grupo: "bateria",
    valor: 128.0, min: 1, max: 100000, paso: 1,
    origen: null,
  },
  dod_pct: {
    nombre: "Profundidad de descarga util", unidad: "%", grupo: "bateria",
    valor: 75.0, min: 1, max: 100, paso: 1,
    origen: null,
  },
  ciclos: {
    nombre: "Ciclos de vida de la bateria", unidad: "ciclos", grupo: "bateria",
    valor: 300.0, min: 1, max: 100000, paso: 100,
    origen: null,
  },
  cortes_mes: {
    nombre: "Cortes por mes", unidad: "cortes/mes", grupo: "bateria",
    valor: 2.0, min: 0, max: 100, paso: 1,
    origen: null,
  },

  // --- Corte de red y recarga ---
  d_h: {
    nombre: "Duracion del corte", unidad: "h", grupo: "red",
    valor: 12.0, min: 0.5, max: 168, paso: 0.5,
    origen: "scenarios.py: sweep_s2a(d_h=12)",
  },
  cargador_w: {
    nombre: "Potencia del cargador", unidad: "W", grupo: "red",
    valor: 30.0, min: 0.1, max: 5000, paso: 0.5,
    origen: null,
  },
  eta: {
    nombre: "Eficiencia de carga", unidad: "0-1", grupo: "red",
    valor: 0.85, min: 0.1, max: 1, paso: 0.01,
    origen: "scenarios.py: ETA_CHARGE",
  },

  // --- Modelo termico de la nevera ---
  t_amb_c: {
    nombre: "Temperatura ambiente", unidad: "C", grupo: "termico",
    valor: 25.0, min: -20, max: 60, paso: 1,
    origen: "scenarios.py: T_AMB_C",
  },
  tau_h: {
    nombre: "Constante de tiempo de la nevera", unidad: "h", grupo: "termico",
    valor: 4.0, min: 0.1, max: 48, paso: 0.5,
    origen: "config.py: TAU_H",
  },
  t_hi_c: {
    nombre: "Temperatura al apagarse A", unidad: "C", grupo: "termico",
    valor: 5.0, min: -20, max: 20, paso: 0.5,
    origen: "config.py: T_HI_C",
  },
  t_lim_c: {
    nombre: "Limite seguro de la nevera", unidad: "C", grupo: "termico",
    valor: 7.5, min: -20, max: 40, paso: 0.5,
    origen: "config.py: T_LIM_C",
  },
};

/* Los valores por defecto, sin la metadata: es lo que come `simular()`. */
export function valoresPorDefecto() {
  const out = {};
  for (const clave of Object.keys(DEFAULTS)) out[clave] = DEFAULTS[clave].valor;
  return out;
}

/* Energia util = energia nominal x profundidad de descarga util.
 * Es la E_UTIL_WH que usa el firmware: con 128 Wh y 75 % da 96 Wh, el valor de
 * config.py. */
export function energiaUtilWh(nominal_wh, dod_pct) {
  return nominal_wh * dod_pct / 100.0;
}

/* Convierte lo que llega del formulario (texto) a numeros y comprueba rangos.
 * Devuelve { valores, errores }; si hay errores, `valores` esta incompleto y no
 * se debe calcular nada. */
export function normalizarEntradas(raw) {
  const valores = {};
  const errores = [];
  for (const clave of Object.keys(DEFAULTS)) {
    const meta = DEFAULTS[clave];
    if (!(clave in raw)) {
      errores.push({ clave, mensaje: meta.nombre + ": falta el valor" });
      continue;
    }
    const bruto = raw[clave];
    let n;
    if (typeof bruto === "number") {
      n = bruto;
    } else {
      const texto = String(bruto).trim();
      if (texto === "") {
        errores.push({ clave, mensaje: meta.nombre + ": vacio" });
        continue;
      }
      // Se acepta la coma decimal (teclado en espanol) y los espacios.
      n = Number(texto.replace(",", "."));
    }
    if (!Number.isFinite(n)) {
      errores.push({ clave, mensaje: meta.nombre + ': "' + bruto + '" no es un numero' });
      continue;
    }
    if (n < meta.min || n > meta.max) {
      errores.push({
        clave,
        mensaje: meta.nombre + ": fuera de rango (" + meta.min + " a " + meta.max +
                 " " + meta.unidad + ")",
      });
      continue;
    }
    valores[clave] = n;
  }
  return { valores, errores };
}

/* Coherencia entre campos (lo que ningun rango individual puede comprobar).
 * Se llama despues de `normalizarEntradas`. */
export function validarCoherencia(valores) {
  const errores = [];
  if (valores.t_hi_c >= valores.t_lim_c) {
    errores.push({
      clave: "t_hi_c",
      mensaje: "La temperatura de apagado (" + valores.t_hi_c +
               " C) debe ser menor que el limite seguro (" + valores.t_lim_c + " C)",
    });
  }
  if (valores.b_w + valores.c_w <= 0 && valores.a_w <= 0) {
    errores.push({ clave: "a_w", mensaje: "Sin carga no hay nada que dimensionar" });
  }
  return errores;
}
