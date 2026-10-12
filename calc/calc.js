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

// ---------------------------------------------------------------------------
// Formulas (punto 3): una funcion pura por calculo.
//
// Los nombres de las horas son los mismos del motor de escenarios:
//   prot_sin_h / prot_con_h  = horas protegidas SIN y CON ClinicKeep
//   e_usada_wh               = energia que sale de la bateria durante el corte
// ---------------------------------------------------------------------------

/* Horas con energia en A si NO hay ClinicKeep: A, B y C comparten la bateria
 * hasta agotarla. Equivale a scenarios.py:outage_baseline(). */
export function horasA_sin(e_util_wh, a_w, b_w, c_w) {
  const p = a_w + b_w + c_w;
  if (p < 0.05) return MAX_H;   // sin carga la bateria no se agota (policy._hours)
  return Math.min(e_util_wh / p, MAX_H);
}

/* Horas con energia en A CON ClinicKeep. Forma cerrada: la misma que valida
 * tests/test_scenarios.py:closed_form_hours_a().
 *
 * Al caer la red se abre C. B sigue hasta que la autonomia total baja de la
 * duracion del corte d (la politica lleva T_RESERVA_H = d), o sea en
 * t_desconexion = e/(a+b) - d. A partir de ahi solo queda A.
 *
 *   si e/(a+b) < d : B no llega a desconectarse y la bateria se agota con A+B
 *                    (queda e/a horas de A)
 *   si no          : t_desconexion horas con A+B  +  el resto con A sola */
export function horasA_con(e_util_wh, a_w, b_w, d_h) {
  if (a_w < 0.05) return MAX_H;         // A nunca se agota: no hay limite
  const p = a_w + b_w;
  if (e_util_wh / p < d_h) return Math.min(e_util_wh / a_w, MAX_H);
  const t_desconexion_h = e_util_wh / p - d_h;
  return Math.min(t_desconexion_h + d_h * p / a_w, MAX_H);
}

/* Horas hasta que la caja pasa de T_HI a T_LIM sin energia (modelo de Newton
 * de masa concentrada). Es policy.py:holdover_h() literal:
 *
 *   T(t) = Ta + (T_HI - Ta) * exp(-t/tau)  =>  t = tau * ln((Ta-T_HI)/(Ta-T_LIM))
 *
 * Si el ambiente no supera T_LIM, la caja nunca lo alcanza: MAX_H. */
export function holdoverHoras(tau_h, t_hi_c, t_lim_c, t_amb_c) {
  if (t_amb_c <= t_lim_c) return MAX_H;
  return Math.min(
    tau_h * Math.log((t_amb_c - t_hi_c) / (t_amb_c - t_lim_c)),
    MAX_H
  );
}

/* Horas protegidas = horas con energia en A + holdover termico de la caja.
 * Es la definicion que usa scenarios.py (autonomia + tiempo de gracia). */
export function horasProtegidas(horas_a_h, holdover_h) {
  return horas_a_h + holdover_h;
}

/* Energia que sale de la bateria durante un corte de d_h horas SIN ClinicKeep:
 * A, B y C tiran de ella, asi que como mucho se agota. */
export function energiaUsada_sin(e_util_wh, a_w, b_w, c_w, d_h) {
  return Math.min(e_util_wh, (a_w + b_w + c_w) * d_h);
}

/* Energia que sale de la bateria durante un corte de d_h horas CON ClinicKeep:
 * si B se desconecta dentro del corte, cuenta (a+b) hasta la desconexion y a
 * desde ahi; si no se desconecta, cuenta (a+b) todo el corte. */
export function energiaUsada_con(e_util_wh, a_w, b_w, d_h) {
  const p = a_w + b_w;
  if (p < 0.05) return 0.0;
  if (e_util_wh / p < d_h) {
    // B se abre en el primer paso: lo cubre A sola, y la bateria puede no
    // llegar a las d_h horas.
    return Math.min(e_util_wh, a_w * d_h);
  }
  const t_desconexion_h = e_util_wh / p - d_h;
  const t_con_b_h = Math.min(t_desconexion_h, d_h);
  return Math.min(e_util_wh, p * t_con_b_h + a_w * (d_h - t_con_b_h));
}

/* Mejora (%) del tiempo protegido frente a no hacer nada. Sin horas sin
 * ClinicKeep no hay proporcion que calcular (null). */
export function mejoraPct(prot_sin_h, prot_con_h) {
  if (prot_sin_h <= 0) return null;
  return (prot_con_h / prot_sin_h - 1.0) * 100.0;
}

/* Los 3 estados de S2b: la nevera cubre todo el corte?
 *   estado 0 -> no cubre ni con ClinicKeep
 *   estado 1 -> solo cubre con ClinicKeep
 *   estado 2 -> cubre con y sin ClinicKeep */
export function estadoCobertura(prot_sin_h, prot_con_h, d_h) {
  const cubre_sin = prot_sin_h >= d_h;
  const cubre_con = prot_con_h >= d_h;
  return { cubre_sin, cubre_con, estado: cubre_sin ? 2 : (cubre_con ? 1 : 0) };
}

/* S3: el cargador alcanza a reponer entre cortes? La energia que hay que meter
 * es la usada / eficiencia (lo que se pierde cargando), y el tiempo disponible
 * es (24 - duracion del corte) horas de red. */
export function recargaAlcanza(e_usada_wh, eta, cargador_w, t_red_h) {
  return e_usada_wh / eta <= cargador_w * t_red_h;
}

/* Los 3 estados de S3:
 *   0 -> no recarga ni con ClinicKeep, 1 -> solo con ClinicKeep, 2 -> recarga
 *   con y sin ClinicKeep. */
export function estadoRecarga(ok_sin, ok_con) {
  return ok_sin ? 2 : (ok_con ? 1 : 0);
}

/* Vida estimada de la bateria en anios: ciclos de vida / ciclos que se gastan
 * al anio. Aqui un corte = un ciclo completo (conservador: el corte promedio
 * rara vez agota la bateria). Sin cortes no hay desgaste: null. */
export function vidaBateriaAnios(ciclos, cortes_mes) {
  if (cortes_mes <= 0) return null;
  return ciclos / (cortes_mes * 12.0);
}

// ---------------------------------------------------------------------------
// Salidas (punto 2): todo lo que responde la calculadora, de una sola pieza.
// ---------------------------------------------------------------------------

/* Calcula las salidas a partir de las entradas ya validadas (los numeros de
 * `valoresPorDefecto()` con lo que haya puesto la persona en el formulario).
 *
 * Devuelve:
 *   e_util_wh      bateria nominal x profundidad de descarga util
 *   holdover_h     tiempo de gracia termico de la caja (MAX_H si no hay limite)
 *   t_red_h        horas de red al dia (24 - duracion del corte)
 *   sin / con      horas con energia en A, horas protegidas, energia usada del
 *                  corte y si alcanza a recargarse
 *   mejora_pct     cuanto alarga ClinicKeep el tiempo protegido
 *   cobertura      estado 0/1/2 de S2b: cubre el corte?
 *   recarga        estado 0/1/2 de S3 + energia que hay que reponer y la que da
 *                  el cargador en las horas de red
 *   bateria        ciclos al anio y vida estimada en anios
 */
export function simular(entradas) {
  const e_util_wh = energiaUtilWh(entradas.nominal_wh, entradas.dod_pct);
  const holdover_h = holdoverHoras(
    entradas.tau_h, entradas.t_hi_c, entradas.t_lim_c, entradas.t_amb_c);
  const t_red_h = 24.0 - entradas.d_h;

  const horas_a_sin = horasA_sin(e_util_wh, entradas.a_w, entradas.b_w, entradas.c_w);
  const horas_a_con = horasA_con(e_util_wh, entradas.a_w, entradas.b_w, entradas.d_h);
  const prot_sin_h = horasProtegidas(horas_a_sin, holdover_h);
  const prot_con_h = horasProtegidas(horas_a_con, holdover_h);

  const e_usada_sin_wh = energiaUsada_sin(
    e_util_wh, entradas.a_w, entradas.b_w, entradas.c_w, entradas.d_h);
  const e_usada_con_wh = energiaUsada_con(
    e_util_wh, entradas.a_w, entradas.b_w, entradas.d_h);

  const ok_sin = recargaAlcanza(e_usada_sin_wh, entradas.eta, entradas.cargador_w, t_red_h);
  const ok_con = recargaAlcanza(e_usada_con_wh, entradas.eta, entradas.cargador_w, t_red_h);

  return {
    e_util_wh: e_util_wh,
    holdover_h: holdover_h,
    t_red_h: t_red_h,

    sin: {
      horas_a_h: horas_a_sin,
      protegidas_h: prot_sin_h,
      e_usada_wh: e_usada_sin_wh,
      e_repuesta_wh: e_usada_sin_wh / entradas.eta,   // lo que hay que meter en la bateria
      recarga_ok: ok_sin,
    },
    con: {
      horas_a_h: horas_a_con,
      protegidas_h: prot_con_h,
      e_usada_wh: e_usada_con_wh,
      e_repuesta_wh: e_usada_con_wh / entradas.eta,
      recarga_ok: ok_con,
    },

    mejora_pct: mejoraPct(prot_sin_h, prot_con_h),
    cobertura: estadoCobertura(prot_sin_h, prot_con_h, entradas.d_h),
    recarga: {
      estado: estadoRecarga(ok_sin, ok_con),
      ok_sin: ok_sin,
      ok_con: ok_con,
      disponible_wh: entradas.cargador_w * t_red_h,
    },
    bateria: {
      ciclos: entradas.ciclos,
      cortes_anio: entradas.cortes_mes * 12.0,
      vida_anios: vidaBateriaAnios(entradas.ciclos, entradas.cortes_mes),
    },
  };
}
