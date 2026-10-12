# Fuentes: que esta citado y que no (calculadora, Fase 4b)

Que es esto: la calculadora de `calc/` y el motor de `scenarios.py` no miden
nada, y sus valores por defecto lo dicen en la propia pagina. Este archivo es la
lista de lo que hay que citar para que esos numeros dejen de ser supuestos.

Lo que cambio en la Fase 4b: **tres** campos ya tienen fuente verificada (tabla
1) y el resto sigue declarado como supuesto (tablas 2 y 3). Los tres enlaces de
la tabla 1 son los unicos que hay en `calc/calc.js`, y
`tests/test_calc_js.py` comprueba que no aparezca ninguno mas: inventar una cita
es peor que no tenerla.

Las formulas no necesitan cita: estan validadas contra `tests/test_scenarios.py`
y `policy.py`. Lo que falta es de donde salen los **numeros de entrada**.

---

## 1. Con fuente (verificada)

Estas ya no son suposiciones nuestras sobre el equipo: hay un documento detras.
En la pagina llevan la etiqueta **FUENTE**, con la URL entera a la vista y la
salvedad al lado.

| Clave | Perfil | Por defecto | Fuente | Que dice — y que no dice |
|---|---|---|---|---|
| `a_w` | PQS de referencia | 35 W | [PQS E003-066](https://extranet.who.int/prequal/sites/default/files/immunization_devices/pdf/e003/E003-066.pdf) | "0.85 kWh/24 h continuo ≈ 35 W; un solo modelo AC." Es la media del ciclo continuo, no el pico de un arranque. En el perfil **didactico** este mismo campo sigue siendo un supuesto por citar (8 W) |
| `t_lim_c` | los dos | 7.5 °C | [PQS E003-RF-021](https://extranet.who.int/prequal/key-resources/documents/pqs-performance-specification-e003rf021-refrigerator-or-combined) | "Vacunas +2 a +8 °C; el holdover PQS se mide hasta +10 °C; 7.5 °C es nuestro margen." Ojo: el 7.5 **no** sale del documento, es el 8 °C de la banda menos un margen de sensor |
| `cortes_mes` | los dos | 1.3 | [IndexMundi · World Bank, cortes por empresa](https://www.indexmundi.com/facts/indicators/IC.ELC.OUTG/rankings/central-america) | "Guatemala 1.3 cortes/mes, 2017, empresas (World Bank Enterprise Surveys); no da duración." Es un promedio de pais medido a empresas, no una serie del sitio ni de una clínica |

## 2. Sin ninguna fuente: los elige esta calculadora

| Clave | Por defecto | Que es | Etiqueta | Que haria falta para citarlo |
|---|---|---|---|---|
| `nominal_wh` | 128 Wh | Capacidad nominal del paquete de baterias | SUPUESTO — por citar | Ficha tecnica del paquete instalado. Ojo: con `dod_pct` = 75 % tiene que dar los 96 Wh utiles de `config.py: E_UTIL_WH` (o cambiar tambien ese valor). En el perfil PQS el defecto es 400 Wh (300 Wh utiles) |
| `dod_pct` | 75 % | Profundidad de descarga util | SUPUESTO — por citar | Ficha de ciclado del fabricante (curva ciclos vs profundidad) o el criterio de instalacion |
| `ciclos` | 300 ciclos | Ciclos completos que admite la bateria | SUPUESTO — por citar | Ficha tecnica de la bateria (plomo-acido suele andar por cientos; LiFePO4, por miles). El calculo asume **un ciclo por corte**, que es conservador |
| `cargador_w` | 30 W | Potencia del cargador | SUPUESTO — por citar | Placa del cargador que se vaya a instalar |

## 3. Copiados del repo, pendientes igualmente de fuente externa

Estos salen tal cual de `scenarios.py` (perfil didactico) o `config.py`, donde
ya estan declarados como supuestos de partida. La columna `origen` de `calc.js`
dice de que archivo se copiaron. Se etiquetan **SUPUESTO** porque son de donde
son, pero siguen sin tener detras una medicion ni un fabricante.

| Clave | Por defecto | Origen en el repo | Que haria falta para citarlo |
|---|---|---|---|
| `a_w` | 8 W | `scenarios.py: A_W` | Medir el consumo medio de la nevera de la maqueta (vatimetro o placa del equipo). En la tabla 1 esta el mismo campo para una nevera PQS real |
| `b_w` | 4 W (25 W en el perfil PQS) | `scenarios.py: B_W` | Medir las luces de pasillo. En el perfil PQS los 25 W son un SUPUESTO por medir, no una fuente |
| `c_w` | 3 W (20 W en el perfil PQS) | `scenarios.py: C_W` | Medir la sala de espera. Igual: los 20 W del perfil PQS son supuesto |
| `d_h` | 12 h | `scenarios.py: PERFILES['didactico'].d_h` | Duracion del corte que se quiere cubrir: historico de la zona |
| `eta` | 0.85 | `scenarios.py: ETA_CHARGE` | Curva de carga del fabricante del cargador/bateria |
| `t_amb_c` | 25 °C | `scenarios.py: T_AMB_C` | Temperatura del sitio donde va la nevera (idealmente, un registro) |
| `tau_h` | 4 h | `config.py: TAU_H` | Constante de tiempo de la nevera: ficha tecnica o ensayo de caida de temperatura. Es la que decide el holdover |
| `t_hi_c` | 5.0 °C | `config.py: T_HI_C` | Consigna de la nevera (techo de la banda de control) |

## 4. Que NO es esto

* No es una prediccion de cortes: no hay datos medidos ni serie historica.
* Los 7.5 °C de `t_lim_c` son un margen **nuestro** sobre la banda 2–8 °C; el
  documento de la tabla 1 da la banda, no el margen.
* El holdover de esta maqueta es el de una caja **sin forro de hielo**, y asi se
  dice en la calculadora y en el panel: una nevera PQS con forro aguanta de
  horas a dias y necesitaria menos ayuda (o sea, aqui se subestima su autonomia,
  que es lo conservador).
* La vida de la bateria (`vida_anios`) supone un ciclo completo por corte. Con
  cortes cortos, eso subestima la vida real; con cortes largos y bateria
  pequena, se acerca.
* El modelo termico es de masa concentrada (una sola `tau`), no un modelo
  termico de la caja real.

## 5. Como se comprueba que esto sigue siendo cierto

`tests/test_calc_js.py` (se salta si no hay `node`) comprueba que:

1. cada campo de `DEFAULTS` tiene etiqueta y que la etiqueta es una de las
   conocidas (`SUPUESTO`, `SUPUESTO — por citar`, `FUENTE`);
2. todas las etiquetas `FUENTE` llevan enlace, y los enlaces son **solo** los
   tres de `URLS_PERMITIDAS`, listados uno a uno;
3. no hay ninguna otra URL suelta en `calc.js` (ni en notas, ni en origenes);
4. los perfiles de `calc.js` dicen lo mismo que `scenarios.py: PERFILES`;
5. los campos marcados «por citar» aparecen en este archivo, y **todos** los
   campos aparecen en este archivo (que no se quede ninguno sin revisar);
6. `origen`, cuando no es `null`, apunta a un archivo que existe de verdad en el
   repo.
