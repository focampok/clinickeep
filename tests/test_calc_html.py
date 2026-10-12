"""test_calc_html.py - Lo que la pagina de la calculadora tiene que tener
(Fase 4, punto 6).

Son comprobaciones sobre el HTML y el CSS, sin navegador: que el aviso de
simulacion y el pie esten, que se pueda usar con teclado, que funcione a 360 px,
que se pueda copiar y descargar, y que no dependa de nada de fuera (ni CDN, ni
fuentes, ni framework: la pagina tiene que funcionar servida de cualquier sitio).
"""

import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(RAIZ, "calc", "index.html")

with open(HTML, encoding="utf-8") as _fh:
    PAGINA = _fh.read()


def test_avisa_de_que_esto_es_una_simulacion():
    assert 'role="note"' in PAGINA
    assert "SIMULACIÓN" in PAGINA


def test_el_pie_es_el_mismo_que_el_de_calc_js():
    """El pie esta escrito en el HTML (se ve aunque el modulo no cargue) y tiene
    que ser exactamente el texto de calc.js, que es el que va en el resumen y el
    CSV. Si uno cambia y el otro no, esta prueba lo dice."""
    with open(os.path.join(RAIZ, "calc", "calc.js"), encoding="utf-8") as fh:
        js = fh.read()
    trozo = re.search(r"export const PIE =\s*\n?\s*\"([^\"]+)\"", js)
    assert trozo, "calc.js ya no exporta PIE"
    assert "<strong>%s</strong>" % trozo.group(1) in PAGINA
    assert "no es predicción de cortes ni datos medidos" in PAGINA


def test_tema_claro_y_oscuro():
    assert "prefers-color-scheme: dark" in PAGINA
    assert "color-scheme: light dark" in PAGINA


def test_se_usa_con_teclado():
    assert 'setAttribute("for", clave)' in PAGINA              # <label for=...>
    assert "aria-describedby" in PAGINA or "setAttribute(\"aria-describedby\"" in PAGINA
    assert ":focus-visible" in PAGINA                          # foco siempre visible
    assert 'class="saltar"' in PAGINA                          # saltar al formulario
    assert "aria-live" in PAGINA                               # los resultados se anuncian
    assert 'role="alert"' in PAGINA                            # los errores tambien


def test_cabe_a_360_px():
    assert "width=device-width" in PAGINA
    assert "max-width: 380px" in PAGINA                        # ajuste para movil
    assert "minmax(" in PAGINA                                 # rejilla que se reordena sola
    assert "min-width: 0" in PAGINA                            # nada que fuerce el ancho


def test_resultados_con_texto_e_icono_no_solo_color():
    assert "ICONO.ok" in PAGINA and "ICONO.aviso" in PAGINA and "ICONO.no" in PAGINA
    assert "estado--ok" in PAGINA and "estado--aviso" in PAGINA and "estado--no" in PAGINA
    # los tres estados se dicen con palabras
    assert "no cubre el corte ni con ClinicKeep" in PAGINA
    assert "solo con ClinicKeep" in PAGINA
    assert "con y sin ClinicKeep" in PAGINA


def test_se_puede_copiar_y_descargar():
    assert "Copiar resumen" in PAGINA
    assert "navigator.clipboard.writeText" in PAGINA
    assert "execCommand" in PAGINA                             # por si el navegador no deja
    assert 'download="clinickeep-calculadora.csv"' in PAGINA
    assert "URL.createObjectURL" in PAGINA


def test_se_puede_elegir_perfil():
    """Dos perfiles de supuestos, elegibles, y el elegido se puede compartir."""
    assert "PERFILES" in PAGINA
    assert 'createElement("select")' in PAGINA
    assert 'id = "perfil"' in PAGINA
    assert "location.search" in PAGINA            # ?perfil=pqs_ref
    assert "cambiarPerfil" in PAGINA              # al cambiar, recarga los defectos


def test_las_fuentes_van_con_enlace_visible():
    """La etiqueta FUENTE se enseña con el enlace entero a la vista, no con un
    "ver mas", y con la salvedad al lado."""
    assert "meta.fuente" in PAGINA
    assert "noopener noreferrer" in PAGINA
    assert "a.textContent = f.url" in PAGINA
    assert "etiqueta--fuente" in PAGINA


def test_no_depende_de_nada_de_fuera():
    """Sin CDN, sin fuentes de Google, sin framework: solo calc.js de al lado."""
    externos = re.findall(r'(?:src|href)\s*=\s*"(https?://[^"]+)"', PAGINA)
    assert externos == []
    assert 'type="module"' in PAGINA
    assert 'from "./calc.js"' in PAGINA
    for etiqueta in ("<script", "<style"):
        assert etiqueta in PAGINA


def test_los_defectos_no_se_copian_en_el_html():
    """Los campos los pinta el script desde calc.js: si el HTML llevara valores
    por su cuenta, podrian desincronizarse."""
    cuerpo = PAGINA.split("<body>", 1)[1]
    assert 'id="formulario"' in cuerpo
    assert 'value="8"' not in cuerpo
    assert "Nevera de vacunas" not in PAGINA                    # eso vive en calc.js
