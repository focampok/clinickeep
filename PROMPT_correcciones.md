# Prompt para el agente: 4 correcciones a la Fase 1 (Wokwi)

Contexto: repo ClinicKeep con carpeta `wokwi/` (ESP32 MicroPython, diagram.json, wokwi.toml, escenarios).
Raíz del repo = fuente de verdad de `policy.py` y `config.py`. No toques la lógica de la política.
Trabaja un punto por commit. Al terminar de cada punto corre `pytest -q` y reporta el resultado.

## 1. Verificar que los relés están ABIERTOS al arrancar y en CORTE (seguridad)
- Con el MCP de Wokwi: inicia la simulación, lee el pin de cada relé (GPIO26 = B, GPIO27 = C) y toma captura
  - justo tras el arranque con red presente,
  - en CORTE con la red caída (B y C deben quedar DESACTIVADOS = cargas sin energía),
  - en modo AHORRO/CRITICO.
- Aclara empíricamente qué hace el atributo `transistor` (npn/pnp) del relé en diagram.json: no confíes en la
  documentación. Documenta en `docs/RELAY_CHECK.md`: nivel del pin, LED/estado del relé y conclusión.
- Si la lógica resulta invertida (relé energizado cuando debía estar abierto), corrige el nivel activo en UN
  solo lugar del firmware (constante `RELAY_ACTIVE_LEVEL`) y, además, deja el pin en el nivel "abierto"
  ANTES de cualquier otra inicialización en `main.py`.
- Añade al escenario de CI las aserciones `expect-pin` (verifica la sintaxis en la documentación de wokwi-cli)
  para: relés abiertos al boot y relés abiertos en CORTE.

## 2. Una sola fuente para policy.py / config.py
- `wokwi/policy.py` y `wokwi/config.py` NO se editan a mano. `build_firmware.py` (o `make sync`) los copia desde la raíz.
- Copia a `tests/` el archivo `tests/test_sync.py` entregado (compara bytes de la raíz vs `wokwi/`).
- Si hoy difieren, la raíz manda; sincroniza y commitea.

## 3. Interruptor vs. pulsador de CORTE (GPIO14)
- Para el VIDEO/demo manual en wokwi.com: usa el interruptor deslizante (slide switch) como red presente/caída.
- Para CI: no uses el pulsador; usa comandos serie `GRID0` / `GRID1` (ya soportados) en el escenario YAML.
- Elimina el pulsador de CORTE de diagram.json si duplica la función, o márcalo en el README como "solo manual".
- Añade `docs/DEMO_CHECKLIST.md` con los pasos manuales (qué mover, qué debe mostrarse en OLED/relés/buzzer).

## 4. Pinout limpio y aclaración del INA219
- Genera `docs/PINOUT.md` con un script (`tools/gen_pinout.py`) leyendo `diagram.json`; tabla: señal, GPIO, componente.
  Esperado: GPIO34 red, GPIO35 potencia A (potenciómetro, emula INA219), GPIO4 DS18B20, GPIO26 relé B,
  GPIO27 relé C, GPIO25 buzzer, GPIO13 botón k (reloj SIM), I2C SDA=21 / SCL=22 (OLED SSD1306).
- Deja escrito en PINOUT.md y README: "INA219 es hardware FUTURO; Wokwi no tiene ese componente; en la simulación
  se emula con un potenciómetro tras la capa de abstracción".
- Esquema Cirkit: actualiza etiquetas para que coincidan exactamente con PINOUT.md; marca INA219 como "futuro".
  Si no puedes editar Cirkit, exporta el esquema como tabla/diagrama en `docs/` y avísame.

Entrega: lista de commits, resultados de pytest, y capturas/lecturas de pines del punto 1.
