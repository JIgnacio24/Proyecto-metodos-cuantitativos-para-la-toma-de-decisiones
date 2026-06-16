"""
Motor de Simulación — Monte Carlo
==================================
Simula 10,000 escenarios de demanda aleatoria para medir el RIESGO del
sistema de inventario bajo incertidumbre.

Metodología:
  1. En cada iteración se genera una demanda aleatoria D_sim ~ Normal(μ, σ)
     donde μ = demanda pronosticada y σ = error estándar del pronóstico.
  2. Se calcula la utilidad del período para dos políticas de inventario:
       Escenario A: pedir EOQ (lote económico sin colchón de seguridad)
       Escenario B: pedir EOQ + Stock de Seguridad (política conservadora)
  3. Se acumulan 10,000 utilidades por escenario, formando una distribución
     empírica que permite medir probabilidades de pérdida y ruptura de stock.

Por qué distribución Normal:
  - La demanda de repuestos en un período agrega muchas ventas individuales
    independientes → el Teorema Central del Límite justifica la Normal.
  - La desviación NO es arbitraria: proviene del modelo de regresión lineal,
    lo que hace que la simulación sea trazable a los datos reales.
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
    Ejecuta la simulación Monte Carlo completa.

    Parámetros
    ----------
    demanda_pronosticada : μ — media de la distribución de demanda (del pronóstico)
    error_estandar       : σ — desviación estándar (del pronóstico)
    eoq                  : cantidad a pedir en el Escenario A
    stock_seguridad      : unidades adicionales para el Escenario B
    precio_venta         : CRC por unidad vendida
    costo_unitario       : CRC por unidad comprada
    costo_por_pedido     : CRC fijo por orden emitida
    costo_mantener       : CRC por unidad sobrante al final del período
    costo_ruptura        : CRC por unidad de demanda no satisfecha (venta perdida)
    factor_incertidumbre : multiplicador sobre σ (para análisis de sensibilidad)
    n_iteraciones        : número de escenarios Monte Carlo (mínimo 10,000)
    semilla              : semilla del generador aleatorio para reproducibilidad

    Retorna
    -------
    dict con utilidades de A y B, indicadores de ruptura y parámetros usados
    """
    # Generador de números aleatorios con semilla fija → resultados reproducibles
    rng = np.random.default_rng(semilla)

    # Desviación estándar efectiva de la simulación
    # El factor_incertidumbre permite al gerente preguntar: "¿qué pasa si la
    # demanda es un 20% más volátil de lo que el modelo sugiere?"
    sigma_efectiva = error_estandar * factor_incertidumbre

    # ------------------------------------------------------------------
    # Generación de escenarios de demanda
    # ------------------------------------------------------------------
    # Distribución Normal: la mayoría de escenarios cercanos a la media,
    # con colas que capturan tanto demanda muy baja como muy alta
    demandas_simuladas = rng.normal(
        loc=demanda_pronosticada,
        scale=sigma_efectiva,
        size=n_iteraciones,
    )
    # Restricción: la demanda no puede ser negativa (no hay "devoluciones" masivas)
    demandas_simuladas = np.maximum(demandas_simuladas, 0.0)

    # ------------------------------------------------------------------
    # Escenario A: pedir EOQ (sin stock de seguridad)
    # Política agresiva → menor costo de mantener, mayor riesgo de ruptura
    # ------------------------------------------------------------------
    Q_a = max(float(eoq), 1.0)
    utilidades_a, rupturas_a = _calcular_utilidades_vectorizado(
        demandas_simuladas, Q_a,
        precio_venta, costo_unitario, costo_por_pedido, costo_mantener, costo_ruptura,
    )

    # ------------------------------------------------------------------
    # Escenario B: pedir EOQ + Stock de Seguridad
    # Política conservadora → mayor costo de mantener, menor riesgo de ruptura
    # ------------------------------------------------------------------
    Q_b = max(float(eoq + stock_seguridad), 1.0)
    utilidades_b, rupturas_b = _calcular_utilidades_vectorizado(
        demandas_simuladas, Q_b,
        precio_venta, costo_unitario, costo_por_pedido, costo_mantener, costo_ruptura,
    )

    return {
        "utilidades_a": utilidades_a.tolist(),
        "utilidades_b": utilidades_b.tolist(),
        "rupturas_a": int(np.sum(rupturas_a)),
        "rupturas_b": int(np.sum(rupturas_b)),
        "Q_a": round(Q_a, 2),
        "Q_b": round(Q_b, 2),
        "sigma_usada": round(float(sigma_efectiva), 2),
        "n_iteraciones": n_iteraciones,
    }


def _calcular_utilidades_vectorizado(
    demandas: np.ndarray,
    cantidad_pedido: float,
    precio_venta: float,
    costo_unitario: float,
    costo_por_pedido: float,
    costo_mantener: float,
    costo_ruptura: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula la utilidad de cada escenario para un nivel de inventario fijo.

    Modelo de inventario de un solo período:
      - Se ordena Q unidades al comienzo del período (decisión fija).
      - Se realiza la demanda D (aleatoria).
      - Se vende min(D, Q): la empresa no puede vender más de lo que tiene.
      - El sobrante max(0, Q−D) genera costo de mantenimiento.
      - La faltante max(0, D−Q) genera costo de ruptura (venta perdida + penalización).

    Utilidad = Ingresos − Costo de compra − Costo de mantener − Costo ruptura − Costo pedido

    Parámetros
    ----------
    demandas      : array de n_iteraciones demandas simuladas
    cantidad_pedido: Q — unidades pedidas según la política evaluada
    (resto)       : parámetros de costo y precio en CRC

    Retorna
    -------
    (utilidades, hay_ruptura) — arrays de longitud n_iteraciones
    """
    # Unidades efectivamente vendidas (no se puede vender más de lo disponible)
    unidades_vendidas = np.minimum(demandas, cantidad_pedido)

    # Inventario sobrante al cierre del período (no vendido)
    sobrante = np.maximum(0.0, cantidad_pedido - demandas)

    # Unidades de demanda insatisfecha (clientes que no pudieron comprar)
    ruptura = np.maximum(0.0, demandas - cantidad_pedido)

    # --- Ingresos ---
    ingresos = unidades_vendidas * precio_venta

    # --- Costos ---
    # Costo de comprar el lote: se paga por todas las Q unidades ordenadas
    costo_compra = cantidad_pedido * costo_unitario

    # Costo de mantener el sobrante: penalización por inmovilizar capital en inventario
    costo_mantener_total = sobrante * costo_mantener

    # Costo de ruptura de stock: penalización por venta perdida + daño a la reputación
    costo_ruptura_total = ruptura * costo_ruptura

    # Costo fijo del pedido: aplica siempre que se emite una orden (costo administrativo)
    costo_pedido_total = np.full(len(demandas), costo_por_pedido)

    # Utilidad neta del período
    utilidades = (
        ingresos
        - costo_compra
        - costo_mantener_total
        - costo_ruptura_total
        - costo_pedido_total
    )

    # Indicador binario: ¿hubo ruptura en este escenario?
    hay_ruptura = ruptura > 0.0

    return utilidades, hay_ruptura
