# Esquema de ingesta: qué emite el firmware y qué acepta el servidor

El servidor **no define un esquema paralelo**: acepta exactamente lo que
`wokwi/main.py` imprime por serie en `emit_json()`. Este documento es el mapeo
campo → origen, medido sobre `evidence/wokwi_accept_serial.log`.

## Líneas que emite el firmware

| Forma | Origen | `tools/serial_to_ingest.py` |
|---|---|---|
| `{"boot":"clinickeep","relays":"open"}` | ventana de arranque seguro | ignora |
| `{"boot_ready":true}` | fin de la ventana de arranque | ignora |
| `{"cmd":"GRID0"}` / `{"cmd":"GRID1"}` / `{"cmd":"GRID"}` / `{"cmd":"K","k":600}` | eco de comandos por serie | ignora |
| estado (11 campos, ver abajo) | `emit_json()`, cada 1 s | **reenvía** |

En el log de evidencia hay 75 líneas de estado y 4 de las otras formas.

## Estado aceptado por `POST /ingest`

Validado con Pydantic y `extra="forbid"`: cualquier campo de más devuelve 422.

| Campo | Tipo | Origen real |
|---|---|---|
| `t_ms` | int ≥ 0 | `ticks_ms()` del ESP32 |
| `k` | float > 0 | factor del reloj SIM (1/60/600) |
| `mode` | enum (6 modos) | `policy.step()` → `out["mode"]` |
| `soc` | float 0…1 | `policy.step()` → `out["soc"]` |
| `relay_a` | bool | `out["relay_a"]` (siempre `true`) |
| `relay_b` | bool | `out["relay_b"]` |
| `relay_c` | bool | `out["relay_c"]` |
| `aut_a_h` | float \| null | `out["aut_a_h"]` |
| `holdover_h` | float \| null | `out["holdover_h"]` |
| `safe_h` | float \| null | `out["safe_h"]` |
| `events` | list[str] ≤ 50 | `out["events"]` |

El servidor añade, ya fuera del firmware, `ts_server` (reloj del servidor) y
`simulado: true`.

## Campos que el dashboard pediría y el firmware HOY NO emite

`policy.step()` **sí devuelve** estos campos, pero `emit_json()` en
`wokwi/main.py` no los incluye en el JSON de serie. No se tocó el firmware
(zona excluida por el encargo); el dashboard los marca como no disponibles o
los deriva:

| Campo útil | ¿En `out` de policy? | ¿En el JSON de serie? | Qué hace el dashboard |
|---|---|---|---|
| `alarma` | sí (`alarm`) | **no** | lo **deriva**: `mode in (CRITICO, FALLO_SENSOR)` — es exactamente como `policy` calcula `alarm` |
| `red` (grid_ok) | sí (`grid_ok`) | **no** | lo **deriva**: hay red si `mode in (NORMAL, RESTAURACION)` |
| `temperatura` | no (vive en `_last_temp`, solo entra a `policy.step`) | **no** | muestra **"no disponible"** |
| `aut_total_h` | sí | **no** | no se muestra; se usan `soc`, `aut_a_h` y `holdover_h`, que sí llegan |
| `e_rest_wh` | sí | **no** | no se muestra (equivale a `soc`, que sí llega) |
| `temp_ok` / `power_ok` | flags internos | **no** | no se muestran |

Conclusión: para que el dashboard muestre alarma, red, temperatura y
`aut_total_h` **tal como los calcula la política** habría que añadir esas claves
al dict de `emit_json()` (unas 4 líneas, dentro de `wokwi/main.py`, que este
encargo prohíbe tocar). Se deja reportado.
