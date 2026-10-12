#!/usr/bin/env node
/* calc/test_calc.mjs - Prueba de consistencia de la calculadora (Fase 4, punto 4).
 *
 * Node puro, sin dependencias. Carga los CSV que genera el motor de escenarios
 * (scenarios.py, la fuente de verdad) y comprueba que calc.js reproduce cada
 * fila con la forma cerrada.
 *
 *   node calc/test_calc.mjs                       -> out/ del repo, perfil didactico
 *   node calc/test_calc.mjs <carpeta>             -> otra carpeta con los 3 CSV
 *   node calc/test_calc.mjs <carpeta> <perfil>    -> con los defectos de ese perfil
 *
 * El perfil importa: los CSV del perfil PQS (out/pqs_ref/) se generan con
 * A=35 W, y calc.js solo los reproduce si usa los defectos de `pqs_ref`.
 *
 * Tolerancias. La forma cerrada es continua y scenarios.py integra con pasos de
 * DT_H = 0.02 h, asi que las horas pueden diferir un pelo:
 *
 *   horas          ±0.05 h  (el paso del motor de escenarios)
 *   energia usada  ±0.5 Wh  (a lo sumo, un paso de simulacion con B encendida)
 *   mejora (%)     ±0.1 pp + lo que propaga el margen de las horas, porque la
 *                  mejora es un cociente de dos cantidades conocidas con ese
 *                  margen: 100*(pc/ps)*(0.05/pc + 0.05/ps). Un margen de 0.1 pp
 *                  a secas no se puede cumplir sin copiar el paso de 0.02 h,
 *                  que es justo lo que una forma cerrada no hace.
 *
 * Los estados (S2b y S3) se comparan exactos: son enteros que deciden "cubre /
 * no cubre" y ahi no cabe un margen.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

import { PERFILES, PERFIL_DEFECTO, valoresDePerfil, simular } from "./calc.js";

const TOL_H = 0.05;
const TOL_WH = 0.5;
const TOL_PP = 0.1;

const AQUI = dirname(fileURLToPath(import.meta.url));
const CARPETA = resolve(process.argv[2] || join(AQUI, "..", "out"));
const PERFIL = process.argv[3] || PERFIL_DEFECTO;
if (!Object.prototype.hasOwnProperty.call(PERFILES, PERFIL)) {
  console.error(`Perfil desconocido: ${PERFIL} (hay: ${Object.keys(PERFILES).join(", ")})`);
  process.exit(2);
}

let comprobaciones = 0;
const fallos = [];
const peor = { h: 0, wh: 0, pp: 0, pp_tol: 0, fichero: "" };

function comprobar(ok, mensaje) {
  comprobaciones += 1;
  if (!ok) fallos.push(mensaje);
}

function leerCsv(nombre) {
  const texto = readFileSync(join(CARPETA, nombre), "utf8").trim();
  const lineas = texto.split(/\r?\n/);
  const cabecera = lineas.shift().split(",");
  return lineas.map((linea) => {
    const celdas = linea.split(",");
    const fila = {};
    cabecera.forEach((clave, i) => { fila[clave] = celdas[i]; });
    return fila;
  });
}

const num = (v) => Number(v);

/* Entradas de la calculadora a partir de una fila del CSV: el resto son los
 * defectos del perfil (que es, de paso, como se comprueba que siguen siendo los
 * de scenarios.py/config.py: si cambiaran, los numeros no cuadrarian).
 * dod_pct = 100 hace que la bateria nominal del defecto valga exactamente la
 * e_wh de la fila. */
function entradasDeFila(fila, extra = {}) {
  return Object.assign(valoresDePerfil(PERFIL), {
    nominal_wh: num(fila.e_wh),
    dod_pct: 100,
    d_h: num(fila.d_h),
  }, extra);
}

function anotaPeor(fichero, h, wh, pp, ppTol) {
  if (h > peor.h) { peor.h = h; peor.fichero = fichero; }
  if (wh > peor.wh) peor.wh = wh;
  if (pp > peor.pp) { peor.pp = pp; peor.pp_tol = ppTol; }
}

/* --- S2a: mejora del tiempo protegido segun bateria y carga no critica ------ */
function probarS2a() {
  const filas = leerCsv("s2a_mejora.csv");
  for (const fila of filas) {
    const r = simular(entradasDeFila(fila, {
      b_w: num(fila.b_w),
      c_w: num(fila.c_w),
    }));
    const etiqueta = `s2a_mejora.csv e=${fila.e_wh} Wh, no critica=${fila.no_critica_pct} %`;

    const dSin = Math.abs(r.sin.protegidas_h - num(fila.prot_sin_h));
    const dCon = Math.abs(r.con.protegidas_h - num(fila.prot_con_h));
    anotaPeor("s2a_mejora.csv", Math.max(dSin, dCon), 0, 0, 0);

    comprobar(dSin <= TOL_H, `${etiqueta}: prot_sin ${r.sin.protegidas_h.toFixed(3)} vs ` +
      `${fila.prot_sin_h} del CSV (dif ${dSin.toFixed(4)} h)`);
    comprobar(dCon <= TOL_H, `${etiqueta}: prot_con ${r.con.protegidas_h.toFixed(3)} vs ` +
      `${fila.prot_con_h} del CSV (dif ${dCon.toFixed(4)} h)`);

    // La mejora tiene que cuadrar dentro de lo que propagan esas horas.
    const ppCalc = r.mejora_pct;
    const ppCsv = num(fila.mejora_pct);
    const ppTol = TOL_PP + 100 * (r.con.protegidas_h / r.sin.protegidas_h) *
      (TOL_H / r.con.protegidas_h + TOL_H / r.sin.protegidas_h);
    const dPp = Math.abs(ppCalc - ppCsv);
    anotaPeor("s2a_mejora.csv", 0, 0, dPp, ppTol);
    comprobar(dPp <= ppTol, `${etiqueta}: mejora ${ppCalc.toFixed(2)} % vs ${fila.mejora_pct} % ` +
      `del CSV (dif ${dPp.toFixed(3)} pp, margen ${ppTol.toFixed(3)} pp)`);
  }
  return filas.length;
}

/* --- S2b: la nevera cubre todo el corte? (0 / 1 / 2) ----------------------- */
function probarS2b() {
  const filas = leerCsv("s2b_cobertura.csv");
  for (const fila of filas) {
    const r = simular(entradasDeFila(fila));
    const etiqueta = `s2b_cobertura.csv e=${fila.e_wh} Wh, corte=${fila.d_h} h`;

    const dSin = Math.abs(r.sin.protegidas_h - num(fila.prot_sin_h));
    const dCon = Math.abs(r.con.protegidas_h - num(fila.prot_con_h));
    anotaPeor("s2b_cobertura.csv", Math.max(dSin, dCon), 0, 0, 0);
    comprobar(dSin <= TOL_H, `${etiqueta}: prot_sin dif ${dSin.toFixed(4)} h`);
    comprobar(dCon <= TOL_H, `${etiqueta}: prot_con dif ${dCon.toFixed(4)} h`);

    comprobar(r.cobertura.estado === num(fila.estado),
      `${etiqueta}: estado ${r.cobertura.estado} vs ${fila.estado} del CSV`);
    comprobar(Number(r.cobertura.cubre_sin) === num(fila.cubre_sin),
      `${etiqueta}: cubre_sin ${r.cobertura.cubre_sin} vs ${fila.cubre_sin}`);
    comprobar(Number(r.cobertura.cubre_con) === num(fila.cubre_con),
      `${etiqueta}: cubre_con ${r.cobertura.cubre_con} vs ${fila.cubre_con}`);
  }
  return filas.length;
}

/* --- S3: alcanza a recargarse entre cortes? -------------------------------- */
function probarS3() {
  const filas = leerCsv("s3_recarga.csv");
  for (const fila of filas) {
    const r = simular(entradasDeFila(fila, { cargador_w: num(fila.cargador_w) }));
    const etiqueta = `s3_recarga.csv corte=${fila.d_h} h, cargador=${fila.cargador_w} W`;

    const dSin = Math.abs(r.sin.e_usada_wh - num(fila.e_usada_sin_wh));
    const dCon = Math.abs(r.con.e_usada_wh - num(fila.e_usada_con_wh));
    anotaPeor("s3_recarga.csv", 0, Math.max(dSin, dCon), 0, 0);
    comprobar(dSin <= TOL_WH, `${etiqueta}: e_usada_sin ${r.sin.e_usada_wh.toFixed(2)} vs ` +
      `${fila.e_usada_sin_wh} Wh (dif ${dSin.toFixed(3)} Wh)`);
    comprobar(dCon <= TOL_WH, `${etiqueta}: e_usada_con ${r.con.e_usada_wh.toFixed(2)} vs ` +
      `${fila.e_usada_con_wh} Wh (dif ${dCon.toFixed(3)} Wh)`);

    comprobar(r.recarga.estado === num(fila.estado),
      `${etiqueta}: estado ${r.recarga.estado} vs ${fila.estado} del CSV`);
    comprobar(Number(r.recarga.ok_sin) === num(fila.recarga_sin),
      `${etiqueta}: recarga_sin ${r.recarga.ok_sin} vs ${fila.recarga_sin}`);
    comprobar(Number(r.recarga.ok_con) === num(fila.recarga_con),
      `${etiqueta}: recarga_con ${r.recarga.ok_con} vs ${fila.recarga_con}`);
  }
  return filas.length;
}

// --- ejecucion --------------------------------------------------------------

console.log(`calc.js contra el motor de escenarios (${CARPETA}), perfil ${PERFIL}`);
let filas = 0;
try {
  filas += probarS2a();
  filas += probarS2b();
  filas += probarS3();
} catch (err) {
  console.error(`No se pudieron leer los CSV de ${CARPETA}: ${err.message}`);
  console.error("Genera primero los escenarios:  python3 scenarios.py --out out");
  process.exit(2);
}

console.log(`  ${filas} filas comprobadas, ${comprobaciones} comprobaciones`);
console.log(`  peor diferencia en horas:   ${peor.h.toFixed(4)} h (margen ${TOL_H})`);
console.log(`  peor diferencia en energia: ${peor.wh.toFixed(3)} Wh (margen ${TOL_WH})`);
console.log(`  peor diferencia en mejora:  ${peor.pp.toFixed(3)} pp ` +
  `(margen ${peor.pp_tol.toFixed(3)} pp, propaga ±${TOL_H} h)`);

if (fallos.length) {
  console.error(`\nFALLAN ${fallos.length} comprobaciones:`);
  for (const f of fallos.slice(0, 20)) console.error("  - " + f);
  if (fallos.length > 20) console.error(`  ... y ${fallos.length - 20} mas`);
  process.exit(1);
}
console.log("OK: calc.js reproduce los tres CSV dentro de tolerancia");
