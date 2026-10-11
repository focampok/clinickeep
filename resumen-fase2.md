# Resumen — Fase 2: fusión del motor de escenarios y correcciones de la Fase 1

**Fecha:** 11 oct 2026
**Repo:** ClinicKeep (`clinickeep`)
**Alcance:** (A) fusionar `clinickeep-core.zip` con el repo y (B) ejecutar las 4 correcciones de `PROMPT_correcciones.md`.
**Estado:** árbol limpio salvo `PLAN.md` y `resumen-fase1.md` (previos). `pytest -q`: **33 passed**. Escenario de aceptación: **EXIT=0**.

---

## 1. Contexto

Dos encargos en la misma sesión:

1. **Fusionar** el zip `clinickeep-core.zip` (motor de escenarios S2/S3) con el código actual, **sin** reemplazar el repo y **sin** tocar `wokwi/` ni `.git`.
2. **Ejecutar** `PROMPT_correcciones.md`: 4 correcciones a la Fase 1, **un commit por punto**, con `pytest -q` al final de cada uno.

El zip se descomprimió en `/tmp/ck-nuevo` (fuera del repo), nunca encima.

---

## 2. Parte A — Fusión del zip

### 2.1 Comparación y decisiones

`diff -rq` más verificación por **md5**, archivo por archivo. Los cuatro archivos compartidos resultaron **idénticos byte a byte**, así que **no hubo ningún conflicto que decidir**:

| Archivo | md5 raíz vs zip |
|---------|-----------------|
| `config.py` | `8b71edd7…` igual |
| `demo.py` | `92ba88fe…` igual |
| `policy.py` | `6adb3fff…` igual |
| `tests/test_policy.py` | `20ec5135…` igual |

Copiados del zip (nuevos): `scenarios.py`, `plots.py`, `tests/test_scenarios.py`, `tests/test_sync.py`. `PROMPT_correcciones.md` ya estaba en el repo **con md5 idéntico** → no se copió nada.

### 2.2 README

No se sobrescribió. Solo se **añadió**: 5 filas a la tabla de archivos y la sección «Escenarios (supuestos, NO datos medidos)». Tu sección «Cómo correr en Wokwi» quedó intacta.

Dos divergencias del README del zip **no aplicadas** (habrían borrado contenido tuyo) y que siguen pendientes de tu decisión:

- El zip elimina la sección «Cómo correr en Wokwi» (las ~40 líneas de Wokwi CLI, criterios de aceptación y `evidence/`) y la reemplaza por 3 líneas genéricas. Es una versión anterior a tus commits del 10-oct.
- El zip cambia `pip install pytest` → `pip install pytest matplotlib` y «deben pasar las 14 pruebas» → «28 pasan». La línea actual quedó desactualizada (ya son 33).

### 2.3 Verificación del motor de escenarios

`python3 scenarios.py --out out` → 3 CSV + 3 PNG. Los **3 CSV son byte a byte idénticos** a los del zip (reproducibilidad confirmada). Los PNG difieren ~20 % en tamaño por versión de matplotlib/fuentes; el contenido del gráfico es el mismo.

`out/` y `.venv/` añadidos a `.gitignore`. El zip se borró del repo. `out/` no entra al commit.

---

## 3. Parte B — Punto 1: polaridad de los relés (seguridad)

### 3.1 Qué hace `transistor` (medido, no leído en la doc)

| `transistor` | Nivel en `IN` (GPIO26) | Contacto COM-NO | Carga |
|---|---|---|---|
| `pnp` | BAJO (0) | **cerrado** | con energía |
| `pnp` | ALTO (1) | abierto | sin energía |
| `npn` | ALTO (1) | **cerrado** | con energía |

**El atributo invierte la polaridad de la entrada.** `pnp` es activo en bajo; `npn` es activo en alto.

### 3.2 Medición fiable

La medición decisiva es **diferencial y en el mismo instante**: en CORTE la política deja `relay_b = true` y `relay_c = false`, y el firmware ponía 26 en ALTO y 27 en BAJO:

```
GPIO26 = 1  ->  relay_b:NO = 0 (flotante)
GPIO27 = 0  ->  relay_c:NO = 1 (atado a 3V3 = contacto cerrado)
```

Un contacto cerrado ata NO a 3V3, así que **leer 1 prueba que cerró**. El lado opuesto queda flotante, Wokwi lo reporta como `undefinedV` y **su valor no es determinista** → no sirve como objetivo de aserción (una aserción `relay_b:NO == 0` falla de forma espuria; se comprobó).

### 3.3 El fallo

`apply_outputs()` traducía «carga con energía» a nivel **alto**, que con `pnp` **abre** el relé: la lógica salía invertida.

| Estado | Política | Contacto medido (antes) | Esperado |
|---|---|---|---|
| NORMAL | B,C = true | B abierto, C abierto | cerrados |
| CORTE | B = true, C = false | B abierto, C **cerrado** | B cerrado, C abierto |

Es decir: en NORMAL no había energía en las cargas no críticas, y en CORTE se sheddeaba el relé equivocado. Además `value=0` en la inicialización ponía los relés en el nivel **activo** al arrancar.

### 3.4 La corrección

En `wokwi/main.py`, en **un solo lugar**:

```python
RELAY_ACTIVE_LEVEL = 0                       # nivel que CIERRA (energiza) el relé
RELAY_OPEN_LEVEL = 1 - RELAY_ACTIVE_LEVEL    # nivel SEGURO: carga sin energía
```

- `apply_outputs()` usa esas dos constantes y nada más.
- Los dos pines van al **nivel abierto antes de cualquier otra inicialización** (antes del watchdog, ADC, I²C y OLED).
- Se añadió **ventana de arranque seguro** (`BOOT_GUARD_MS = 2000`): B y C quedan abiertos hasta la primera decisión de la política. Emite `{"boot":…,"relays":"open"}` al entrar y `{"boot_ready":true}` al salir.

### 3.5 Verificación posterior

12 aserciones `expect-pin` en `wokwi/scenario_accept.yaml`, corrida en verde (`EXIT=0`):

| Momento | `esp:26` (B) | `esp:27` (C) | Significa |
|---|---|---|---|
| Arranque (ventana segura) | 1 | 1 | ambas sin energía |
| NORMAL | 0 | 0 | ambas con energía |
| CORTE | 0 | 1 | B con energía, C sin energía |
| AHORRO | 1 | 1 | ambas sin energía |
| CRITICO | 1 | 1 | ambas sin energía |
| NORMAL tras restaurar | 0 | 0 | ambas con energía |

Evidencia: `docs/RELAY_CHECK.md`, `evidence/wokwi_accept_cli.log`, `evidence/corte_led_{b,c}.png`.

---

## 4. Parte B — Punto 2: una sola fuente para `policy.py` / `config.py`

- `wokwi/build_firmware.py` ahora **copia** `policy.py` y `config.py` desde la raíz antes de empaquetar, y avisa si tuvo que sobrescribir. Flag `--sync-only` para sincronizar sin empaquetar.
- Probado: se inyectó divergencia en `wokwi/policy.py` y el script la restauró desde la raíz ("la raíz manda").
- `tests/test_sync.py` (venía en el zip) falla si vuelven a divergir. **Pasa**: las copias estaban y siguen idénticas.

---

## 5. Parte B — Punto 3: interruptor vs. pulsador de CORTE

- **CI**: el corte y la restauración se provocan con `GRID0` / `GRID1` por serie, no con el pulsador. El log muestra `{"cmd":"GRID0"}` y `{"cmd":"GRID1"}`.
- **Demo manual / video**: el control es el **interruptor deslizante**.
- `diagram.json`: el pulsador rojo pasó a llamarse **"CORTE manual"** (se conserva: es útil si no se quiere mover el interruptor, y el interruptor no tiene automation control). Marcado como solo-manual en el README.
- Nuevo `docs/DEMO_CHECKLIST.md`: pasos manuales y qué debe verse en OLED, LEDs y buzzer, incluido el paso 0 (ventana de arranque seguro).

---

## 6. Parte B — Punto 4: pinout y INA219

- **`tools/gen_pinout.py`** deriva GPIO, componente y pin de `wokwi/diagram.json`; los nombres de señal son intención de diseño y viven en el script. Genera dos documentos y **avisa si la tabla y el circuito se desincronizan**.
- **`docs/PINOUT.md`**: GPIO34 red · GPIO35 potencia A (potenciómetro) · GPIO4 DS18B20 · GPIO26 relé B · GPIO27 relé C · GPIO25 buzzer · GPIO13 botón k · GPIO14 botón CORTE manual · I²C SDA 21 / SCL 22 (OLED).
- La zona A se marca como **sin relé** (nunca se corta por software).
- **INA219 declarado hardware FUTURO** en `PINOUT.md` y en el README: Wokwi no tiene ese componente; en la simulación se **emula con un potenciómetro** detrás de la capa de abstracción (`read_power_a_w()`), así que al integrarlo se reemplaza solo esa función y la política no se toca.
- **`docs/SCHEMA.md`**: exportación del esquema en texto (Mermaid + todas las conexiones), con las mismas etiquetas que `PINOUT.md`.
- **`tests/test_pinout.py`**: falla si los docs no coinciden con el diagrama (verificado inyectando basura).
- **Cirkit: no se pudo editar.** No hay acceso desde este entorno y el proyecto solo aparece referenciado en `PLAN.md` (no hay artefacto Cirkit en el repo). Se exportó el esquema a `docs/SCHEMA.md` y se avisa aquí, como pedía el prompt. Proyecto: <https://app.cirkitdesigner.com/project/4e224752-621d-45eb-b841-17e5f0f924d7>

---

## 7. Pruebas

| Momento | `pytest -q` |
|---|---|
| Tras la fusión del zip (30 pruebas) | **30 passed** |
| Tras los 4 puntos | **33 passed** (30 + 3 de `test_pinout.py`) |

`test_sync` pasa: no hubo que sincronizar nada porque las copias de `wokwi/` ya eran idénticas a la raíz. El punto 2 del prompt partía de la sospecha de que diferían; **no era el caso**.

---

## 8. Commits de la sesión

```
b7ee13b Fusiona motor de escenarios (S2/S3) y pruebas de sincronización
8662c67 Corrige la polaridad de los relés y aserta el estado seguro en CI
2c1995b Sincroniza policy.py y config.py desde la raíz antes de empaquetar
bada522 Desacopla el CI del pulsador: corte por serie y checklist manual
5e4b33a Documenta el pinout generándolo desde diagram.json
```

Total: 21 archivos, +1363 / −97.

---

## 9. Archivos creados / tocados

| Ruta | Rol |
|------|-----|
| `scenarios.py`, `plots.py` | Motor de escenarios S2/S3 y mapas de calor (del zip) |
| `tests/test_scenarios.py`, `tests/test_sync.py` | Pruebas del motor y de la sincronización |
| `tests/test_pinout.py` | Detecta deriva entre docs y `diagram.json` |
| `tools/gen_pinout.py` | Genera `docs/PINOUT.md` y `docs/SCHEMA.md` |
| `docs/RELAY_CHECK.md` | Polaridad de los relés y estado seguro (medido) |
| `docs/DEMO_CHECKLIST.md` | Pasos de la demo manual |
| `docs/PINOUT.md`, `docs/SCHEMA.md` | Pinout y esquema (generados) |
| `wokwi/main.py` | Nivel activo único + ventana de arranque seguro |
| `wokwi/scenario_accept.yaml` | 12 aserciones `expect-pin`; corte por serie |
| `wokwi/build_firmware.py` | Sincroniza desde la raíz; `--sync-only` |
| `wokwi/diagram.json` | Etiqueta del pulsador → "CORTE manual" |
| `README.md` | Filas de tabla, sección de escenarios, enlaces a `docs/`, nota del INA219 |
| `.gitignore` | `out/` |
| `evidence/` | Logs de aceptación (serial y CLI) y capturas de LED |

No modificados: `policy.py`, `config.py`, `demo.py`, `tests/test_policy.py` (raíz) y la lógica de `policy.py`.

---

## 10. Cómo reproducir

```bash
cd clinickeep
python3 -m venv .venv && source .venv/bin/activate
pip install pytest matplotlib

pytest -q                        # 33 passed
python3 scenarios.py --out out   # CSV + PNG de S2a, S2b, S3
python3 tools/gen_pinout.py      # docs/PINOUT.md y docs/SCHEMA.md
cd wokwi && python3 build_firmware.py
export WOKWI_CLI_TOKEN=wok_...
wokwi-cli . --scenario scenario_accept.yaml --timeout 120000   # exit 0
```

---

## 11. Decisiones pendientes y limitaciones

### Pendientes de tu decisión

1. **Semántica de CORTE.** El prompt dice "en CORTE (B y C deben quedar DESACTIVADOS)". Eso no coincide con la política: hasta `T_RESERVA_H` solo se abre C; B se abre en AHORRO. No se tocó la política y se asertó el comportamiento real. Si querías que B cayera ya en CORTE, es un cambio de política.
2. **`pnp` vs `npn`.** Se dejó `pnp` porque el prompt pedía corregir el firmware. Pero con `pnp` el estado seguro es el nivel **alto**, que no es el estado natural del pin al resetear (alta impedancia). Para el hardware real es más robusto `npn` (activo en alto): "sin energía" coincide con el estado por defecto. Cambiarlo = el atributo en `diagram.json` + `RELAY_ACTIVE_LEVEL = 1`.
3. **`BOOT_GUARD_MS = 2000`.** Va más allá del pedido literal. Sin esa ventana no se puede asertar "abiertos al boot": a los 0 ns el pin está en alta impedancia y no se distingue de un pin forzado a bajo.
4. **README del zip.** Las dos divergencias de §2.2 siguen sin aplicar.
5. **`PLAN.md` (modificado) y `resumen-fase1.md` (sin trackear)** quedaron fuera de los commits, por no ser parte de estas tareas.

### Limitaciones

1. **El MCP de Wokwi se desconectó** a mitad de la tarea. Las mediciones iniciales son por MCP; toda la verificación final, por `wokwi-cli`. Los logs quedan en `evidence/`.
2. **El nodo COM-NO no es asertable** cuando el contacto está abierto (flotante, `undefinedV`). Por eso el CI aserta GPIO, que sí es determinista.
3. **Capturas de LED no concluyentes**: `evidence/corte_led_{b,c}.png` son de 16×16 px y no distinguen encendido de apagado. No se usaron como prueba; la evidencia es la medición diferencial.
4. **Cirkit no editable** desde aquí (§6).
5. **`firmware.bin` no se versiona** (4 MB, gitignored): hay que regenerarlo con `build_firmware.py` para CLI/MCP.
6. **Escenarios S2/S3**: siguen siendo análisis de sensibilidad con **supuestos**, no datos medidos.

---

## 12. Próximos pasos naturales

- Decidir §11.1–11.3 y, si aplica, un commit de seguimiento.
- Sustituir el potenciómetro por el INA219 real cuando exista el hardware (solo `read_power_a_w()`).
- Alinear el esquema de Cirkit con `docs/PINOUT.md` (no se pudo desde aquí).
- Según `PLAN.md`: dashboard, ingesta HTTP, calculadora, video de demo.
