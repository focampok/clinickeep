# Resumen — Fase 4: calculadora de dimensionamiento

**Fecha:** 12 oct 2026
**Repo:** ClinicKeep (`clinickeep`)
**Alcance:** `calc/` (página estática, JS puro, sin framework ni build) + sus pruebas + publicación en `/calc` del servicio.
**Estado:** árbol limpio. `pytest -q`: **88 passed** (sin `node`: 83 passed, 5 skipped). `node calc/test_calc.mjs`: **OK, 876 filas / 3564 comprobaciones**. 7 commits en `main` local, **sin empujar** (`origin/main` sigue en `ddbe71e`).

---

## 1. Qué se pidió y en qué quedó

La calculadora responde, dados los datos de una clínica: cuántas horas protege la nevera con y sin ClinicKeep, y si alcanzan la batería y el cargador. Los 8 puntos del encargo se hicieron **un commit por punto**, con `pytest -q` al final de cada uno.

| Punto | Commit | Qué entró |
|---|---|---|
| 1 | `38250ef` | `calc/calc.js`: los 14 campos con valor, unidad, rango y `origen`; `energiaUtilWh`; validación y coherencia |
| 3 | `fb85698` | Las fórmulas, una función pura por cálculo (forma cerrada + holdover) |
| 2 | `a4b530b` | `simular()`: todas las salidas de una pieza |
| 4 | `cacda8d` | `calc/test_calc.mjs` + `tests/test_calc_js.py` (se omite si no hay `node`) |
| 5 | `296ff6e` | Etiqueta por campo, `PIE`, `docs/FUENTES_PENDIENTES.md` y las pruebas que lo vigilan |
| 6 | `371db4a` | `calc/index.html`: banner, temas, 360 px, teclado, icono+texto, copiar y CSV |
| 7 | `8c932f7` | `tools/publish_calc.py`, `/calc` en el servidor, pruebas del servicio y READMEs |

**Los puntos 2 y 3 se hicieron en el orden inverso al del encargo** (primero las fórmulas, después las salidas): las salidas no se pueden escribir sin las fórmulas, y así cada commit se sostiene solo en vez de meter las dos cosas en uno.

### Archivos nuevos

| Archivo | Líneas | Qué es |
|---|---|---|
| `calc/calc.js` | 416 | 21 exports: entradas, fórmulas y `simular`. Sin DOM, sin red, sin dependencias |
| `calc/index.html` | 551 | La página: CSS dentro, script como módulo que importa `calc.js` |
| `calc/package.json` | 6 | Solo marca la carpeta como ESM para que Node pueda importar `calc.js` |
| `calc/test_calc.mjs` | 186 | Node puro: `calc.js` contra los CSV de `scenarios.py` |
| `tests/test_calc_js.py` | 117 | Enlaza esa comparación con pytest + vigila las etiquetas de los supuestos |
| `tests/test_calc_html.py` | 91 | Lo que la página tiene que tener (sin navegador) |
| `tools/publish_calc.py` | 133 | Publica `calc/` en `server/static/calc/` y compara los supuestos con la fuente de verdad |
| `docs/FUENTES_PENDIENTES.md` | 68 | Los 14 campos, dónde están y qué falta para citarlos |
| `evidence/calc_360.png`, `calc_360_resultados.png`, `calc_escritorio.png`, `calc_oscuro.png` | — | Capturas |

Publicado (copia dentro de `server/`, para que `server/` siga siendo autocontenido): `server/static/calc/index.html`, `server/static/calc/calc.js`.

---

## 2. La respuesta con los supuestos por defecto

| Entrada | Valor | Etiqueta |
|---|---|---|
| A / B / C | 8 / 4 / 3 W | SUPUESTO (`scenarios.py`) |
| Batería | 128 Wh × 75 % = **96 Wh útiles** | SUPUESTO — por citar (`config.py: E_UTIL_WH` = 96) |
| Corte a cubrir | 12 h | SUPUESTO (`scenarios.py`) |
| Cargador / eficiencia | 30 W / 0.85 | SUPUESTO (la eficiencia, de `ETA_CHARGE`) |
| Ambiente / tau / T_HI / T_LIM | 25 °C / 4 h / 5.0 / 7.5 °C | SUPUESTO (`scenarios.py` y `config.py`) |
| Ciclos / cortes al mes | 300 ciclos / 2 | SUPUESTO — por citar |

| Salida | Valor |
|---|---|
| Horas protegidas **sin** ClinicKeep | **6.9 h** (6.4 h de nevera + 0.53 h de holdover) |
| Horas protegidas **con** ClinicKeep | **12.5 h** (12.0 h + 0.53 h) |
| Mejora | **+80.8 %** |
| ¿Cubre el corte de 12 h? (S2b) | **estado 1**: solo con ClinicKeep |
| ¿Alcanza el cargador de 30 W? (S3) | **estado 2**: recarga con y sin (reponer 112.9 Wh con 360 Wh disponibles en 12 h de red) |
| Vida de la batería | **12.5 años** (24 cortes/año, 300 ciclos) |

---

## 3. Las fórmulas (y por qué son esas)

Son las mismas que ya usaba el motor de escenarios, para que la página no invente física:

- **Horas de A con ClinicKeep**: `e/(a+b) < d ? e/a : (e/(a+b) − d) + d·(a+b)/a`. Es exactamente la forma cerrada que valida `tests/test_scenarios.py:closed_form_hours_a()`. C se abre al caer la red; B se abre cuando la autonomía total baja de `d` (la política lleva `T_RESERVA_H = d`).
- **Horas de A sin ClinicKeep**: `e/(a+b+c)`, compartiendo batería hasta agotarla (`outage_baseline`).
- **Holdover**: `tau · ln((Ta − T_HI)/(Ta − T_LIM))`, literal de `policy.py:holdover_h()`. Si el ambiente no supera T_LIM, `MAX_H` = 999 h (el mismo tope que la política).
- **Tiempo protegido** = horas de A + holdover.
- **S2b** (`cubre`): `prot_sin >= d` → 2; si no, `prot_con >= d` → 1; si no → 0.
- **S3** (recarga): `e_usada/eta <= cargador · (24 − d)`.
- **Vida**: `ciclos / (cortes_mes · 12)`. Un corte = un ciclo completo (conservador y dicho en la tarjeta).

### Validación contra la fuente de verdad

`calc/test_calc.mjs` reproduce las 876 filas de `s2a_mejora.csv`, `s2b_cobertura.csv` y `s3_recarga.csv` (regenerados con `scenarios.py`):

```
876 filas comprobadas, 3564 comprobaciones
  peor diferencia en horas:   0.0277 h (margen 0.05)
  peor diferencia en energia: 0.080 Wh (margen 0.5)
  peor diferencia en mejora:  0.275 pp (margen 1.989 pp, propaga ±0.05 h)
```

De cada fila solo se toman las entradas que le tocan (b/c en S2a, el cargador en S3, la `e_wh` de la fila como batería nominal con 100 % de profundidad); lo demás son los defectos. Así la prueba también vigila que los defectos siguen siendo los de `scenarios.py`/`config.py`.

---

## 4. Honestidad de los números

- Cada campo lleva **«SUPUESTO»** (9 campos, con el archivo y la constante en `origen`) o **«SUPUESTO — por citar»** (5 campos, que no están en ningún archivo del repo): `nominal_wh` 128 Wh, `dod_pct` 75 %, `ciclos` 300, `cortes_mes` 2, `cargador_w` 30 W.
- **No hay ni una URL escrita a mano** en el código, y una prueba lo comprueba (una cita inventada es peor que no tenerla).
- Pie permanente, visible en la página, en el resumen copiado y en el CSV: *«Análisis de sensibilidad con supuestos; no es predicción de cortes ni datos medidos»*.
- `docs/FUENTES_PENDIENTES.md` lista los 14 campos en dos tablas con **qué haría falta para citarlos** (medir la nevera, ficha del paquete de baterías, histórico de cortes…), y dice lo que este modelo **no** es.
- Pruebas que lo vigilan: todo defecto tiene etiqueta conocida, `origen` apunta a un archivo que existe, los «por citar» aparecen marcados en el documento, y el pie del HTML es idéntico al de `calc.js` (si uno cambia y el otro no, falla). Las tres primeras se verificaron **por mutación**.

---

## 5. Cómo correrlo

```bash
pytest -q                      # 88 pasan (sin node: 83 y 5 omitidas)
node calc/test_calc.mjs        # calc.js contra out/ (antes: python3 scenarios.py --out out)

python3 tools/publish_calc.py  # copia calc/ a server/static/calc/ y compara supuestos
cd calc && python3 -m http.server   # ojo: con file:// el navegador bloquea los módulos ES
```

Con el servicio: `cd server && uvicorn app:app --port 8000` → la calculadora en **`/calc`** (redirige a `/calc/` con 307, que es lo normal de un directorio montado) y el panel en `/`.

---

## 6. Decisiones y desviaciones (lo que conviene revisar)

1. **Tolerancia de la mejora.** Se pidió 0.1 %. Con ±0.05 h en las horas, el cociente `prot_con/prot_sin` se mueve hasta ~1.9 pp por propagación; 0.1 pp secos obligarían a copiar el paso de 0.02 h del simulador en la forma cerrada, que es justo lo que una forma cerrada no hace. La prueba usa `0.1 pp + lo que propagan las horas` y comprueba que la desviación real cabe. Con 0.1 pp fallarían 30 de 876 filas por redondeo de la integración. Está explicado en el encabezado de `test_calc.mjs`.
2. **Ciclos por defecto: 3000 → 300.** Con 3000 y 2 cortes/mes la página decía «125 años», que engaña. Con 300 dice 12.5 años. Sigue siendo un supuesto sin fuente.
3. **`server/app.py`:** 8 líneas **nuevas** (constante + montaje de `static/calc/` en `/calc` con `html=True`, guardado por `isdir`). Ninguna ruta existente cambió. Se monta aparte de `/static` para que la página pida su `calc.js` con ruta relativa.
4. **`server/static/index.html`:** el panel enlaza a la calculadora desde el subtítulo.
5. **`policy.py`, `config.py`, `wokwi/main.py`, `scenarios.py`, `plots.py` y `demo.py` siguen intactos** (verificado con `git diff --stat` contra `origin/main`).
6. **Sin verificar en navegador real:** el botón «Copiar resumen». En Chrome sin cabecera el portapapeles está bloqueado, así que solo se pudo comprobar que cae al plan B (copia clásica y, si tampoco, avisa y remite al CSV).

---

## 7. Comprobado a mano (navegador, final, servida por el uvicorn real en `/calc`)

Por DevTools Protocol, sin instalar nada: recalculado en vivo al cambiar un campo · mensaje de error + `aria-invalid` + resultados fuera al dejar un campo vacío · «Restablecer» vuelve a los supuestos · enlace CSV como blob (23 líneas: entradas, salidas y el pie) · 360 px sin scroll horizontal (`scrollWidth = 360`, ningún elemento desborda) · tema oscuro (`rgb(15,20,25)`) · 20 paradas de tabulador en orden con anillo de foco en todas · 14 campos, 4 grupos, 6 tarjetas, 9 etiquetas «SUPUESTO» y 5 «por citar».

---

## 8. Pendiente

- **Citar los 14 campos** de `docs/FUENTES_PENDIENTES.md` (hoy ninguno tiene fuente externa) y cambiar su etiqueta en `calc/calc.js`.
- **Empujar**: los 7 commits de la Fase 4 están solo en `main` local.
- Probar el botón «Copiar resumen» en un navegador normal.
- Nota de documentación: hay `docs/resumen-fase1.md` y `docs/resumen-fase2.md`, pero **no hay resumen de la Fase 3** (se puede reconstruir del historial de commits, `7e1c393`…`ddbe71e`).
