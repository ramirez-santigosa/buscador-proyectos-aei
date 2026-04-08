"""
Funciones de normalización de texto y mapas de columnas.
Portado de buscador_proyectos.py (líneas 39-166).
"""

TILDES = str.maketrans(
    "áàâäéèêëíìîïóòôöúùûüñÁÀÂÄÉÈÊËÍÌÎÏÓÒÔÖÚÙÛÜÑ",
    "aaaaeeeeiiiioooouuuunAAAAEEEEIIIIOOOOUUUUN"
)


def normalizar(texto):
    if not isinstance(texto, str):
        texto = str(texto) if texto is not None else ""
    return texto.lower().translate(TILDES)


def normalizar_numero(valor):
    if valor is None or (isinstance(valor, float) and str(valor) == 'nan'):
        return None
    if isinstance(valor, (int, float)):
        return valor
    s = str(valor).strip().replace('€', '').replace(' ', '')
    if not s or s.lower() == 'nan':
        return None
    if ',' in s and '.' in s:
        if s.index(',') > s.index('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def limpiar(texto):
    if not isinstance(texto, str):
        return texto
    for ch in ["_x000D_", "\r", "\t"]:
        texto = texto.replace(ch, " ")
    texto = texto.replace("\n", " ")
    while "  " in texto:
        texto = texto.replace("  ", " ")
    return texto.strip()


def detectar_programa(nombre):
    n = nombre.upper()
    if "RTC" in n:  return "Retos de Colaboración (RTC)"
    if "CPP" in n:  return "Proyectos en Colaboración Público-Privada (CPP)"
    if "PLEC" in n: return "Proyectos Estratégicos de Líneas de Actuación (PLEC)"
    return nombre


def terminos_hallados(texto_norm, kws_norm):
    return [kw for kw in kws_norm if kw in texto_norm]


# Columnas del DataFrame de resultados (orden para Excel de salida)
COLS_SALIDA = [
    "Fuente", "Año Convocatoria", "Convocatoria / Programa",
    "Referencia Padre", "Referencia", "Título", "Resumen",
    "Prioridad Temática / Reto / Área", "Área / Subárea",
    "Organismo / Entidad", "NIF / CIF", "Rol (Solicitante/Participante)",
    "Centro", "Tipo de Centro", "Subtipo de Centro",
    "Comunidad Autónoma", "Provincia", "Sector Público",
    "Género", "Ayuda Total Concedida (€)", "Términos encontrados"
]

# Mapeo cabeceras Excel RTC-CPP-PLE → nombre canónico
MAPA_EXCEL = {
    "ano convocatoria":          "Año Convocatoria",
    "convocatoria":              "_convocatoria",
    "referencia padre":          "Referencia Padre",
    "referencia":                "Referencia",
    "titulo":                    "Título",
    "resumen ejecutivo":         "Resumen",
    "palabras clave":            "Palabras Clave",
    "reto":                      "_reto",
    "prioridad tematica":        "Prioridad Temática / Reto / Área",
    "acronimo area":             "_area",
    "acronimo subarea":          "_subarea",
    "organismo":                 "Organismo / Entidad",
    "nif organismo":             "NIF / CIF",
    "solicitante/participante":  "Rol (Solicitante/Participante)",
    "centro":                    "Centro",
    "tipo de centro":            "Tipo de Centro",
    "subtipo de centro":         "Subtipo de Centro",
    "sector publico":            "Sector Público",
    "comunidad autonoma centro": "Comunidad Autónoma",
    "provincia":                 "Provincia",
    "provincia centro":          "Provincia",
    "ayuda total concedida":     "Ayuda Total Concedida (€)",
}

# Mapeo cabeceras CSV ANUALES → nombre canónico
MAPA_CSV = {
    "ano":                       "Año Convocatoria",
    "ano convocatoria":          "Año Convocatoria",
    "convocatoria":              "Convocatoria / Programa",
    "referencia":                "Referencia",
    "genero":                    "Género",
    "genero ip":                 "Género",
    "area":                      "Área / Subárea",
    "subarea":                   "_subarea",
    "titulo":                    "Título",
    "titulo del proyecto":       "Título",
    "denominacion":              "Título",
    "denominacion del proyecto": "Título",
    "c.i.f.":                    "NIF / CIF",
    "cif":                       "NIF / CIF",
    "nif":                       "NIF / CIF",
    "entidad":                   "Organismo / Entidad",
    "entidad beneficiaria":      "Organismo / Entidad",
    "organismo":                 "Organismo / Entidad",
    "cc.aa.":                    "Comunidad Autónoma",
    "ccaa":                      "Comunidad Autónoma",
    "comunidad autonoma":        "Comunidad Autónoma",
    "provincia":                 "Provincia",
    "resumen":                   "Resumen",
    "palabras clave":            "Palabras Clave",
}

# Campos en los que se busca texto libre
CAMPOS_BUSQUEDA = ["Título", "Resumen", "Palabras Clave"]

# Mapeo nombres CCAA (datos fuente) → nombre en shapefile IGN
CCAA_MAP = {
    "ANDALUCIA":         "Andalucía",
    "ARAGON":            "Aragón",
    "PDO.ASTURIAS":      "Principado de Asturias",
    "BALEARES":          "Illes Balears",
    "CANARIAS":          "Canarias",
    "CANTABRIA":         "Cantabria",
    "CASTILLA Y LEON":   "Castilla y León",
    "CASTILLA-LA MANCHA":"Castilla-La Mancha",
    "CATALUÑA":          "Cataluña/Catalunya",
    "C.VALENCIANA":      "Comunitat Valenciana",
    "EXTREMADURA":       "Extremadura",
    "GALICIA":           "Galicia",
    "MADRID":            "Comunidad de Madrid",
    "MURCIA":            "Región de Murcia",
    "NAVARRA":           "Comunidad Foral de Navarra",
    "PAIS VASCO":        "País Vasco/Euskadi",
    "LA RIOJA":          "La Rioja",
    "CEUTA":             "Ciudad Autónoma de Ceuta",
    "MELILLA":           "Ciudad Autónoma de Melilla",
}


def filtrar_por_keywords(df, kws_norm):
    """Devuelve las filas del DataFrame que contienen alguno de los términos."""
    import pandas as pd
    campos = [c for c in CAMPOS_BUSQUEDA if c in df.columns]
    if "Título" not in campos:
        return pd.DataFrame()
    filas = []
    for _, row in df.iterrows():
        texto = " ".join(normalizar(str(row.get(c) or "")) for c in campos)
        encontrados = terminos_hallados(texto, kws_norm)
        if encontrados:
            r = row.copy()
            r["Términos encontrados"] = "; ".join(encontrados)
            filas.append(r)
    return pd.DataFrame(filas) if filas else pd.DataFrame()
