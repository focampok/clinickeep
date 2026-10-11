# Esquema de ingesta: qué emite el firmware y qué acepta el servidor

El servidor **no define un esquema paralelo**: acepta lo que `wokwi/main.py`
imprime por serie en `emit_json()`. Este documento es el mapeo campo → origen.

**Fase 3b (actual): 16 campos.** El firmware pasó de 11 a 16 al emitir también
`grid_ok`, `alarm`, `aut_total_h`, `temp_c` y `temp_ok`. El servidor los acepta
como **opcionales**, así que un evento del formato antiguo (11 campos) sigue
validando y guardándose.

## Líneas que emite el firmware

| Forma | Origen | `tools/serial_to_ingest.py` |
|---|---|---|
| `{"boot":"clinickeep","relays":"open"}` | ventana de arranque seguro | ignora |
| `{"boot_ready":true}` | fin de la ventana de arranque | ignora |
| `{"cmd":"GRID0"}` / `{"cmd":"GRID1"}` / `{"cmd":"GRID"}` / `{"cmd":"K","k":600}` | eco de comandos por serie | ignora |
| estado (16 campos, ver abajo) | `emit_json()`, cada 1 s | **reenvía** |

## Estado aceptado por `POST /ingest`

Validado con Pydantic y `extra="forbid"`: cualquier campo de más devuelve 422.

| Campo | Tipo | Origen real | Desde |
|---|---|---|---|
| `t_ms` | int ≥ 0 | `ticks_ms()` del ESP32 | Fase 3 |
| `k` | float > 0 | factor del reloj SIM (1/60/600) | Fase 3 |
| `mode` | enum (6 modos) | `policy.step()` → `out["mode"]` | Fase 3 |
| `soc` | float 0…1 | `policy.step()` → `out["soc"]` | Fase 3 |
| `relay_a` | bool | `out["relay_a"]` (siempre `true`) | Fase 3 |
| `relay_b` | bool | `out["relay_b"]` | Fase 3 |
| `relay_c` | bool | `out["relay_c"]` | Fase 3 |
| `aut_a_h` | float \| null | `out["aut_a_h"]` | Fase 3 |
| `holdover_h` | float \| null | `out["holdover_h"]` | Fase 3 |
| `safe_h` | float \| null | `out["safe_h"]` | Fase 3 |
| `events` | list[str] ≤ 50 | `out["events"]` | Fase 3 |
| `grid_ok` | bool \| null | `out["grid_ok"]` (red ya filtrada) | **Fase 3b** |
| `alarm` | bool \| null | `out["alarm"]` (`critical or fault`) | **Fase 3b** |
| `aut_total_h` | float \| null | `out["aut_total_h"]` | **Fase 3b** |
| `temp_c` | float \| null | `_last_temp`: lectura del DS18B20, `null` sin lectura | **Fase 3b** |
| `temp_ok` | bool \| null | `_temp_ok` | **Fase 3b** |

Los cinco de la Fase 3b son `None` por defecto en el modelo y `NULL` en SQLite
cuando el evento es del formato antiguo (el servidor migra solo las columnas que
falten, sin perder eventos). El servidor añade, ya fuera del firmware,
`ts_server` (reloj del servidor) y `simulado: true`.

## Ojo con `temp_c`: es el AMBIENTE, no la caja

`_last_temp` es la lectura del DS18B20 y entra a `policy.step(t_amb_c=...)`, es
decir, es la **temperatura ambiente** que usa el modelo de enfriamiento
(`holdover_h`). En la maqueta el DS18B20 del `diagram.json` está fijado a 25 °C.

`T_HI_C = 5.0` y `T_LIM_C = 7.5` (`config.py`) son umbrales de la **caja de la
nevera**, que no tiene sensor propio en la maqueta. El dashboard dibuja esas dos
líneas sobre la serie como referencia, pero **no** son un control: comparar 25 °C
de ambiente contra 7.5 °C de caja mezcla magnitudes distintas, y así se explica
en pantalla. T_HI/T_LIM siguen siendo SUPUESTOS.

## Campos que el dashboard deriva (respaldo)

Con un firmware antiguo (o un evento ya guardado de 11 campos) faltan `grid_ok` y
`alarm`, así que el dashboard los deriva del `mode` — con la misma fórmula de
`policy.py` — y lo etiqueta como *derivado*; cuando llegan del firmware, usa el
valor nativo y lo etiqueta como *nativo*.

| Campo | Si no llega | Cómo se deriva |
|---|---|---|
| `grid_ok` | eventos antiguos | hay red si `mode in (NORMAL, RESTAURACION)` |
| `alarm` | eventos antiguos | suena si `mode in (CRITICO, FALLO_SENSOR)` |
| `temp_c` | eventos antiguos | no se puede: la tarjeta dice "no disponible" |
