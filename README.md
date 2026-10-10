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

## Para usarlo en Wokwi (MicroPython)

Copia `config.py` y `policy.py` al proyecto de Wokwi y llama a `policy.step(...)` en
el lazo principal cada 200-500 ms. Mantén `policy.py` simple (sin dataclasses ni
anotaciones de tipos) para que siga siendo compatible con MicroPython.

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
