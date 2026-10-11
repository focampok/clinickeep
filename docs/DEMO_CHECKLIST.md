# Checklist de demo manual (Wokwi)

Para el video / demo en [wokwi.com](https://wokwi.com) o con el MCP. El corte se
provoca con el **interruptor deslizante**; el pulsador rojo es un atajo manual y el
escenario de CI **no** lo usa (ahí el corte va por serie con `GRID0` / `GRID1`).

Recuerda: `config.py` y `policy.py` son copias de la raíz del repo. Si tocas la
política, corre `python3 wokwi/build_firmware.py` antes de simular.

## Antes de empezar

1. Proyecto `wokwi/` abierto (ESP32 DevKit C V4 + MicroPython).
2. `firmware.bin` reconstruido si cambió algún `.py`:
   `python3 wokwi/build_firmware.py`.
3. Monitor serie visible (imprime un JSON por segundo).

## Pasos

| # | Qué haces | Qué debe verse |
|---|---|---|
| 0 | Pulsa Start | ~2 s con **ambas cargas sin energía** (ventana de arranque seguro) y luego `NORMAL`. Es lo esperado y es la propiedad de seguridad. |
| 1 | Interruptor a la **izquierda** (hay red) | OLED: `NORMAL`, `SoC 100%`, `B:ON C:ON`, badge `SIM x1`. LEDs verde (B) y amarillo (C) **encendidos**. Serie: `"mode": "NORMAL"`, `relay_b`/`relay_c` en `true`. |
| 2 | Interruptor a la **derecha** (corte) | A los ~2 s: modo `CORTE`. El LED amarillo (C, sala de espera) se **apaga**; el verde (B) sigue encendido. Serie: `events: ["grid_down","shed_c"]`. |
| 3 | Pulsa **SIM k** (o tecla `K`) hasta `SIM x600` | El reloj simulado corre ×600. A los ~12 s: modo `AHORRO` y el LED verde (B) se **apaga**: las dos cargas no críticas quedan sin energía. |
| 4 | Espera | A los ~60 s (reales) desde el corte: modo `CRITICO` y **suena el buzzer**. A (nevera) **nunca** se apaga. |
| 5 | Interruptor de vuelta a la **izquierda** (vuelve la red) | A los ~5 s: `RESTAURACION` y el LED verde (B) se enciende. 3 s después se cierra C (`NORMAL`, ambos LEDs encendidos). El buzzer se apaga. |
| 6 | Gira el potenciómetro (GPIO35) | Cambia la potencia de A (0–20 W; ~40 % ≈ 8 W). Con más potencia, el corte llega antes a `AHORRO`. |

El pulsador rojo **CORTE manual** (o la tecla `G`) hace lo mismo que el paso 2 sin
mover el interruptor. Si el interruptor ya está en "hay red", el pulsador manda:
mientras está pulsado, la red se considera caída.

## Qué NO debería pasar nunca

- Que la zona A se quede sin energía por decisión del software: `relay_a` siempre
  es `true` y A no tiene relé.
- Que B se reabra y se vuelva a cerrar durante un corte (el shedding es monótono).
- Que al arrancar las cargas no críticas queden con energía antes de la primera
  decisión de la política (ventana de arranque seguro).

## Comandos serie útiles

`GRID0` (sin red) · `GRID1` (hay red) · `GRID` (vuelve a leer el interruptor) ·
`K=1` · `K=60` · `K=600`.

Son los que usa `wokwi/scenario_accept.yaml` para el corte y la restauración.
