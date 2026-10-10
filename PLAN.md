# ClinicKeep v4 — plan "simulación primero" (IAS Global Energy Hackathon 2026)

**Evento:** [hackathon.anneru.com](https://hackathon.anneru.com/) · virtual · vie 30 oct – dom 1 nov 2026 (~48 h; horario exacto sin publicar)
**Zona horaria de trabajo:** America/Guatemala (UTC−6)
**Versión:** v4 (9 oct 2026). Reemplaza el enfoque de maqueta física de v2/v3 por firmware real ejecutado en simulación (Wokwi), un gemelo digital y evidencia por escenarios.

---

## 0. Qué cambia respecto a v3

| Cambio | Motivo |
|---|---|
| **Sin maqueta física obligatoria.** El firmware del ESP32 corre en Wokwi | Cero inversión, menos riesgo, se puede aprender sin quemar nada |
| **Track y pilar definidos** (sección 2) | Coherencia con lo que realmente se entrega |
| **Evidencia por escenarios** (cientos de combinaciones) en vez de una sola corrida física | En simulación se puede barrer duración del corte, proporción de cargas y tamaño de batería |
| **Capa de abstracción de sensores** (`readPowerW()`, `readTempC()`) | En simulación leen potenciómetros; en hardware real leerían INA219 y DS18B20 sin cambiar la política |
| **Sin calibración física** del gemelo térmico | Los parámetros vienen de fichas técnicas o rangos declarados, con análisis de sensibilidad |
| **Ingesta por HTTP(S) a Railway** (o MQTT público con prefijo aleatorio) | Se elimina la dependencia de la Pi y del broker propio |
| **LoRaWAN como arquitectura de reporte**, sin simularlo | Respuesta a "¿y si no hay Wi-Fi ni celular?" sin inflar el alcance |
| **Uso del MCP de Wokwi** por el agente | Edita el proyecto, compila y ejecuta escenarios de forma repetible (sección 6) |

---

## 1. Pitch e hipótesis

> ClinicKeep es una **política de prioridad de energía** para clínicas con cortes: cuando cae la red, apaga primero lo que puede esperar, mantiene la nevera de vacunas y avisa al personal **cuánto tiempo seguro queda y cuándo actuar**. La decisión se toma en el borde (firmware), sin internet.

**Hipótesis falsable:** *con la misma energía disponible, priorizar la nevera de vacunas aumenta las horas de cadena de frío protegida frente a no priorizar, y la mejora depende de cuánta carga no crítica exista.*

**KPI único:** horas de cadena de frío protegida, con y sin ClinicKeep, bajo el mismo escenario.

**Qué es el producto:** (1) una política de prioridad ejecutada por firmware, (2) un gemelo digital que estima autonomía y tiempo seguro, (3) un dashboard y una calculadora de dimensionamiento y costo, y (4) la evidencia por escenarios que respalda la hipótesis.

**Lo que NO promete:**
- No genera energía ni garantiza 24 h por sí solo; con cortes largos la limitante es la fuente.
- No es un dispositivo certificado ni sustituye el protocolo de cadena de frío de salud.
- La validación es en simulación; el prototipo físico es el siguiente paso.

---

## 2. Registro, track y pilar

| Campo | Elección | Razón |
|---|---|---|
| **Track (Primary Interest)** | **Digital Solutions, Apps & AI/ML Tools** | El entregable es firmware en simulación, gemelo digital, dashboard y herramienta de dimensionamiento. El track de hardware espera un dispositivo nuevo o una brecha en modelos existentes (su ejemplo es un inversor solar) y un prototipo físico; con solo simulación sería difícil de defender |
| **Pilar** | **Availability** | Casi literal con el ejemplo oficial: instituciones críticas (hospitales) con cortes largos y necesidad de refrigeración y equipo médico |
| **Cliente** | **Non-residential (salud)** | Puesto de salud o clínica |
| Ángulo secundario | **Access** | "Clínica sin red": si la red no existe, "grid down" equivale a "generación insuficiente" y la misma política aplica. Se menciona en el pitch, no se reclama como pilar principal |

**Notas:**
- El ejemplo de la tarjeta de Digital (app educativa) es una ilustración, no un límite del track. No uses lenguaje de IA/ML si no hay ML: el gemelo térmico es físico y la política es determinista.
- Si más adelante añades una prueba física mínima (el ESP32 que ya tienes con relés y OLED), el track de hardware se vuelve defendible, pero no es necesario para este plan.
- No sé si el campo "Primary Interest" se puede cambiar después del registro. Explica el enfoque en la descripción del proyecto.
- Al elegir mentor, prioriza perfiles de sistemas embebidos, almacenamiento o energía para salud.

---

## 3. Arquitectura

```
[Wokwi: ESP32 con firmware real]
   entradas simuladas:  interruptor = "red" · potenciómetro = potencia de A · DS18B20 = temperatura · interruptor = ingesta online/offline
   salidas simuladas:   relé B · relé C · OLED SSD1306 · LEDs de zona · buzzer
        │  HTTP(S) POST con token (JSON)
        ▼
[Railway: API de ingesta + dashboard público de solo lectura (SSE) + calculadora estática]
        ▲
[Motor de escenarios (TypeScript o Python)]  ← mismo algoritmo de política que el firmware
        │  genera mapas de calor y gráficos de la hipótesis

(Hoja de ruta, no simulado)  ESP32 --LoRaWAN--> gateway compartido --> supervisor distrital
```

**Principios:**
1. **El borde decide.** La política vive en el firmware; el dashboard solo muestra.
2. **El video no puede depender de Railway.** Graba la ventana de Wokwi con la OLED y el dashboard local como respaldo.
3. **Una sola política.** Mantén la lógica en un módulo pequeño (funciones puras) y reproduce los mismos casos canónicos en el motor de escenarios; compara resultados para validar el modelo contra el firmware.

---

## 4. Mapa de hardware simulado (Wokwi)

| Pieza real (futura) | Pieza en Wokwi | Nota |
|---|---|---|
| ESP32 | ESP32 DevKit | Firmware Arduino (C++) |
| Detección de red (divisor al ADC) | Interruptor deslizable o potenciómetro en GPIO 34 | ADC1, no ADC2 |
| INA219 (potencia de A y total) | Potenciómetro | El INA219 no aparece en la lista de partes de Wokwi; se emula tras la capa de abstracción |
| DS18B20 (caja y ambiente) | DS18B20 | Temperatura ajustable desde la interfaz |
| Relés B y C | Módulo de relé | Contactos NO |
| OLED | SSD1306 128×64 I2C | Estado local sin internet |
| Alarma | Buzzer + LED rojo/verde | Verifica que la pieza esté disponible |
| Batería real | **Modelo en software** + reloj SIM ×k | La energía se integra a partir de la potencia simulada |

**Capa de abstracción (en el código):**
```cpp
float readPowerA_W();     // sim: potenciómetro · real: INA219 #2
float readPowerTotal_W(); // sim: suma de zonas activas · real: INA219 #1
float readBoxTempC();     // sim/real: DS18B20
bool  readGridOk();       // sim: interruptor · real: divisor + ADC
void  setRelay(char zone, bool on);
```
Con esto, pasar a hardware real cambia solo estas funciones.

---

## 5. Firmware y política

### 5.1 Máquina de estados

| Estado | Condición | Acción |
|---|---|---|
| NORMAL | red presente y estable ≥ `T_RESTORE_S` | A, B y C encendidas |
| CORTE | red ausente ≥ `T_DEBOUNCE_S` (1–2 s) | abrir C; iniciar contabilidad de energía |
| AHORRO | CORTE y `autonomía_total < T_RESERVA` | abrir B |
| CRÍTICO | AHORRO y `tiempo_seguro < T_ACT_MIN` | A permanece; buzzer y OLED: "mover vacunas en X h Y min" |
| RESTAURACIÓN | red vuelve estable | cerrar B, esperar `T_STAGGER_S`, cerrar C (escalonado) |
| FALLO_SENSOR | sensor de potencia sin lectura ≥ 3 veces | con red presente: solo alarma; con red caída: conservador (abrir B y C, mantener A) |

- **Umbrales por autonomía, no por SoC fijo:** `T_RESERVA` es el número de horas de A que quieres garantizar.
- Un fallo del sensor de temperatura **solo** desactiva el holdover (muestra "n/d"), nunca el shedding.
- **A nunca se corta por software.** Histéresis en todos los umbrales. Parámetros en un solo bloque `config.h`.
- La alerta se expresa como **duración**, no como hora (sin NTP no hay hora real fiable).

### 5.2 Reloj de simulación ×k
- `E_usada += P_total × dt × K`. `K = horas_simuladas × 3600 / segundos_de_demo`.
- Badge `SIM ×k` y reloj simulado siempre visibles en OLED y dashboard; decirlo en voz en el video.
- Modo LIVE (K = 1) disponible para mostrar lecturas sin aceleración.

### 5.3 Estimadores
- **Autonomía de A** = energía restante ÷ potencia actual de A. Se reporta también "con shedding" y "sin shedding".
- **Tiempo seguro total** = autonomía de A + holdover térmico, **ambos en el mismo reloj**.
- **Holdover** = `τ · ln((Ta − T_HI) / (Ta − T_LIM))`, desde la temperatura al apagarse A (límite superior de la banda de control).

### 5.4 Robustez
- Buffer circular de ~20 eventos en RAM que se envía en orden al reconectar la ingesta.
- Watchdog. Persistencia del estado en memoria no volátil si el simulador lo permite (opcional).
- Ingesta con token en cabecera y `boot_id` + `t_ms` para reconstruir el orden de eventos.

---

## 6. Uso del MCP de Wokwi con el agente

- Usa el agente para editar el proyecto (sketch y definición del circuito), compilar y ejecutar casos, según las herramientas que exponga tu MCP. Revisa su lista de capacidades antes de depender de ellas.
- Define **casos canónicos** (sección 8) con entradas y salidas esperadas por puerto serie. Si tu entorno admite escenarios automatizados de Wokwi (en su CLI), úsalos como pruebas de regresión; verifica límites y precios del plan gratuito, porque parte de la integración con CI estaba en beta.
- Guarda **logs de cada corrida** (serie con marcas de tiempo) en `evidence/`.
- Para el barrido de escenarios usa el motor de escenarios (TypeScript/Python), no cientos de ejecuciones del simulador.
- Verifica en los términos de Wokwi que el uso en un hackatón sea aceptable.

---

## 7. Gemelo térmico (sin calibración física)

- Modelo de masa concentrada: `T(t) = Ta + (T0 − Ta)·e^(−t/τ)`. Estado ON: la temperatura se mantiene en la banda de control. Estado OFF: sube con τ.
- **Parámetros:** toma el holdover de fichas técnicas de neveras de vacunas (o de la precalificación OMS/PQS del equipo) y cítalo. Si no puedes citar un valor, **declara un rango** y haz análisis de sensibilidad.
- **Honestidad:** es un modelo con parámetros de referencia, no una medición propia. En el pitch: "estimación basada en datos de ficha técnica; en campo se calibra por equipo".
- En un equipo con compresor, el holdover desde el techo de la banda es corto: es la red de seguridad final. El grueso del tiempo lo da la fuente.

---

## 8. Evidencia por escenarios

| ID | Experimento | Qué se reporta |
|---|---|---|
| S1 | Latencia de diseño: evento de red → relé C abierto (marcas en el log de la simulación) | Valor de diseño por antirrebote; **no** una medición de hardware |
| S2 | Barrido: duración del corte (8–20 h) × proporción de cargas no críticas × tamaño de batería | Mapa de calor de **horas protegidas con y sin ClinicKeep** y dónde el beneficio es despreciable |
| S3 | Chequeo de recarga: horas de red por día × potencia del cargador | Zona donde la batería **no alcanza a recargar** y se requiere solar o generador |
| S4 | Ingesta caída en pleno corte | El shedding continúa; el buffer vuelca los eventos sin pérdidas |
| S5 | Fallo de sensor de potencia o de temperatura | Estados seguros esperados |
| S6 | Validación cruzada: 5 casos canónicos en firmware vs. motor de escenarios | Diferencias máximas entre ambos |

**Son análisis de sensibilidad con supuestos declarados, no predicción de cortes.** Cada gráfico lleva su tabla de supuestos.

---

## 9. Calculadora de dimensionamiento y costo (página estática)

**Entradas:** cargas por zona (W), horas de corte por día, horas con red, política de shedding, eficiencia, profundidad de descarga, química de batería, **vida útil en ciclos**, precio por kWh, potencia del cargador, diésel (L/h, precio por litro, mantenimiento).

**Salidas:**
1. Energía diaria **con** y **sin** shedding, y el ahorro (puede ser pequeño; mostrarlo).
2. `Batería_kWh = E_dia ÷ (DoD × η)`.
3. **Chequeo de recarga:** `E_dia ÷ η_carga ≤ P_cargador × t_red`.
4. Costo por kWh entregado ≈ `precio_kWh ÷ (ciclos × DoD)` + energía de recarga.
5. Comparación con generador diésel.
6. Horas de cadena de frío protegida con y sin shedding.

Sin cifras sin fuente en el submit; los supuestos son visibles.

---

## 10. Reporte con LoRaWAN (arquitectura, no simulado)

**Para qué:** un puesto sin Wi-Fi ni celular avisa a un supervisor distrital. **Es un canal de reporte, no de control.**

**Por qué encaja:** el alcance típico es 2–5 km en zonas urbanas y 5–15 km en rurales (más de 15 km con línea de vista); la carga útil es pequeña (11–242 bytes según región y velocidad) y hay límites de ciclo de trabajo, así que se envían eventos y un latido periódico, no flujos continuos. Necesita un gateway que conecte con la nube, y un gateway puede atender a muchos nodos.

**Paquete de ejemplo (9 bytes, cabe en el mínimo de 11):**

| Byte | Contenido |
|---|---|
| 0 | Estado (4 bits) + banderas (4 bits: red, B, C, alarma) |
| 1 | SoC % (0–100) |
| 2–3 | Potencia de A (0.1 W, uint16) |
| 4–5 | Temperatura de la caja (0.01 °C, int16) |
| 6–7 | Tiempo seguro (minutos, uint16) |
| 8 | Contador de secuencia |

**Modelo de negocio asociado:** un gateway compartido entre varios puestos de un distrito. Confirma el plan de frecuencias y la cobertura local antes de prometer nada.

---

## 11. Guion de demo remota (~2:00–2:30)

| Tiempo | Qué se ve |
|---|---|
| 0:00–0:10 | Problema del reto: hospitales con 8–20 h de corte; vacunas en riesgo |
| 0:10–0:25 | Pantalla dividida: Wokwi (ESP32, OLED, relés) y dashboard. Decir: "el firmware es real; la planta está simulada y el tiempo está acelerado (SIM)" |
| 0:25–0:40 | Estado NORMAL: tres zonas activas, temperatura en banda |
| 0:40–0:55 | Clic en el interruptor de red: C se apaga; estado CORTE |
| 0:55–1:15 | La autonomía baja (SIM): se apaga B; A sigue. Autonomía, holdover y total visibles |
| 1:15–1:30 | **Ingesta apagada** (interruptor): el firmware sigue decidiendo; al reconectar aparecen los eventos |
| 1:30–1:45 | ALERTA CRÍTICA: buzzer y "mover vacunas en X h Y min" |
| 1:45–2:00 | Mapa de calor S2: horas protegidas con y sin ClinicKeep, y dónde el beneficio es pequeño |
| 2:00–2:15 | Calculadora: chequeo de recarga y costo frente a diésel |
| 2:15–2:30 | Cierre: hoja de ruta (prototipo físico, LoRaWAN) y límites declarados |

Respaldo: la misma secuencia pregrabada en 1080p. Grabar cada escena con dos tomas.

---

## 12. Inversión

- **Obligatorio:** Q0 (navegador, cuenta gratuita de Wokwi, tu cuenta de Railway).
- **Opcional (prueba física mínima):** tu ESP32, un módulo de relé de 2 canales (~Q35 en Tettsa) y una OLED I2C (~Q49 en Oxdea). Precios vistos en tiendas en línea; confirma existencia.

---

## 13. Plan de trabajo

**Ahora (práctica y preparación, sin riesgo con las reglas):**
- Hitos 0–2 de la guía (fundamentos, ESP32 + relé + LED, OLED + detección de red) **en Wokwi**.
- Investigación y citas: holdover de neveras de vacunas (fichas técnicas), duración típica de cortes, consumo de equipos, costos de baterías y diésel, vida útil en ciclos.
- Si sigues con otro hackatón la semana del 12 al 18 de oct, planea solo repaso esos días.

**No escribas el firmware ni el motor finales hasta que Anneru responda sobre trabajo previo.** Si sigue sin respuesta hacia el 15 de oct, reenvía un correo corto e incluye la pregunta de si una demo en simulación es válida.

**Durante las 48 h:**

| Bloque | Entrega |
|---|---|
| 0–4 h | Proyecto Wokwi: circuito, capa de abstracción, lecturas por serie |
| 4–12 h | Máquina de estados, reloj SIM, OLED, buzzer |
| 12–20 h | Estimadores (autonomía, holdover, tiempo seguro) y casos canónicos |
| 20–28 h | Ingesta a Railway y dashboard |
| 28–36 h | Motor de escenarios (S2, S3) y calculadora |
| 36–44 h | Video (dos tomas), one-pager y descripción en inglés |
| 44–48 h | Revisión de checklist y envío con margen |

**Recortes si vamos tarde (en este orden):** (1) validación cruzada S6 y fallo de sensor S5; (2) calculadora a una hoja con captura; (3) dashboard público (queda el local). **Nunca recortar:** corte → shed → OLED → ingesta apagada → alerta crítica → mapa de calor → video. Dormir al menos 6 h.

---

## 14. Riesgos

| Riesgo | Mitigación |
|---|---|
| "Es solo una simulación" | Declararlo desde el primer segundo; firmware real, abstracción lista para hardware, hoja de ruta física y evidencia por escenarios |
| Track de hardware pierde sentido sin prototipo | Registrarse en Digital; si se añade prueba física, mencionarlo como extra |
| Parámetros térmicos no medidos | Citar fichas técnicas; análisis de sensibilidad; declarar rango |
| Wokwi: límites de plan o términos | Verificar antes; el motor de escenarios no depende del simulador |
| INA219 ausente en Wokwi | Emulación tras la capa de abstracción; la pieza real se prueba después |
| Broker MQTT público (si se usa) | Preferir HTTP con token; si se usa MQTT, prefijo aleatorio y sin datos sensibles |
| LoRaWAN infla el alcance | Solo arquitectura y diapositiva |
| Reglas sobre trabajo previo y sobre demos simuladas | Preguntar a los organizadores y escribir el código principal dentro de las 48 h |
| Beneficio del shedding pequeño | Mostrarlo en S2 como hallazgo honesto, no esconderlo |

---

## 15. Criterio de listo

- [ ] Wokwi: corte → C se abre → B se abre por autonomía → A nunca se corta.
- [ ] Ingesta apagada: el shed continúa y los eventos se recuperan sin pérdidas.
- [ ] ALERTA CRÍTICA con duración (no hora) y buzzer.
- [ ] Badge `SIM ×k` visible y explicado.
- [ ] Mapa de calor S2 y mapa de recarga S3 con tabla de supuestos.
- [ ] Calculadora con fuentes citadas y chequeo de recarga.
- [ ] Dashboard (local y público) con estado, autonomía, holdover, total y motivo de cada evento.
- [ ] Video ~2:00–2:30 y descripción en inglés, con límites declarados y hoja de ruta (prototipo físico, LoRaWAN).

---

## 16. Pendientes con los organizadores

- ¿Se permite trabajo previo (investigación, diseño, prototipos)?
- ¿Es válida una demo en simulación? ¿Se exige prototipo físico en algún track?
- Fecha y hora límite de entrega, duración del video, formato del one-pager.
- ¿Se exige URL pública o basta el video?
- Nombres de las seis categorías de evaluación.

**Plan B:** LuzPAY, solo si el mentor empuja Access/Affordability; ver `luzpay.md`.
