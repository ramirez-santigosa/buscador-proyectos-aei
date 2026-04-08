"""
Generación del mapa coroplético de CCAA.
Portado de buscador_proyectos.py líneas 295-404.
Acepta shapefile IGN o data/ccaa.geojson.
"""

from pathlib import Path

import pandas as pd

from core.text import CCAA_MAP

# Rutas candidatas al fichero de geometrías
_REPO = Path(__file__).resolve().parents[1]
_GEOJSON = _REPO / "data" / "ccaa.geojson"

_SHP_CANDIDATES = [
    _REPO / "data" / "geodata" / "recintos_autonomicas_inspire_peninbal_etrs89.shp",
    Path.home()
    / "OneDrive - MINISTERIO DE CIENCIA E INNOVACIÓN"
    / "General - Unidad de Apoyo"
    / "08-PROYECTOS"
    / "01-BUSQUEDA DE PROYECTOS"
    / "SOURCES"
    / "geodata"
    / "SHP_ETRS89"
    / "recintos_autonomicas_inspire_peninbal_etrs89"
    / "recintos_autonomicas_inspire_peninbal_etrs89.shp",
]


def _find_geo():
    if _GEOJSON.exists():
        return _GEOJSON, "geojson"
    for p in _SHP_CANDIDATES:
        if p.exists():
            return p, "shp"
    return None, None


def generar_mapa_ccaa(top_ccaa_df: pd.DataFrame, out_img_path: Path, terminos_str: str, dpi: int = 600):
    """
    Genera un mapa coroplético de España coloreado por nº de proyectos.

    Parámetros
    ----------
    top_ccaa_df  : DataFrame con columnas 'Comunidad Autónoma' y 'Proyectos'
    out_img_path : ruta de salida para el PNG
    terminos_str : cadena de términos (para el título del mapa)

    Retorna la ruta del PNG si se generó correctamente, None en caso contrario.
    """
    try:
        import geopandas as gpd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        import numpy as np

        geo_path, geo_type = _find_geo()
        if geo_path is None:
            return None

        if geo_type == "shp":
            gdf = gpd.read_file(str(geo_path), encoding="latin-1")
        else:
            gdf = gpd.read_file(str(geo_path))

        # Preparar datos (excluir filas de TOTAL)
        df_data = top_ccaa_df[
            ~top_ccaa_df["Comunidad Autónoma"].isin(["TOTAL TOP 10", "TOTAL", ""])
        ].copy()
        df_data["NAMEUNIT"] = df_data["Comunidad Autónoma"].map(CCAA_MAP)
        df_data = df_data.dropna(subset=["NAMEUNIT"])

        gdf["NAMEUNIT_clean"] = gdf["NAMEUNIT"].str.strip()
        gdf = gdf.merge(
            df_data[["NAMEUNIT", "Proyectos"]],
            left_on="NAMEUNIT_clean", right_on="NAMEUNIT", how="left",
        )
        gdf["Proyectos"] = gdf["Proyectos"].fillna(0)

        peninsula = gdf[~gdf["NAMEUNIT_clean"].str.contains("Canarias", na=False)]
        canarias  = gdf[gdf["NAMEUNIT_clean"].str.contains("Canarias", na=False)]

        max_val = gdf["Proyectos"].max()
        cmap = plt.cm.Blues
        norm = mcolors.Normalize(vmin=0, vmax=max(max_val, 1))

        fig, ax = plt.subplots(1, 1, figsize=(6, 4))
        fig.patch.set_facecolor("#F8FBFF")
        ax.set_facecolor("#EAF4FB")

        peninsula.plot(
            ax=ax,
            color=[cmap(norm(v)) for v in peninsula["Proyectos"]],
            edgecolor="#666666", linewidth=0.6,
        )

        for _, row in peninsula.iterrows():
            if row["Proyectos"] > 0:
                centroid = row.geometry.centroid
                ax.annotate(
                    str(int(row["Proyectos"])),
                    xy=(centroid.x, centroid.y),
                    ha="center", va="center",
                    fontsize=7, fontweight="bold",
                    color="white" if row["Proyectos"] > max_val * 0.5 else "#1F4E79",
                )

        if len(canarias) > 0:
            ax_in = ax.inset_axes([0.0, 0.0, 0.28, 0.28])
            ax_in.set_facecolor("#EAF4FB")
            canarias.plot(
                ax=ax_in,
                color=[cmap(norm(v)) for v in canarias["Proyectos"]],
                edgecolor="#666666", linewidth=0.6,
            )
            ax_in.set_xticks([]); ax_in.set_yticks([])
            ax_in.set_title("Canarias", fontsize=6, pad=2)
            for spine in ax_in.spines.values():
                spine.set_edgecolor("#1F4E79")
                spine.set_linewidth(0.8)

        ax.set_axis_off()

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.02)
        cbar.set_label("Nº Proyectos", fontsize=8, color="#1F4E79")
        cbar.ax.tick_params(labelsize=7)

        fig.text(0.01, 0.01, "Obra derivada de BDLJE CC-BY 4.0 ign.es",
                 fontsize=6, color="#888888", style="italic")

        plt.tight_layout(pad=0.5)
        fig.patch.set_edgecolor("black")
        fig.patch.set_linewidth(1.5)
        plt.savefig(
            str(out_img_path), dpi=dpi, bbox_inches="tight",
            facecolor=fig.get_facecolor(), edgecolor="black", format="png",
        )
        plt.close(fig)
        return out_img_path

    except Exception:
        import traceback
        traceback.print_exc()
        return None


def shapefile_a_geojson(shp_path: Path = None, out_path: Path = _GEOJSON):
    """
    Convierte el shapefile IGN a data/ccaa.geojson ligero.
    Solo necesita ejecutarse una vez (el resultado se versiona en el repo).
    """
    import geopandas as gpd

    if shp_path is None:
        for p in _SHP_CANDIDATES:
            if p.exists():
                shp_path = p
                break
    if shp_path is None or not shp_path.exists():
        raise FileNotFoundError("Shapefile IGN no encontrado.")

    gdf = gpd.read_file(str(shp_path), encoding="latin-1")
    gdf = gdf[["NAMEUNIT", "geometry"]].copy()
    gdf = gdf.to_crs("EPSG:4326")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(str(out_path), driver="GeoJSON")
    size_kb = out_path.stat().st_size / 1024
    print(f"GeoJSON generado: {out_path}  ({size_kb:.0f} KB)")
    return out_path
