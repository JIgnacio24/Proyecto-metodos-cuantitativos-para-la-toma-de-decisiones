"""
Motor de Inventario — EOQ, Stock de Seguridad y Punto de Reorden
================================================================
Implementa el modelo de Lote Económico de Pedido (EOQ) clásico y sus extensiones.

Vínculo con el pronóstico:
  El ERROR ESTÁNDAR del modelo de regresión lineal (σ) se usa directamente
  como la desviación de la demanda para calcular el stock de seguridad.
  Esto conecta matemáticamente el módulo de pronóstico con el de inventario.

Fórmulas principales:
  EOQ = √(2·D·S / H)
  SS  = Z · σ · √(lead_time)
  ROP = D·lead_time + SS
"""

import numpy as np
from scipy import stats


def calcular_eoq(
    demanda: float,
    costo_por_pedido: float,
    costo_mantener: float,
) -> float:
    """
    Calcula el Lote Económico de Pedido (EOQ).

    La fórmula EOQ minimiza el costo total del sistema de inventario, que es
    la suma de: costo de ordenar (disminuye con lotes grandes) + costo de
    mantener (aumenta con lotes grandes). El mínimo ocurre donde se cruzan.

    Parámetros
    ----------
    demanda         : D — demanda del período (unidades)
    costo_por_pedido: S — costo fijo por emitir una orden de compra (CRC)
    costo_mantener  : H — costo de mantener una unidad por período (CRC)

    Retorna
    -------
    float : cantidad óptima a pedir por orden (unidades)
    """
    if costo_mantener <= 0:
        raise ValueError("El costo de mantener debe ser mayor a cero.")
    if demanda <= 0:
        raise ValueError("La demanda debe ser mayor a cero.")

    eoq = np.sqrt((2.0 * demanda * costo_por_pedido) / costo_mantener)
    return float(eoq)


def calcular_stock_seguridad(
    error_estandar: float,
    lead_time: int,
    nivel_servicio: float = 0.95,
) -> float:
    """
    Calcula el Stock de Seguridad (SS) basado en el error del pronóstico.

    SS = Z · σ · √(lead_time)

    Donde:
      Z          : percentil de la distribución Normal para el nivel de servicio
                   (Z = 1.645 para 95%, Z = 1.282 para 90%, Z = 2.326 para 99%)
      σ          : error estándar del pronóstico (viene del módulo pronostico.py)
      √(lead_time): factor que amplía la incertidumbre a lo largo del tiempo de espera

    Conexión clave: σ no es un número arbitrario, proviene del modelo de regresión
    y refleja la variabilidad REAL observada en los datos históricos.

    Parámetros
    ----------
    error_estandar : σ de los residuos del modelo de regresión lineal
    lead_time      : períodos que tarda en llegar un pedido
    nivel_servicio : fracción [0.5, 0.999] — qué tan seguido queremos tener stock
    """
    # Z es el valor crítico de la distribución Normal estándar
    # Ejemplo: ppf(0.95) = 1.645 → cubre el 95% de los escenarios de demanda
    z = float(stats.norm.ppf(nivel_servicio))

    # Durante el lead_time, la incertidumbre se acumula según la raíz del tiempo
    # (propiedad de la varianza de la suma de variables aleatorias independientes)
    stock_seguridad = z * error_estandar * np.sqrt(lead_time)
    return max(float(stock_seguridad), 0.0)


def calcular_punto_reorden(
    demanda: float,
    lead_time: int,
    stock_seguridad: float,
) -> float:
    """
    Calcula el Punto de Reorden (ROP).

    ROP = D_promedio_durante_lead_time + SS

    Interpretación gerencial:
      "Cuando el inventario baje a ROP unidades, emita un nuevo pedido."
      El pedido llegará exactamente cuando el stock normal se agote.
      El stock de seguridad cubre la demanda por encima del promedio durante la espera.

    Parámetros
    ----------
    demanda        : demanda promedio por período
    lead_time      : períodos de espera hasta recibir el pedido
    stock_seguridad: buffer para cubrir variabilidad durante el lead_time
    """
    demanda_durante_espera = demanda * lead_time
    return float(demanda_durante_espera + stock_seguridad)


def calcular_costo_total(
    demanda: float,
    eoq: float,
    costo_por_pedido: float,
    costo_mantener: float,
    costo_unitario: float,
) -> dict:
    """
    Calcula y desglosa el costo total del sistema de inventario con cantidad EOQ.

    TC = (D/EOQ)·S + (EOQ/2)·H + D·c

    Componentes:
      (D/EOQ)·S  : costo de ordenar — número de pedidos × costo por pedido
      (EOQ/2)·H  : costo de mantener — inventario promedio × costo de mantener
      D·c        : costo de compra de todas las unidades del período

    Parámetros
    ----------
    demanda         : D — demanda del período
    eoq             : Q* — lote económico calculado
    costo_por_pedido: S
    costo_mantener  : H
    costo_unitario  : c — precio de compra por unidad (CRC)
    """
    num_pedidos = demanda / eoq
    costo_ordenar = num_pedidos * costo_por_pedido
    costo_mantener_total = (eoq / 2.0) * costo_mantener
    costo_compra = demanda * costo_unitario
    costo_total = costo_ordenar + costo_mantener_total + costo_compra

    return {
        "costo_ordenar": round(costo_ordenar, 2),
        "costo_mantener_total": round(costo_mantener_total, 2),
        "costo_compra": round(costo_compra, 2),
        "costo_total": round(costo_total, 2),
        "num_pedidos": round(num_pedidos, 2),
    }


def calcular_inventario(
    demanda_pronosticada: float,
    error_estandar: float,
    costo_unitario: float,
    costo_por_pedido: float,
    costo_mantener: float,
    lead_time: int,
    nivel_servicio: float = 0.95,
) -> dict:
    """
    Orquesta el cálculo completo del sistema de inventario.

    Secuencia:
      1. EOQ          → cantidad óptima de cada pedido
      2. Stock Seg.   → buffer basado en σ del pronóstico y lead_time
      3. Punto Reorden→ nivel de inventario que dispara un nuevo pedido
      4. Costo Total  → desglose de costos del sistema

    Parámetros
    ----------
    demanda_pronosticada: D — del módulo de pronóstico
    error_estandar      : σ — del módulo de pronóstico (conexión entre módulos)
    costo_unitario      : c — CRC por unidad comprada
    costo_por_pedido    : S — CRC fijo por orden emitida
    costo_mantener      : H — CRC por unidad por período
    lead_time           : períodos de reposición
    nivel_servicio      : fracción de escenarios en los que se quiere tener stock
    """
    eoq = calcular_eoq(demanda_pronosticada, costo_por_pedido, costo_mantener)
    stock_seguridad = calcular_stock_seguridad(error_estandar, lead_time, nivel_servicio)
    punto_reorden = calcular_punto_reorden(demanda_pronosticada, lead_time, stock_seguridad)
    desglose_costos = calcular_costo_total(
        demanda_pronosticada, eoq, costo_por_pedido, costo_mantener, costo_unitario
    )

    # Inventario promedio = EOQ/2 (ciclo) + SS (colchón de seguridad)
    inventario_promedio = (eoq / 2.0) + stock_seguridad

    return {
        "eoq": round(eoq, 2),
        "stock_seguridad": round(stock_seguridad, 2),
        "punto_reorden": round(punto_reorden, 2),
        "inventario_promedio": round(inventario_promedio, 2),
        "nivel_servicio_usado": nivel_servicio,
        "lead_time": lead_time,
        "costos": desglose_costos,
    }
