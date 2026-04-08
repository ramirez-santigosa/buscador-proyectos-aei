"""Modelos Pydantic para la API."""

from pydantic import BaseModel, field_validator


class BusquedaRequest(BaseModel):
    keywords: list[str]
    and_terms: list[str] = []
    cif_filter: str = ""
    conv_filter: str = ""

    @field_validator("keywords")
    @classmethod
    def al_menos_uno(cls, v):
        limpio = [k.strip() for k in v if k.strip()]
        if not limpio:
            raise ValueError("Introduce al menos un término de búsqueda.")
        return limpio

    @field_validator("and_terms")
    @classmethod
    def limpiar_and(cls, v):
        return [k.strip() for k in v if k.strip()]


class ResumenBusqueda(BaseModel):
    n_proyectos: int
    ayuda_total: float
    keywords: list[str]
    and_terms: list[str]
    anos: list[str]           # años disponibles en el resultado
    terminos_proyectos: list  # filas de df_terminos_proyectos (dicts)
    terminos_ayuda: list      # filas de df_terminos_ayuda (dicts)
    # Estadísticas agregadas
    totales: list = []
    top_conv: list = []
    top_entidades: list = []
    top_ccaa: list = []
    mapa_b64: str = ""        # PNG del mapa coroplético en base64
