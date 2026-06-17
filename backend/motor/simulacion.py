"""
Motor de Simulación — Monte Carlo
==================================
Simula 10,000 escenarios de demanda aleatoria para medir el RIESGO del
sistema de inventario bajo incertidumbre.

Modelo corregido — Order-Up-To (nivel de cobertura S):
  En cada período la empresa decide hasta qué nivel S cubre su inventario.
  La variable de política NO es el lote EOQ, sino el nivel de cobertura:
    · Escenario A: S_A = demanda pronosticada (μ)     → sin colchón
    · Escenario B: S_B = demanda pronosticada + SS     → con colchón

  El EOQ define el costo de ordenar:
    pedidos_por_período = demanda_pronosticada / EOQ

  Por cada iteración (demanda d ~ Normal(μ, σ)):
    vendido  = min(d, S)
    sobrante = max(S − d, 0)
    perdido  = max(d − S, 0)
    utilidad = vendido × margen
               − sobrante × costo_mantener
               − pedidos_por_período × costo_por_pedido
               − perdido × costo_ruptura

Por qué distribución Normal:
  La demanda de repuestos en un período agrega muchas ventas individuales
  independientes → el Teorema Central del Límite justifica la Normal.
  La desviación σ proviene del modelo de regresión lineal, lo que hace
  que la simulación sea trazable a los datos reales.
"""

import numpy as np


def ejecutar_simulacion(
    demanda_pronosticada: float,
    error_estandar: float,
    eoq: float,
    stock_seguridad: float,
    precio_venta: float,
    costo_unitario: float,
    costo_por_pedido: float,
    costo_mantener: float,
    costo_ruptura: float,
    factor_incertidumbre: float = 1.0,
    n_iteraciones: int = 10000,
    semilla: int = 42,
) -> dict:
    """
    Ejecuta la simulación Monte Carlo con el modelo Order-Up-To.

    Parámetros
    ----------
    demanda_pronosticada : μ — media de la distribución de demanda (del pronóstico)
    error_estandar       : σ — desviación estándar (del pronóstico)
    eoq                  : lote económico (define el costo de ordenar, no el stock)
    stock_seguridad      : colchón de inventario para el Escenario B
    precio_venta         : CRC por unidad vendida
    costo_unitario       : CRC por unidad comprada
    costo_por_pedido     : CRC fijo por orden emitida
    costo_mantener       : CRC por unidad sobrante al final del período
    costo_ruptura        : CRC por unidad de demanda no satisfecha (venta perdida)
    factor_incertidumbre : multiplicador sobre σ (para análisis de sensibilidad)
    n_iteraciones        : número de escenarios Monte Carlo (mínimo 10,000)
    semilla              : semilla aleatoria para reproducibilidad

    Retorna
    -------
    dict con utilidades de A y B, indicadores de ruptura y parámetros usados
    """
    np.random.seed(semilla)

    # Desviación estándar efectiva: el factor permite preguntar
    # "¿qué pasa si la demanda es un 20% más volátil de lo que sugiere el modelo?"
    sigma_efectiva = error_estandar * factor_incertidumbre

    # Margen bruto por unidad vendida
    margen = precio_venta - costo_unitario

    # El EOQ determina cuántas órdenes se emiten en el período,
    # y por tanto el costo de ordenar total.
    pedidos_por_periodo = demanda_pronosticada / max(eoq, 1.0)

    # ------------------------------------------------------------------
    # Niveles de cobertura (order-up-to level S)
    # ------------------------------------------------------------------
    # A: cubre exactamente la demanda esperada → cualquier demanda sobre μ genera ruptura
    S_a = float(demanda_pronosticada)
    # B: cubre demanda esperada + colchón de seguridad → absorbe variabilidad hasta 95%
    S_b = float(demanda_pronosticada + stock_seguridad)

    # ------------------------------------------------------------------
    # Generación de escenarios de demanda (misma muestra para ambos escenarios)
    # ------------------------------------------------------------------
    demandas = np.random.normal(loc=demanda_pronosticada, scale=sigma_efectiva, size=n_iteraciones)
    # La demanda no puede ser negativa
    demandas = np.maximum(demandas, 0.0)

    # ------------------------------------------------------------------
    # Evaluar utilidad en cada escenario para cada política
    # ------------------------------------------------------------------
    utilidades_a, rupturas_a = _calcular_utilidades_vectorizado(
        demandas, S_a, margen, costo_mantener, pedidos_por_periodo, costo_por_pedido, costo_ruptura,
    )
    utilidades_b, rupturas_b = _calcular_utilidades_vectorizado(
        demandas, S_b, margen, costo_mantener, pedidos_por_periodo, costo_por_pedido, costo_ruptura,
    )

    return {
        "utilidades_a": utilidades_a.tolist(),
        "utilidades_b": utilidades_b.tolist(),
        "rupturas_a":   int(np.sum(rupturas_a)),
        "rupturas_b":   int(np.sum(rupturas_b)),
        "S_a":          round(S_a, 2),
        "S_b":          round(S_b, 2),
        "sigma_usada":  round(float(sigma_efectiva), 2),
        "n_iteraciones": n_iteraciones,
    }


def _calcular_utilidades_vectorizado(
    demandas: np.ndarray,
    S: float,
    margen: float,
    costo_mantener: float,
    pedidos_por_periodo: float,
    costo_por_pedido: float,
    costo_ruptura: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula la utilidad de cada escenario dado el nivel de cobertura S.

    Modelo Order-Up-To de un período:
      · La empresa cubre hasta S unidades disponibles.
      · Se realiza la demanda aleatoria d.
      · vendido  = min(d, S) — no se puede vender más de lo disponible.
      · sobrante = max(S − d, 0) — inventario no vendido, genera costo de mantener.
      · perdido  = max(d − S, 0) — demanda insatisfecha, genera costo de ruptura.
      · El costo de ordenar se paga independientemente de la demanda realizada.

    Utilidad = vendido × margen
               − sobrante × costo_mantener
               − pedidos_por_período × costo_por_pedido
               − perdido × costo_ruptura
    """
    vendido  = np.minimum(demandas, S)
    sobrante = np.maximum(S - demandas, 0.0)
    perdido  = np.maximum(demandas - S, 0.0)

    utilidades = (
        vendido  * margen
        - sobrante * costo_mantener
        - pedidos_por_periodo * costo_por_pedido
        - perdido  * costo_ruptura
    )

    hay_ruptura = perdido > 0.0

    return utilidades, hay_ruptura
