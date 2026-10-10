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

## Cómo correrlo en Linux

```
cd clinickeep
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
pytest -q          # deben pasar las 14 pruebas
python3 demo.py    # tabla del corte y comparación con/sin ClinicKeep
```

## Reglas de diseño

1. **A (nevera) nunca se corta por software.** `relay_a` siempre es `True`.
2. **El shedding es monótono** durante un corte: B no se reabre hasta que vuelva la red.
3. **Temporizadores en tiempo real; energía en tiempo simulado** (`k`, el reloj SIM).
4. **Tiempo seguro = autonomía de A + holdover**, ambos en el mismo reloj.
5. Si falla el sensor de potencia con la red caída: modo conservador (se abren B y C, A sigue).
   Si falla el de temperatura: solo desaparece el holdover.

## Cómo correr en Wokwi

El proyecto está en `wokwi/` (ESP32 DevKit C V4 + MicroPython). Incluye copias de
`config.py` y `policy.py` (manténlas alineadas con la raíz del repo).

### En wokwi.com (importar)

1. Crea un proyecto **MicroPython ESP32** en [wokwi.com](https://wokwi.com).
2. Copia al proyecto: `diagram.json`, `main.py`, `config.py`, `policy.py`, `ssd1306.py`.
3. Pulsa Start. En la OLED deberías ver `NORMAL`, SoC, B/C y el badge `SIM x1`.
4. Demo manual:
   - Interruptor deslizante (GPIO34): izquierda = hay red; derecha = corte.
   - Pulsador rojo **CORTE** (GPIO14): atajo para simular caída de red.
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
