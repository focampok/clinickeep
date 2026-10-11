# ClinicKeep - núcleo de política (paso 1)

Política de prioridad de energía para una clínica con cortes. Está escrita para
correr **igual en MicroPython (ESP32 en Wokwi) y en Python normal**, así el firmware
y el motor de escenarios usan exactamente el mismo código.

## Archivos

| Archivo | Qué es |
|---|---|
| `config.py` | Parámetros (todos son supuestos de partida; citar fuente o declararlos) |
| `policy.py` | Máquina de estados, reloj SIM, autonomía, holdover y tiempo seguro |
| `tests/test_policy.py` | 14 pruebas de la política |
| `demo.py` | Un corte simulado y comparación CON vs SIN ClinicKeep |
| `scenarios.py` | Motor de escenarios S2a/S2b/S3 (usa la misma `policy.step`) -> CSV |
| `plots.py` | Mapas de calor (matplotlib) |
| `tests/test_scenarios.py` | Validación contra fórmula cerrada y monotonía |
| `tests/test_sync.py` | `wokwi/policy.py` y `config.py` idénticos a la raíz |
| `PROMPT_correcciones.md` | Prompt para el agente: 4 correcciones de la Fase 1 |
| `tools/gen_pinout.py` | Genera `docs/PINOUT.md` y `docs/SCHEMA.md` desde el diagrama |
| `docs/PINOUT.md` | Pinout GPIO ↔ señal (generado; no editar a mano) |
| `docs/SCHEMA.md` | Esquema del circuito en texto + enlace al proyecto Cirkit |
| `docs/RELAY_CHECK.md` | Polaridad de los relés y estado seguro (medido en simulador) |
| `docs/DEMO_CHECKLIST.md` | Pasos de la demo manual (qué mover y qué debe verse) |

## Cómo correrlo en Linux

```
cd clinickeep
python3 -m venv .venv
source .venv/bin/activate
pip install pytest matplotlib
pytest -q          # 33 pasan
python3 demo.py    # tabla del corte y comparación con/sin ClinicKeep
```

## Reglas de diseño

1. **A (nevera) nunca se corta por software.** `relay_a` siempre es `True`.
2. **El shedding es monótono** durante un corte: B no se reabre hasta que vuelva la red. Al caer la red se abre **solo C**; **B** se abre en AHORRO, cuando la autonomía total baja de `T_RESERVA_H` (6 h).
3. **Temporizadores en tiempo real; energía en tiempo simulado** (`k`, el reloj SIM).
4. **Tiempo seguro = autonomía de A + holdover**, ambos en el mismo reloj.
5. Si falla el sensor de potencia con la red caída: modo conservador (se abren B y C, A sigue).
   Si falla el de temperatura: solo desaparece el holdover.

## Cómo correr en Wokwi

El proyecto está en `wokwi/` (ESP32 DevKit C V4 + MicroPython). `config.py` y
`policy.py` son **copias de la raíz**: no se editan en `wokwi/`. `build_firmware.py`
las copia antes de empaquetar (con `--sync-only` solo sincroniza), y `tests/test_sync.py`
falla si divergen.

Pinout: `docs/PINOUT.md`. Esquema del circuito: `docs/SCHEMA.md`. Polaridad de los
relés: `docs/RELAY_CHECK.md`. Demo manual paso a paso: `docs/DEMO_CHECKLIST.md`.

**El INA219 es hardware FUTURO.** Wokwi no tiene ese componente: en la simulación la
potencia de la zona A se **emula con un potenciómetro** (GPIO35), siempre detrás de la
capa de abstracción (`read_power_a_w()`). El sensor real va en el bus I²C compartido con
la OLED (dirección 0x40) y en serie con la carga de A; al integrarlo se reemplaza solo
esa función y la política no se toca.

### En wokwi.com (importar)

1. Crea un proyecto **MicroPython ESP32** en [wokwi.com](https://wokwi.com).
2. Copia al proyecto: `diagram.json`, `main.py`, `config.py`, `policy.py`, `ssd1306.py`.
3. Pulsa Start. En la OLED deberías ver `NORMAL`, SoC, B/C y el badge `SIM x1`.
4. Demo manual (paso a paso en `docs/DEMO_CHECKLIST.md`):
   - Interruptor deslizante (GPIO34): izquierda = hay red; derecha = corte.
     **Es el control que se usa en el video.**
   - Pulsador rojo **CORTE manual** (GPIO14) o tecla `G`: atajo para simular la
     caída de red. **Solo manual**: el escenario de CI no lo usa, provoca el corte
     por serie con `GRID0` / `GRID1`.
   - Pulsador azul **SIM k** (GPIO13) o tecla `K`: cicla `k` en 1 → 60 → 600.
   - Potenciómetro (GPIO35): potencia de A (0–20 W); ~40 % ≈ 8 W.
5. El monitor serie imprime JSON cada segundo (`t_ms`, `k`, `mode`, `soc`, relés, etc.).

### Con Wokwi CLI / MCP (local)

```bash
cd wokwi
pip install littlefs-python   # solo para empaquetar el filesystem
python3 build_firmware.py    # descarga MicroPython y genera firmware.bin
export WOKWI_CLI_TOKEN=wok_...   # https://wokwi.com/dashboard/ci
wokwi-cli . --scenario scenario_accept.yaml --timeout 120000
```

Comandos serie opcionales (CI): `GRID0` / `GRID1` / `GRID`, `K=1` / `K=60` / `K=600`.

### Criterios de aceptación (verificados en simulador)

| # | Criterio | Resultado |
|---|---|---|
| 1 | Con red: B y C cerrados, modo NORMAL | OK |
| 2 | Al cortar: ~2 s reales → C abre, modo CORTE | OK (~2.0 s) |
| 3 | Con k=600: ~12 s → AHORRO (B abre); ~60 s → CRITICO + alarma | OK (~12 s / ~62 s) |
| 4 | A nunca se abre (`relay_a` siempre true) | OK |
| 5 | Al volver la red: 5 s → cierra B; +3 s → cierra C; NORMAL | OK |

Log de la corrida: `evidence/wokwi_accept_serial.log`.

## Resultado del demo (supuestos: 96 Wh; A=8 W, B=4 W, C=3 W; holdover 0.53 h)

| | A sin energía | Horas protegidas (con holdover) |
|---|---|---|
| Sin ClinicKeep | 6.4 h | 6.9 h |
| Con ClinicKeep | 11.0 h | 11.5 h |

La mejora (+66 %) depende de cuánta carga no crítica exista: con menos carga en B y C,
el beneficio baja. Ese barrido es el experimento S2 del plan.

## Simplificaciones declaradas

- La batería vuelve a 100 % cuando se restaura la red (la recarga real se modela en el
  chequeo de recarga de la calculadora).
- Los parámetros térmicos (`TAU_H`, límites) son supuestos; hay que tomarlos de la ficha
  técnica de una nevera de vacunas o declarar un rango.

## Escenarios (supuestos, NO datos medidos)

Análisis de sensibilidad, no predicción de cortes. S2a: mejora vs batería y % de carga no crítica (corte 12 h).
S2b: qué cortes cubre la nevera. S3: recarga entre cortes (1 corte/día, eficiencia 0.85).
Hallazgo honesto de S3: casi no depende de ClinicKeep (1 de 156 celdas); depende de duración del corte y del cargador.
