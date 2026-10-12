# Resumen — Fase 4b: perfiles y fuentes

**Fecha:** 12 oct 2026
**Repo:** ClinicKeep (`clinickeep`)
**Alcance:** `scenarios.py` (perfiles), `plots.py` (titulo y pie por perfil), `calc/` (selector de perfil y campos con fuente), el panel, `docs/FUENTES_PENDIENTES.md` y las pruebas.
**Estado:** `pytest -q`: **103 passed** (sin `node`: 98 passed, 5 skipped). `node calc/test_calc.mjs`: **876 filas / 3564 comprobaciones**; `node calc/test_calc.mjs out/pqs_ref pqs_ref`: **726 filas / 2984 comprobaciones**; los dos OK. 6 commits en `main`.

No se toco `policy.py`, `config.py`, `wokwi/main.py` ni `server/app.py`.

---

## 1. Los dos perfiles

| Perfil | Nevera (A) | B / C | Bateria (barrido) | Etiqueta visible |
|---|---|---|---|---|
| `didactico` (**por defecto**) | 8 W | 4 / 3 W | 24 … 300 Wh | "perfil didáctico de demo, no representa una nevera PQS" |
| `pqs_ref` | **35 W** (fuente: PQS E003-066, 0.85 kWh/24 h) | 25 / 20 W — **SUPUESTO por medir** | 200 … 2000 Wh | "perfil PQS de referencia (E003-066, 0.85 kWh/24 h); B y C por medir" |

* `python3 scenarios.py` → `out/` (como siempre). `python3 scenarios.py --perfil pqs_ref` → `out/pqs_ref/`.
* Los CSV del perfil didactico salen **byte a byte iguales** que antes de esta fase (comprobado por md5 al hacer el punto 1): los 88 tests y el firmware no se enteran de que existen los perfiles.
* Los mapas llevan el perfil en el subtitulo ("Perfil PQS de referencia — …") y el pie empieza diciendo de que perfil es.

## 2. Las fuentes (y lo que NO dicen)

Las tres fueron verificadas por el autor. En la pagina llevan etiqueta **FUENTE**, con la URL entera a la vista y la salvedad al lado.

| Clave | Perfil | Valor | Fuente |
|---|---|---|---|
| `a_w` | PQS | 35 W | PQS E003-066 — "0.85 kWh/24 h continuo ≈ 35 W; un solo modelo AC" |
| `t_lim_c` | los dos | 7.5 °C | PQS E003-RF-021 — "vacunas +2 a +8 °C; el holdover PQS se mide hasta +10 °C; 7.5 °C es nuestro margen" |
| `cortes_mes` | los dos | **1.3** (antes 2) | IndexMundi / World Bank — "Guatemala 1.3 cortes/mes, 2017, empresas; no da duración" |

`tests/test_calc_js.py:URLS_PERMITIDAS` lista esas tres una a una y comprueba que en `calc.js` no haya ninguna otra URL: ni en notas, ni en origenes, ni en valores. El resto de campos sigue con **SUPUESTO** o **SUPUESTO — por citar**, y `docs/FUENTES_PENDIENTES.md` tiene ahora una tabla "Con fuente" y deja el resto como pendiente.

`cortes_mes` = 1.3 solo mueve la vida estimada de la bateria (19.2 años en vez de 12.5 con 300 ciclos): no entra en los barridos.

## 3. La nota del forro de hielo

La misma frase, en tres archivos, comparada por una prueba:

> Aplica a neveras sin forro de hielo (holdover corto). Las neveras PQS con forro de hielo tienen un holdover de horas a días y necesitan menos ayuda.

* `calc/calc.js: NOTA_HOLDOVER` (sale tambien en el resumen que se copia)
* `calc/index.html`: a la vista, antes de las tarjetas y sin depender del modulo
* `server/static/index.html`: en la tarjeta de "Horas protegidas" del panel

## 4. Cuanto cambia la mejora (%) entre perfiles (S2a)

Misma tabla, mismos ejes; lo unico que cambia es el juego de supuestos. **A igualdad de bateria (300 Wh útiles, la mayor del didactico):**

| Carga no critica | didáctico (300 Wh) | PQS (300 Wh) | Diferencia |
|---|---|---|---|
| 0 % | +0.0 % | +0.0 % | 0.0 pp |
| 20 % | +14.8 % | +23.2 % | +8.4 pp |
| 40 % | +40.0 % | +60.4 % | +20.3 pp |
| 60 % | +99.6 % | +129.8 % | +30.2 pp |
| 80 % | +373.4 % | +305.0 % | **−68.4 pp** |

**Al tope de cada perfil (didactico 300 Wh / PQS 2000 Wh):**

| Carga no critica | didáctico 300 | PQS 2000 | Diferencia |
|---|---|---|---|
| 40 % | +40.0 % | +34.0 % | −6.0 pp |
| 80 % | +373.4 % | +275.5 % | −97.9 pp |

**Resumen de la tabla entera:**

| Perfil | Filas | Media | Minimo | Maximo |
|---|---|---|---|---|
| `didactico` | 408 | +51.4 % | +0.0 % (24 Wh, 0 % no crítica) | +373.4 % (300 Wh, 80 %) |
| `pqs_ref` | 323 | +45.7 % | +0.0 % (200 Wh, 0 %) | +373.2 % (1300 Wh, 80 %) |

Como se lee esto:

* **La mejora no es una propiedad de ClinicKeep, es del cociente entre la nevera y el resto de la carga.** Por eso 35 W no dan "más mejora" ni "menos": dan otra forma.
* Con la nevera PQS (A grande, 35 W) priorizar ayuda **mas** que en la maqueta mientras la carga no critica es moderada (hasta +30 pp a igual batería), porque B + C se comen la bateria del didactico muy rapido.
* Con **bateria grande** la mejora se aplana: si sin ClinicKeep ya se aguanta el corte, no hay nada que ganar (de ahi el −98 pp al tope del PQS a 80 %).
* El maximo es el mismo en los dos (~+373 %), solo que el didactico lo alcanza a 300 Wh y el PQS a 1300 Wh.

## 5. Que se toco, punto por punto

| Punto | Commit | Que entro |
|---|---|---|
| 1 | `ec7b740` | `Perfil` + `PERFILES` en `scenarios.py`, `--perfil`, `out/pqs_ref/`, titulo y pie por perfil en `plots.py`, 6 pruebas |
| 2 | `4a81556` | `PERFILES` y `FUENTES` en `calc.js`, selector de perfil (y `?perfil=`), etiqueta FUENTE con enlace visible, `cortes_mes` 1.3, `test_calc.mjs --perfil`, `publish_calc.py` compara perfiles |
| 3 | `a26528b` | `NOTA_HOLDOVER` en la calculadora (modulo + HTML) y en el panel |
| 4 | `48b3ae8` | `docs/FUENTES_PENDIENTES.md` con la tabla "Con fuente" y la prueba que la vigila |
| 5 | *(este resumen)* | CSV de los dos perfiles regenerados, `test_calc.mjs` para los dos, informe de S2a |
| 6 | | Capturas en `evidence/` y push a `origin/main` |

### Archivos nuevos

| Archivo | Que es |
|---|---|
| `docs/resumen-fase4b.md` | Este resumen |
| `evidence/calc_perfil_didactico.png` | La calculadora con el perfil didactico |
| `evidence/calc_perfil_pqs_ref.png` | La calculadora con el perfil PQS (a_w = 35 W con su enlace) |
| `evidence/panel_nota_holdover.png` | El panel con la nota fija |

## 6. Lo que sigue sin fuente

Todo lo de las tablas 2 y 3 de `docs/FUENTES_PENDIENTES.md`: potencia de B y C del perfil PQS (25 / 20 W, dichos como SUPUESTO por medir), bateria (nominal, profundidad, ciclos), cargador, duracion del corte, ambiente, `tau`, T_HI y el margen de `t_lim_c`. Nada de eso se invento: esta declarado y listado.

Y la salvedad termica de siempre: esta maqueta no tiene forro de hielo, asi que su holdover es corto y con una nevera PQS de verdad estos numeros se quedan cortos.
