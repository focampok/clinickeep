# Fuentes pendientes de la calculadora (Fase 4)

Qué es esto: la calculadora de `calc/` no tiene **ningún** dato medido, y sus
valores por defecto están marcados como tales en la propia página. Este archivo
es la lista de lo que hay que citar para que esos números dejen de ser
supuestos, con lo que haría falta para cada uno.

Detalle deliberado: aquí **no hay ninguna URL**. No he inventado citas ni
enlaces. Cuando tengas la fuente, se escribe en la columna que corresponda y se
cambia la etiqueta del campo en `calc/calc.js` (`DEFAULTS[clave].etiqueta`).

Las fórmulas no necesitan cita: están validadas contra `tests/test_scenarios.py`
y `policy.py`. Lo que falta es de dónde salen los **números de entrada**.

---

## 1. Sin ninguna fuente: los elige esta calculadora

| Clave | Por defecto | Qué es | Etiqueta | Qué haría falta para citarlo |
|---|---|---|---|---|
| `nominal_wh` | 128 Wh | Capacidad nominal del paquete de baterías | SUPUESTO — por citar | Ficha técnica del paquete instalado. Ojo: con `dod_pct` = 75 % tiene que dar los 96 Wh útiles de `config.py: E_UTIL_WH` (o cambiar también ese valor) |
| `dod_pct` | 75 % | Profundidad de descarga útil | SUPUESTO — por citar | Ficha de ciclado del fabricante (curva ciclos vs profundidad) o el criterio de instalación |
| `ciclos` | 300 ciclos | Ciclos completos que admite la batería | SUPUESTO — por citar | Ficha técnica de la batería (plomo-ácido suele andar por cientos; LiFePO4, por miles). El cálculo asume **un ciclo por corte**, que es conservador |
| `cortes_mes` | 2 cortes/mes | Cortes de red al mes | SUPUESTO — por citar | Histórico de la distribuidora o del propio sitio. Es del lugar, no del equipo |
| `cargador_w` | 30 W | Potencia del cargador | SUPUESTO — por citar | Placa del cargador que se vaya a instalar |

## 2. Copiados del repo, pendientes igualmente de fuente externa

Estos salen tal cual de `scenarios.py` o `config.py`, donde ya están declarados
como supuestos de partida. La columna `origen` de `calc.js` dice de qué archivo
se copiaron. Se etiquetan **SUPUESTO** porque son de dónde son, pero siguen sin
tener detrás una medición ni un fabricante.

| Clave | Por defecto | Origen en el repo | Qué haría falta para citarlo |
|---|---|---|---|
| `a_w` | 8 W | `scenarios.py: A_W` | Medir el consumo medio de la nevera (vatímetro o la placa del equipo); es la carga que manda en todo el dimensionamiento |
| `b_w` | 4 W | `scenarios.py: B_W` | Medir las luces de pasillo, o sustituir por su vatios reales |
| `c_w` | 3 W | `scenarios.py: C_W` | Medir la sala de espera |
| `d_h` | 12 h | `scenarios.py: sweep_s2a(d_h=12)` | Duración del corte que se quiere cubrir: histórico de la zona |
| `eta` | 0.85 | `scenarios.py: ETA_CHARGE` | Curva de carga del fabricante del cargador/batería |
| `t_amb_c` | 25 °C | `scenarios.py: T_AMB_C` | Temperatura del sitio donde va la nevera (idealmente, un registro) |
| `tau_h` | 4 h | `config.py: TAU_H` | Constante de tiempo de la nevera: ficha técnica o ensayo de caída de temperatura |
| `t_hi_c` | 5.0 °C | `config.py: T_HI_C` | Consigna de la nevera (techo de la banda de control) |
| `t_lim_c` | 7.5 °C | `config.py: T_LIM_C` | Banda de conservación de vacunas (2–8 °C) según la norma/guía que aplique, menos el margen del sensor |

## 3. Qué NO es esto

* No es una predicción de cortes: no hay datos medidos ni serie histórica.
* `t_lim_c` sale de la banda 2–8 °C que ya está en `config.py`; el 7.5 es el
  8 °C menos un margen de sensor. La referencia de esa banda **está sin citar**
  (ver fila anterior).
* La vida de la batería (`vida_anios`) supone un ciclo completo por corte. Con
  cortes cortos, eso subestima la vida real; con cortes largos y batería
  pequeña, se acerca.
* El modelo térmico es de masa concentrada (una sola `tau`), no un modelo
  térmico de la caja real.

## 4. Cómo se comprueba que esto sigue siendo cierto

`tests/test_calc_js.py` (se salta si no hay `node`) comprueba que:

1. cada campo de `DEFAULTS` tiene etiqueta y que la etiqueta es una de las
   conocidas (`SUPUESTO`, `SUPUESTO — por citar`);
2. los campos marcados «por citar» aparecen en este archivo, en la tabla 1;
3. **todos** los campos aparecen en este archivo (que no se quede ninguno sin
   revisar);
4. `origen`, cuando no es `null`, apunta a un archivo que existe de verdad en el
   repo, y ninguna etiqueta lleva una URL escrita a mano.
