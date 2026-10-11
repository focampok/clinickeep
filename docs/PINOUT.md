# Pinout del banco de pruebas

Generado por `tools/gen_pinout.py` a partir de `wokwi/diagram.json`. No lo edites
a mano: cambia el diagrama (o `SIGNALS` en el script) y vuelve a correrlo.

Niveles de los relés: `1` = abierto (carga sin energía, estado seguro),
`0` = cerrado (carga con energía). Ver `docs/RELAY_CHECK.md`.

| Señal | GPIO | Componente | Pin | Nota |
|---|---|---|---|---|
| Red: hay red / corte | GPIO34 | sw_grid (wokwi-slide-switch) | 2 | Interruptor deslizante. Nivel alto = hay red. |
| Potencia de la zona A | GPIO35 | pot_a (wokwi-potentiometer) | SIG | Potenciómetro. **Emula el INA219 (hardware FUTURO).** |
| Temperatura de la nevera | GPIO4 | temp1 (wokwi-ds18b20) | DQ | DS18B20 por OneWire, con pull-up de 4.7 kΩ. |
| Relé zona B (luces de pasillo) | GPIO26 | relay_b (wokwi-relay-module) | IN | 1 = abierto = carga **sin** energía. |
| Relé zona C (sala de espera) | GPIO27 | relay_c (wokwi-relay-module) | IN | 1 = abierto = carga **sin** energía. |
| Buzzer (alarma) | GPIO25 | bz1 (wokwi-buzzer) | 2 | PWM. Suena en CRITICO y con fallo del sensor. |
| Botón k (reloj SIM) | GPIO13 | btn_k (SIM k) | 1.r | Pulsador azul o tecla K: cicla k = 1 / 60 / 600. |
| Botón CORTE manual | GPIO14 | btn_outage (CORTE manual) | 1.r | Pulsador rojo o tecla G. Solo manual; el CI usa GRID0/GRID1. |
| I2C SDA (OLED) | GPIO21 | oled1 (board-ssd1306) | SDA | SSD1306 128x64 en la dirección 0x3C. |
| I2C SCL (OLED) | GPIO22 | oled1 (board-ssd1306) | SCL | SSD1306 128x64 en la dirección 0x3C. |

La zona A (nevera de vacunas) **no tiene relé**: es la carga crítica y el software
nunca la corta (`relay_a` siempre es `true`). Por eso no aparece un GPIO de salida para A.

## INA219: hardware futuro, no está en la simulación

El **INA219** (sensor de corriente y voltaje de la zona A) es **hardware FUTURO**.
**Wokwi no tiene ese componente.** En la simulación la medición de potencia de A se
**emula con un potenciómetro** en GPIO35, siempre detrás de la capa de abstracción
(`read_power_a_w()` en `wokwi/main.py`): cuando exista el INA219 real, se reemplaza
solo esa función y la política no se toca.
