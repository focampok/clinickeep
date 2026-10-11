# Resumen — Fase 1: proyecto Wokwi (ESP32 / MicroPython)

**Fecha:** 10 oct 2026  
**Repo:** ClinicKeep (`clinickeep`)  
**Alcance:** solo el proyecto de simulación en Wokwi que ejecuta la política; sin dashboard, ingesta HTTP ni motor de escenarios.

---

## 1. Contexto

Se pidió:

1. Revisar si el MCP de Wokwi estaba bien configurado.
2. Leer `PLAN.md` (secciones 3–6) y `README.md`.
3. Crear el proyecto Wokwi en `wokwi/` que ejecute `policy.py` / `config.py` (sin cambiar su comportamiento).
4. Verificar criterios de aceptación en el simulador.
5. Commits pequeños + sección «Cómo correr en Wokwi» en el README + lista de lo no verificado.

`policy.py` y `config.py` en la raíz **no se modificaron**. Copias en `wokwi/` para el filesystem de MicroPython. `pytest -q`: **14 passed**.

---

## 2. MCP de Wokwi — configuración

| Check | Resultado |
|-------|-----------|
| Estado del namespace | `ready` |
| Config | `~/.cursor/mcp.json` → `command: wokwi-cli`, `args: ["mcp"]`, env `WOKWI_CLI_TOKEN` |
| CLI | `wokwi-cli` 0.28.1 en `/home/focampo/bin/wokwi-cli` |
| Prueba | `wokwi_get_status` respondió (`running: false` al inicio) |

Hubo un fallo temprano en logs (10:23) por token faltante; tras añadir el token (10:25) conectó bien.

**Nota de seguridad:** el token queda en texto plano en `mcp.json`; conviene rotarlo si el archivo se compartió.

### Herramientas MCP listadas

| Herramienta | Uso |
|-------------|-----|
| `wokwi_start_simulation` | Arrancar simulación (ruta del proyecto) |
| `wokwi_stop_simulation` | Detener |
| `wokwi_restart_simulation` | Reiniciar |
| `wokwi_resume_simulation` | Reanudar |
| `wokwi_get_status` | Estado (running, nanos, project) |
| `wokwi_read_pin` | Leer pin de una parte |
| `wokwi_read_serial` | Leer monitor serie |
| `wokwi_write_serial` | Escribir al serie |
| `wokwi_set_control` | Controles (botón, pot, etc.) |
| `wokwi_take_screenshot` | Captura de display (p. ej. OLED) |
| `wokwi_export_vcd` | Exportar VCD |

**Capacidad clave:** permiten **ejecutar** un proyecto existente; **no** crean el diagrama. Los archivos de `wokwi/` se generaron a mano con nombres de [docs.wokwi.com](https://docs.wokwi.com).

---

## 3. Arquitectura de la fase (PLAN §3–6, recorte)

```
[Wokwi: ESP32 + firmware MicroPython]
  entradas:  interruptor red · pot P_A · DS18B20 · botón k · (CI: botón CORTE)
  salidas:   relé B · relé C · OLED SSD1306 · LEDs · buzzer
  lazo:      policy.step(...) cada ~500 ms
```

Principios respetados: el borde decide; una sola política (`policy.py` compatible con MicroPython); badge `SIM ×k` visible.

---

## 4. Circuito (`wokwi/diagram.json`)

Nombres de partes según documentación Wokwi:

| Pieza | Tipo Wokwi | GPIO / notas |
|-------|------------|--------------|
| ESP32 DevKit C V4 | `board-esp32-devkit-c-v4` | — |
| Red (slide switch) | `wokwi-slide-switch` | GPIO34; izq=3V3 (hay red), der=GND |
| Potencia A | `wokwi-potentiometer` | GPIO35; 0–20 W (`value`≈409 ≈ 8 W) |
| Temperatura | `wokwi-ds18b20` + `wokwi-resistor` 4.7 kΩ | GPIO4 |
| Relé zona B | `wokwi-relay-module` (`transistor: pnp`) | GPIO26; LED verde en NO |
| Relé zona C | `wokwi-relay-module` (`transistor: pnp`) | GPIO27; LED amarillo en NO |
| OLED | `board-ssd1306` I2C 0x3c | SDA 21, SCL 22 |
| Alarma | `wokwi-buzzer` | GPIO25 |
| Factor k | `wokwi-pushbutton` (`btn_k`) | GPIO13; cicla 1→60→600 |
| CORTE (CI/MCP) | `wokwi-pushbutton` (`btn_outage`) | GPIO14; el slide switch **no** tiene automation control |

Cargas: B = 4 W y C = 3 W constantes si su relé está cerrado; `p_total = p_a + cargas activas`. Zona A sin relé.

---

## 5. Firmware (`wokwi/main.py`)

Al arrancar:

1. Relés B y C **abiertos** (`IN` bajo; módulo pnp → NO abierto).
2. Watchdog (`WDT`, 8 s).
3. Lazo ~500 ms: `dt` con `ticks_ms`, lee entradas, `policy.step(...)`, aplica `relay_b` / `relay_c`, OLED, alimenta WDT.
4. Fallo DS18B20 → `temp_ok=False`; el lazo no se detiene.
5. OLED: modo, SoC, B/C, AutA, Safe, badge `SIM xK` siempre.
6. Cada ~1 s: línea JSON por serie (`t_ms`, `k`, `modo`, `soc`, relés, `aut_a_h`, `holdover_h`, `safe_h`, `events`).

Comandos serie opcionales (CI): `GRID0` / `GRID1` / `GRID`, `K=1` / `K=60` / `K=600`.

Empaquetado CLI/MCP: `build_firmware.py` descarga MicroPython ESP32 y mete los `.py` en LittleFS → `firmware.bin` (gitignored).

---

## 6. Criterios de aceptación (verificados)

Corrida automatizada:

```bash
cd wokwi && python3 build_firmware.py
wokwi-cli . --scenario scenario_accept.yaml --timeout 120000
```

Resultado: **Scenario completed successfully** (exit 0).  
Log: `evidence/wokwi_accept_serial.log`.

| # | Criterio | Resultado |
|---|----------|-----------|
| 1 | Con red: B y C cerrados, modo NORMAL | **OK** |
| 2 | Al cortar: ~2 s reales → C abre, modo CORTE | **OK** (~2.0 s) |
| 3 | Con k=600: ~12 s → AHORRO (B abre); ~60 s → CRITICO + alarma | **OK** (~12 s / ~62 s desde k=600) |
| 4 | A nunca se abre (`relay_a` siempre true) | **OK** |
| 5 | Al volver la red: 5 s → cierra B; +3 s → cierra C; NORMAL | **OK** (T_RESTORE_S + T_STAGGER_S) |

Transiciones observadas (t_ms aproximados de esa corrida):

```
NORMAL → CORTE → AHORRO → CRITICO → RESTAURACION → NORMAL
```

---

## 7. Commits de la sesión

```
f5c66ce Añadir circuito Wokwi ESP32 (diagrama y empaquetado MicroPython).
288d51b Ejecutar la política ClinicKeep en firmware MicroPython para Wokwi.
6b98550 Añadir escenario de aceptación Wokwi y log de evidencia.
33f3922 Documentar cómo correr ClinicKeep en Wokwi.
```

(Más este documento `resumen-fase1.md` si se commitea después.)

---

## 8. Archivos tocados / creados

| Ruta | Rol |
|------|-----|
| `wokwi/diagram.json` | Circuito |
| `wokwi/wokwi.toml` | Apunta a `firmware.bin` |
| `wokwi/build_firmware.py` | MicroPython + LittleFS |
| `wokwi/main.py` | Lazo firmware |
| `wokwi/ssd1306.py` | Driver OLED (micropython-lib) |
| `wokwi/config.py`, `wokwi/policy.py` | Copias para el simulador |
| `wokwi/scenario_accept.yaml` | Escenario CI |
| `wokwi/.gitignore` | `firmware.bin`, binarios MicroPython |
| `evidence/wokwi_accept_serial.log` | Evidencia de la corrida |
| `README.md` | Sección «Cómo correr en Wokwi» |

No cambiados: `policy.py`, `config.py`, `tests/`, `demo.py` (raíz).

---

## 9. Cómo correr (resumen)

### wokwi.com

1. Proyecto MicroPython ESP32.
2. Copiar `diagram.json`, `main.py`, `config.py`, `policy.py`, `ssd1306.py`.
3. Start; usar interruptor / botones / pot; JSON en el monitor serie.

### CLI / MCP

```bash
cd wokwi
pip install littlefs-python
python3 build_firmware.py
export WOKWI_CLI_TOKEN=wok_...   # https://wokwi.com/dashboard/ci
wokwi-cli . --scenario scenario_accept.yaml --timeout 120000
```

---

## 10. Lo que no se pudo verificar / limitaciones

1. **Slide switch con `set_control` del MCP:** no mueve el interruptor (no figura entre partes con automation controls). Para CI se usó el pulsador **CORTE** (GPIO14) y/o comandos serie.
2. **Import visual en wokwi.com:** no se abrió el proyecto en el navegador; solo CLI/MCP + lint local.
3. **Lint:** avisos informativos de tipos «undocumented» (`board-esp32-devkit-c-v4`, `wokwi-ds18b20`) pese a ser los nombres de la documentación oficial.
4. **OLED:** captura MCP tomada; no hay diff automatizado contra una imagen de referencia.
5. **`firmware.bin`:** no versionado (4 MB); hay que regenerarlo con `build_firmware.py` para CLI/MCP. En wokwi.com no hace falta: la web monta los `.py` del proyecto.
6. **Fuera de alcance (a propósito):** dashboard, ingesta HTTP, motor de escenarios, LoRaWAN, calculadora.

---

## 11. Próximos pasos naturales (no hechos en esta fase)

Según `PLAN.md`: ingesta a Railway + dashboard; motor de escenarios (S2/S3); calculadora; evidencia ampliada; video de demo. Mantener una sola política compartida entre firmware y motor.
