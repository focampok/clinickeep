"""plots.py - Mapas de calor de S2 y S3 (requiere matplotlib).

Colores: rampa secuencial de un solo tono para magnitud (S2a) y tres estados con
leyenda y trama para identidad (S2b, S3): no depende solo del color.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle, Patch

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e3e2de"
NEUTRAL = "#d6d5d0"
BLUE = "#2a78d6"
AQUA = "#1baf7a"
SEQ = LinearSegmentedColormap.from_list("seq", ["#e7f0fb", "#7fb2ea", "#2a78d6", "#123a73"])


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=9, length=3)


def _axes(title, subtitle, xlabel, ylabel):
    fig, ax = plt.subplots(figsize=(8.4, 5.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    fig.text(0.07, 0.95, title, fontsize=13, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.07, 0.905, subtitle, fontsize=9.5, color=INK2, ha="left", va="top")
    ax.set_xlabel(xlabel, color=INK2, fontsize=10)
    ax.set_ylabel(ylabel, color=INK2, fontsize=10)
    return fig, ax


def _footer(fig, text):
    fig.text(0.07, 0.015, text, fontsize=7.2, color=INK2, ha="left", va="bottom", wrap=True)


def _axis_values(rows, key):
    vals = sorted(set(r[key] for r in rows))
    return vals


def _heat_continuous(rows, xkey, ykey, vkey):
    xs = _axis_values(rows, xkey)
    ys = _axis_values(rows, ykey)
    grid = [[0.0] * len(xs) for _ in ys]
    xi = {v: i for i, v in enumerate(xs)}
    yi = {v: i for i, v in enumerate(ys)}
    for r in rows:
        grid[yi[r[ykey]]][xi[r[xkey]]] = r[vkey]
    return xs, ys, grid


def _marca(perfil, subtitulo):
    """El perfil va delante del subtitulo: cada mapa dice de que supuestos es."""
    return ("Perfil %s — %s" % (perfil, subtitulo)) if perfil else subtitulo


def s2a(path, rows, assumptions, perfil=None):
    xs, ys, grid = _heat_continuous(rows, "no_critica_pct", "e_wh", "mejora_pct")
    d = rows[0]["d_h"]
    fig, ax = _axes(
        "S2a - Cuánto ayuda priorizar la nevera (corte de %d h)" % d,
        _marca(perfil, "Mejora en horas de cadena de frío protegida, con vs sin ClinicKeep"),
        "Carga no crítica (B + C) como % de la carga total",
        "Batería útil (Wh)")
    fig.subplots_adjust(left=0.1, right=0.9, top=0.84, bottom=0.18)
    dx = xs[1] - xs[0]
    dy = ys[1] - ys[0]
    mesh = ax.pcolormesh([x - dx / 2 for x in xs] + [xs[-1] + dx / 2],
                         [y - dy / 2 for y in ys] + [ys[-1] + dy / 2],
                         grid, cmap=SEQ, vmin=0, edgecolors=SURFACE, linewidth=0.6)
    cb = fig.colorbar(mesh, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Mejora (%)", color=INK2, fontsize=9)
    cb.ax.tick_params(colors=INK2, labelsize=8)
    cb.outline.set_visible(False)
    ax.set_xticks(xs[::2])
    _footer(fig, assumptions)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def _heat_states(path, rows, xkey, ykey, title, subtitle, xlabel, ylabel, labels,
                 assumptions, perfil=None):
    xs = _axis_values(rows, xkey)
    ys = _axis_values(rows, ykey)
    st = {(r[xkey], r[ykey]): r["estado"] for r in rows}
    fig, ax = _axes(title, _marca(perfil, subtitle), xlabel, ylabel)
    fig.subplots_adjust(left=0.1, right=0.97, top=0.84, bottom=0.2)
    dx = xs[1] - xs[0]
    dy = ys[1] - ys[0]
    colors = [NEUTRAL, BLUE, AQUA]
    for x in xs:
        for y in ys:
            s = st[(x, y)]
            ax.add_patch(Rectangle((x - dx / 2, y - dy / 2), dx, dy, facecolor=colors[s],
                                   edgecolor=SURFACE, linewidth=0.8,
                                   hatch="////" if s == 2 else None))
    ax.set_xlim(xs[0] - dx / 2, xs[-1] + dx / 2)
    ax.set_ylim(ys[0] - dy / 2, ys[-1] + dy / 2)
    handles = [Patch(facecolor=NEUTRAL, label=labels[0]),
               Patch(facecolor=BLUE, label=labels[1]),
               Patch(facecolor=AQUA, hatch="////", edgecolor="white", label=labels[2])]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3,
              frameon=False, fontsize=8.5, labelcolor=INK2)
    _footer(fig, assumptions)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def make_all(out, s2a_rows, s2b_rows, s3_rows, assumptions, perfil=None):
    s2a(os.path.join(out, "s2a_mejora.png"), s2a_rows, assumptions, perfil)
    _heat_states(
        os.path.join(out, "s2b_cobertura.png"), s2b_rows, "d_h", "e_wh",
        "S2b - ¿La nevera aguanta todo el corte?",
        "Cobertura de A durante el corte, según duración y batería",
        "Duración del corte (h)", "Batería útil (Wh)",
        ["No cubre", "Solo con ClinicKeep", "Cubre con y sin ClinicKeep"], assumptions, perfil)
    _heat_states(
        os.path.join(out, "s3_recarga.png"), s3_rows, "d_h", "cargador_w",
        "S3 - ¿Alcanza a recargarse entre cortes? (batería de %.0f Wh)" % s3_rows[0]["e_wh"],
        "Un corte al día; la red vuelve el resto del día. Si no recarga, hace falta solar o generador",
        "Duración del corte (h)", "Potencia del cargador (W)",
        ["No recarga", "Recarga solo con ClinicKeep", "Recarga con y sin ClinicKeep"],
        assumptions, perfil)
