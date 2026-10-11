# Verificación de relés (polaridad del pin y estado seguro)

Punto 1 de `PROMPT_correcciones.md`. Todo lo de abajo está **medido en el simulador**,
no copiado de la documentación.

- Simulador: Wokwi (ESP32 DevKit C V4 + MicroPython), proyecto `wokwi/`.
- Herramientas: MCP de Wokwi (`start_simulation`, `read_pin`, `set_control`) y
  `wokwi-cli 0.28.1` con `expect-pin`.
- Circuito: `relay_*:COM` → 3V3, `relay_*:NO` → LED → 220 Ω → GND. Con el contacto
  cerrado el nodo NO queda atado a 3V3; con el contacto abierto queda **flotante**.

## Qué hace el atributo `transistor`

`wokwi-relay-module` acepta `transistor: "npn"` o `"pnp"`. Se comparó el mismo pin
en el mismo estado lógico cambiando solo ese atributo:

| `transistor` | Nivel en `IN` (GPIO26) | Contacto COM-NO | Carga |
|---|---|---|---|
| `pnp` | BAJO (0) | **cerrado** | con energía |
| `pnp` | ALTO (1) | abierto | sin energía |
| `npn` | ALTO (1) | **cerrado** | con energía |

Conclusión: **el atributo invierte la polaridad de la entrada.** `pnp` es activo en
bajo; `npn` es activo en alto. La documentación no lo dice explícitamente y el
comentario original del firmware lo tenía al revés.

### Cómo se midió (y por qué es fiable)

La medición decisiva es **diferencial y en el mismo instante**: en CORTE la política
deja `relay_b = true` y `relay_c = false`, y el firmware ponía el pin 26 en ALTO y el
27 en BAJO. Leídos a la vez:

```
GPIO26 = 1  ->  relay_b:NO = 0 (flotante)
GPIO27 = 0  ->  relay_c:NO = 1 (atado a 3V3 = contacto cerrado)
```

Un contacto cerrado ata NO a 3V3, así que leer **1 prueba que el contacto cerró**.
La lectura opuesta (flotante) no es una prueba por sí sola: Wokwi la reporta como
`undefinedV` y su valor no es determinista. Por eso la conclusión se apoya en el
lado "1" de cada comparación.

> Aviso para futuras pruebas: `expect-pin` sobre `relay_*:NO` **no es determinista**
> cuando el contacto está abierto (nodo flotante). Una aserción `relay_b:NO == 0`
> puede fallar de forma espuria. Por eso el escenario de CI aserta solo GPIO.

Evidencia visual: `evidence/corte_led_b.png` y `evidence/corte_led_c.png`. Los LEDs
cuelgan del contacto NO, pero a 16×16 px el encendido no se distingue con claridad
en el PNG; no se usan como prueba.

## El fallo encontrado

`apply_outputs()` traducía `True` (carga CON energía) a nivel **ALTO**, y con
`transistor: pnp` el nivel alto **abre** el relé. La lógica salía invertida:

| Estado | Política | Contacto medido (antes) | Esperado |
|---|---|---|---|
| NORMAL | B,C = true | B abierto, C abierto | cerrados |
| CORTE | B = true, C = false | B abierto, C **cerrado** | B cerrado, C abierto |

Es decir: en NORMAL no había energía en las cargas no críticas, y en CORTE se
sheddeaba el relé equivocado (seguía con energía C, que es la que se quería quitar).
Además, la inicialización `value=0` ponía los relés en el nivel **activo** tanto al
arrancar.

## La corrección

En `wokwi/main.py`, en **un solo lugar**:

```python
RELAY_ACTIVE_LEVEL = 0                       # nivel que CIERRA (energiza) el relé
RELAY_OPEN_LEVEL = 1 - RELAY_ACTIVE_LEVEL    # nivel SEGURO: carga sin energía
```

- `apply_outputs()` usa esas dos constantes y nada más.
- Los dos pines se llevan al **nivel abierto antes de cualquier otra inicialización**
  (antes del watchdog, del ADC, del I²C y del OLED).
- Si algún día se cambia el `transistor` a `npn`, se cambia **solo**
  `RELAY_ACTIVE_LEVEL` a `1`.

Además se añadió una **ventana de arranque seguro** (`BOOT_GUARD_MS = 2000`): los
relés de B y C quedan abiertos hasta que la política tome su primera decisión, para
no energizar cargas no críticas antes de tener lecturas válidas. El firmware emite
`{"boot":"clinickeep","relays":"open"}` al entrar en la ventana y
`{"boot_ready":true}` al salir.

## Verificación posterior

`wokwi/scenario_accept.yaml` aserta el nivel del GPIO en cada estado, incluido el
arranque. Corrida en verde (`evidence/wokwi_accept_cli.log`, `EXIT=0`, 12 aserciones):

| Momento | `esp:26` (B) | `esp:27` (C) | Significa |
|---|---|---|---|
| Arranque (ventana segura) | 1 | 1 | ambas cargas sin energía |
| NORMAL | 0 | 0 | ambas con energía |
| CORTE | 0 | 1 | B con energía, C sin energía |
| AHORRO | 1 | 1 | ambas sin energía |
| CRITICO | 1 | 1 | ambas sin energía |
| NORMAL tras restaurar | 0 | 0 | ambas con energía |

## Hardware real

En el ESP32 real los pines quedan en alta impedancia al resetear. Antes de conectar cargas, verificar con multímetro que el módulo de relé real interpreta ese estado como relé abierto; si no, añadir una resistencia pull-up/pull-down según la hoja de datos del módulo. En simulación se usa transistor: pnp (activo en bajo).

## Pendiente / recomendación

Con `pnp` el estado seguro es el nivel **alto**, que no es el estado natural del pin
del ESP32 al resetear (queda en alta impedancia). Hoy no hay riesgo medido —en la
ventana de reset el contacto queda abierto— pero para el hardware real es más robusto
usar `transistor: "npn"` (activo en alto): así "sin energía" coincide con el estado
por defecto del pin. **No se cambió** porque el prompt pide corregir el nivel activo
en el firmware; si se decide pasar a `npn`, basta con cambiar esa única constante y el
atributo en `diagram.json`.
