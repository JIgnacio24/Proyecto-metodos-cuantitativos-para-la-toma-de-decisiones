"""
Decisión Core DSS — Backend FastAPI
=====================================
Punto de entrada del servidor. Define todos los endpoints REST que el
frontend Angular consume para ejecutar el pipeline de análisis:

  POST /api/analizar       → pipeline completo: pronóstico → inventario → Monte Carlo → reporte
  GET  /api/datos-ejemplo  → datos precargados de una PyME importadora de repuestos
  GET  /api/salud          → verificar que el servidor está activo

Arquitectura del pipeline (en orden):
  1. Regresión Lineal    → demanda pronosticada + σ (error estándar)
  2. EOQ + Stock Seguridad → usando σ del paso 1 (conexión entre módulos)
  3. Monte Carlo 10,000  → usando σ del paso 1 para la dispersión de demanda
  4. Reporte Estadístico → VaR, IC 95%, probabilidades, comparación A vs B
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Annotated

from motor.pronostico import calcular_pronostico
from motor.inventario import calcular_inventario
from motor.simulacion import ejecutar_simulacion
from motor.reportes import (
    calcular_estadisticas,
    calcular_histograma,
    calcular_distribucion_acumulada,
    generar_reporte_comparativo,
)

# -----------------------------------------------------------------------
# Inicialización de la aplicación FastAPI
# -----------------------------------------------------------------------
app = FastAPI(
    title="Decisión Core DSS",
    description=(
        "Sistema de Soporte a Decisiones para PyMEs importadoras. "
        "Integra Pronóstico (Regresión Lineal), Optimización (EOQ) "
        "y Simulación (Monte Carlo) en un único pipeline cuantitativo."
    ),
    version="1.0.0",
)

# -----------------------------------------------------------------------
# CORS — Cross-Origin Resource Sharing
# Permite que el navegador cargue la app Angular (localhost:4200) y llame
# a este backend (localhost:8000) sin que el navegador bloquee la petición.
# En producción se reemplazarían estos orígenes por el dominio real.
# -----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------
# Modelos de datos (Pydantic)
# Pydantic valida automáticamente el JSON que llega del frontend y devuelve
# errores claros si algún campo falta o tiene el tipo incorrecto.
# -----------------------------------------------------------------------

class ParametrosAnalisis(BaseModel):
    """
    Parámetros de entrada para el análisis completo del DSS.
    Todos los montos son en Colones Costarricenses (CRC).
    """

    # --- Datos históricos de demanda ---
    # Cada elemento es la demanda observada en un período (mes, trimestre, etc.)
    # Se necesitan mínimo 3 puntos para que la regresión lineal tenga grados de libertad.
    demanda_historica: Annotated[list[float], Field(min_length=3, description="Demanda por período (mínimo 3 puntos)")]

    # --- Parámetros financieros en CRC ---
    costo_unitario:   float = Field(..., gt=0, description="Costo de compra por unidad (CRC)")
    precio_venta:     float = Field(..., gt=0, description="Precio de venta por unidad (CRC)")
    costo_por_pedido: float = Field(..., gt=0, description="Costo fijo por orden de compra (CRC)")
    costo_mantener:   float = Field(..., gt=0, description="Costo de mantener una unidad por período (CRC)")
    costo_ruptura:    float = Field(..., gt=0, description="Penalización por unidad de demanda no satisfecha (CRC)")

    # --- Parámetros logísticos ---
    lead_time:       int   = Field(default=1, ge=1,    description="Períodos de reposición (tiempo entre pedido y entrega)")
    nivel_servicio:  float = Field(default=0.95, ge=0.5, le=0.999, description="Fracción de escenarios con stock disponible")

    # --- Parámetros de simulación ---
    n_iteraciones:        int   = Field(default=10000, ge=1000, le=100000, description="Número de escenarios Monte Carlo")
    factor_incertidumbre: float = Field(default=1.0, ge=0.1, le=5.0,    description="Multiplicador sobre σ del pronóstico")

    @field_validator("demanda_historica")
    @classmethod
    def validar_demandas_positivas(cls, v: list[float]) -> list[float]:
        """Las demandas históricas no pueden ser negativas."""
        if any(d < 0 for d in v):
            raise ValueError("Todas las demandas históricas deben ser no negativas.")
        return v

    @model_validator(mode="after")
    def validar_margen_positivo(self) -> "ParametrosAnalisis":
        """El precio de venta debe superar el costo unitario para que haya margen."""
        if self.precio_venta <= self.costo_unitario:
            raise ValueError(
                f"El precio de venta ({self.precio_venta:,.0f} CRC) debe ser "
                f"mayor al costo unitario ({self.costo_unitario:,.0f} CRC)."
            )
        return self


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@app.get("/api/salud", tags=["Sistema"])
def verificar_salud():
    """
    Endpoint de verificación de estado.
    El frontend lo llama al iniciar para confirmar que el backend está activo.
    """
    return {
        "estado": "activo",
        "version": "1.0.0",
        "mensaje": "Decisión Core DSS está funcionando correctamente.",
    }


@app.get("/api/datos-ejemplo", tags=["Sistema"])
def obtener_datos_ejemplo():
    """
    Devuelve un conjunto de datos de ejemplo para explorar el sistema.

    Escenario: PyME costarricense que importa repuestos para camiones de carga.
    Los datos representan demanda mensual (unidades) durante 12 meses.
    Todos los montos están en Colones Costarricenses (CRC).
    """
    return {
        # 12 meses de demanda histórica con tendencia ascendente y algo de ruido
        "demanda_historica": [420, 445, 410, 460, 480, 435, 500, 470, 515, 490, 530, 505],
        "costo_unitario":    15000,   # CRC — costo de importar un repuesto
        "precio_venta":      28000,   # CRC — precio al que se vende al taller
        "costo_por_pedido":  85000,   # CRC — costo administrativo + flete de la orden
        "costo_mantener":    2500,    # CRC — almacenaje + seguro + depreciación por unidad/mes
        "costo_ruptura":     12000,   # CRC — penalización por venta perdida (pérdida de margen + cliente)
        "lead_time":         2,       # meses — tiempo de importación desde el proveedor
        "nivel_servicio":    0.95,    # 95% — nivel de servicio deseado
        "n_iteraciones":     10000,
        "factor_incertidumbre": 1.0,
        "descripcion": (
            "PyME importadora de repuestos para camiones en Costa Rica. "
            "Demanda mensual en unidades. Montos en CRC."
        ),
    }


@app.post("/api/analizar", tags=["Análisis"])
def analizar_completo(params: ParametrosAnalisis):
    """
    Endpoint principal del DSS. Ejecuta el pipeline cuantitativo completo:

    PASO 1 — PRONÓSTICO (Regresión Lineal):
      Ajusta Y = β0 + β1·X sobre los datos históricos.
      Produce: demanda pronosticada μ y error estándar σ.

    PASO 2 — INVENTARIO (EOQ):
      Calcula el lote económico óptimo usando μ del paso 1.
      Calcula el stock de seguridad usando σ del paso 1.
      → Aquí está el primer vínculo entre pronóstico e inventario.

    PASO 3 — SIMULACIÓN MONTE CARLO:
      Genera 10,000 escenarios de demanda ~ Normal(μ, σ · factor).
      Evalúa la utilidad del período para cada escenario, bajo dos políticas:
        A: pedir EOQ  |  B: pedir EOQ + stock de seguridad.
      → Aquí está el segundo vínculo: σ del pronóstico define la incertidumbre.

    PASO 4 — REPORTE:
      Media, IC 95%, VaR, probabilidades, comparación A vs B y recomendación.

    Parámetros
    ----------
    params : ParametrosAnalisis — todos los inputs del usuario (validados por Pydantic)

    Retorna
    -------
    JSON con los resultados de los 4 pasos, listos para renderizar en Angular.
    """
    try:
        # ---- PASO 1: PRONÓSTICO ----
        resultado_pronostico = calcular_pronostico(params.demanda_historica)
        demanda_forecast = resultado_pronostico["demanda_pronosticada"]
        sigma_pronostico = resultado_pronostico["error_estandar"]

        # ---- PASO 2: INVENTARIO ----
        resultado_inventario = calcular_inventario(
            demanda_pronosticada=demanda_forecast,
            error_estandar=sigma_pronostico,        # σ viene del pronóstico
            costo_unitario=params.costo_unitario,
            costo_por_pedido=params.costo_por_pedido,
            costo_mantener=params.costo_mantener,
            lead_time=params.lead_time,
            nivel_servicio=params.nivel_servicio,
        )
        eoq            = resultado_inventario["eoq"]
        stock_seguridad = resultado_inventario["stock_seguridad"]

        # ---- PASO 3: SIMULACIÓN MONTE CARLO ----
        resultado_sim = ejecutar_simulacion(
            demanda_pronosticada=demanda_forecast,
            error_estandar=sigma_pronostico,        # σ viene del pronóstico
            eoq=eoq,
            stock_seguridad=stock_seguridad,
            precio_venta=params.precio_venta,
            costo_unitario=params.costo_unitario,
            costo_por_pedido=params.costo_por_pedido,
            costo_mantener=params.costo_mantener,
            costo_ruptura=params.costo_ruptura,
            factor_incertidumbre=params.factor_incertidumbre,
            n_iteraciones=params.n_iteraciones,
        )

        # ---- PASO 4: REPORTE ESTADÍSTICO ----
        stats_a = calcular_estadisticas(
            resultado_sim["utilidades_a"],
            resultado_sim["rupturas_a"],
            params.n_iteraciones,
        )
        stats_b = calcular_estadisticas(
            resultado_sim["utilidades_b"],
            resultado_sim["rupturas_b"],
            params.n_iteraciones,
        )

        hist_a = calcular_histograma(resultado_sim["utilidades_a"])
        hist_b = calcular_histograma(resultado_sim["utilidades_b"])

        cdf_a = calcular_distribucion_acumulada(resultado_sim["utilidades_a"])
        cdf_b = calcular_distribucion_acumulada(resultado_sim["utilidades_b"])

        comparacion = generar_reporte_comparativo(
            stats_a, stats_b,
            resultado_sim["Q_a"],
            resultado_sim["Q_b"],
        )

        # Respuesta estructurada: cada sección corresponde a un módulo del DSS
        return {
            "pronostico": resultado_pronostico,
            "inventario": resultado_inventario,
            "simulacion": {
                "Q_a":           resultado_sim["Q_a"],
                "Q_b":           resultado_sim["Q_b"],
                "sigma_usada":   resultado_sim["sigma_usada"],
                "n_iteraciones": resultado_sim["n_iteraciones"],
                "escenario_a":   stats_a,
                "escenario_b":   stats_b,
                "histograma_a":  hist_a,
                "histograma_b":  hist_b,
                "cdf_a":         cdf_a,
                "cdf_b":         cdf_b,
            },
            "comparacion": comparacion,
        }

    except ValueError as e:
        # Error de validación de datos (ej: demanda negativa, margen negativo)
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        # Error interno inesperado: se devuelve un mensaje claro sin exponer el stack
        raise HTTPException(
            status_code=500,
            detail=f"Error interno en el motor de cálculo: {str(e)}"
        )
