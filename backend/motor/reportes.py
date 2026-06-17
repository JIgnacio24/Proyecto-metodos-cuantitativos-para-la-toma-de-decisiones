"""
Motor de Reportes — Estadísticas e Indicadores Gerenciales
===========================================================
Transforma los 10,000 resultados de la simulación Monte Carlo en
indicadores concretos para la toma de decisiones:

  - Media y Desviación Estándar : tendencia central y dispersión del resultado
  - Intervalo de Confianza 95%  : rango plausible del resultado esperado
  - VaR al 95%                  : pérdida máxima esperada en el peor 5% de casos
  - Probabilidad de Éxito       : % de escenarios con utilidad positiva
  - Probabilidad de Ruptura     : % de escenarios con quiebre de stock
  - Tabla Comparativa           : A vs B para guiar la decisión gerencial
  - Datos para Gráficos         : histograma y CDF para el frontend Angular
"""

import numpy as np


def calcular_estadisticas(
    utilidades: list[float],
    rupturas: int,
    n_iteraciones: int,
) -> dict:
    """
    Calcula el reporte estadístico completo de una distribución de utilidades.

    Parámetros
    ----------
    utilidades    : resultados de utilidad de las n_iteraciones simuladas
    rupturas      : número de iteraciones con ruptura de stock
    n_iteraciones : total de iteraciones (para calcular probabilidad de ruptura)

    Retorna
    -------
    dict con todos los indicadores clave para el panel gerencial
    """
    arr = np.array(utilidades, dtype=float)
    n = len(arr)

    # --- Estadísticas de posición y dispersión ---
    media = float(np.mean(arr))
    # ddof=1: estimador insesgado de la varianza (divide entre n-1, no n)
    std = float(np.std(arr, ddof=1))

    # --- Intervalo de Confianza al 95% para la media ---
    # Interpretación: "con 95% de confianza, la utilidad esperada real está en [IC_inf, IC_sup]"
    # Se usa la aproximación Normal por el TCL (n = 10,000 >> 30)
    error_estandar_media = std / np.sqrt(n)
    ic_inferior = float(media - 1.96 * error_estandar_media)
    ic_superior = float(media + 1.96 * error_estandar_media)

    # --- Valor en Riesgo (VaR) al 5% ---
    # El percentil 5 de las utilidades: "existe un 5% de probabilidad de obtener
    # una utilidad MENOR a este valor". Si es negativo, es la pérdida máxima esperada.
    var_95 = float(np.percentile(arr, 5))

    # --- Probabilidades ---
    # % de escenarios donde la empresa gana dinero (utilidad > 0)
    prob_exito = float(np.mean(arr > 0) * 100.0)

    # % de escenarios donde la demanda superó el inventario disponible
    prob_ruptura = float((rupturas / n_iteraciones) * 100.0)

    return {
        "media": round(media, 2),
        "desviacion_std": round(std, 2),
        "ic_95_inferior": round(ic_inferior, 2),
        "ic_95_superior": round(ic_superior, 2),
        "var_95": round(var_95, 2),
        "prob_exito": round(prob_exito, 2),
        "prob_ruptura": round(prob_ruptura, 2),
        "utilidad_minima": round(float(np.min(arr)), 2),
        "utilidad_maxima": round(float(np.max(arr)), 2),
        "mediana": round(float(np.median(arr)), 2),
        "percentil_25": round(float(np.percentile(arr, 25)), 2),
        "percentil_75": round(float(np.percentile(arr, 75)), 2),
    }


def calcular_histograma(utilidades: list[float], n_bins: int = 50) -> dict:
    """
    Prepara los datos del histograma de frecuencias para Chart.js en Angular.

    El histograma muestra la DISTRIBUCIÓN de las utilidades simuladas:
    qué rango de utilidades ocurre más frecuentemente.

    Parámetros
    ----------
    utilidades : resultados de la simulación
    n_bins     : número de barras del histograma (50 da buena resolución)

    Retorna
    -------
    dict con:
      - centros       : valor central de cada barra (eje X)
      - frecuencias   : cantidad de escenarios en cada barra (eje Y)
      - valor_esperado: media de las utilidades (para dibujar la línea roja)
    """
    arr = np.array(utilidades, dtype=float)

    frecuencias, bordes = np.histogram(arr, bins=n_bins)
    # Centro de cada bin: promedio entre el borde izquierdo y el derecho
    centros = (bordes[:-1] + bordes[1:]) / 2.0

    return {
        "centros": [round(float(c), 2) for c in centros],
        "frecuencias": [int(f) for f in frecuencias],
        "valor_esperado": round(float(np.mean(arr)), 2),
    }


def calcular_distribucion_acumulada(
    utilidades: list[float],
    n_puntos: int = 200,
) -> dict:
    """
    Calcula la Función de Distribución Acumulada (CDF) empírica.

    La CDF(x) = P(Utilidad ≤ x) = fracción de escenarios con utilidad ≤ x.

    Usos para el gerente:
      - Leer el VaR directamente en el gráfico (valor donde CDF = 0.05)
      - Ver la probabilidad de pérdida (valor donde la curva cruza Utilidad = 0)

    Parámetros
    ----------
    utilidades : resultados de la simulación
    n_puntos   : puntos de la curva a devolver (200 es suficiente para una curva suave)
    """
    arr = np.sort(np.array(utilidades, dtype=float))
    n = len(arr)

    # Probabilidad acumulada para cada valor ordenado: k/n para el k-ésimo valor
    probabilidades = np.arange(1, n + 1) / float(n)

    # Reducir a n_puntos para no enviar 10,000 puntos al frontend
    indices = np.linspace(0, n - 1, n_puntos, dtype=int)

    return {
        "valores": [round(float(arr[i]), 2) for i in indices],
        "probabilidades": [round(float(probabilidades[i]), 4) for i in indices],
    }


def _mejor_es(val_a: float, val_b: float, *, mayor_es_mejor: bool) -> str:
    """
    Retorna 'A', 'B' o '—' según qué escenario tiene el mejor valor.
    Los empates se marcan con '—' en lugar de asignar ganador arbitrario.
    """
    if val_a == val_b:
        return "—"
    if mayor_es_mejor:
        return "A" if val_a > val_b else "B"
    return "A" if val_a < val_b else "B"


def generar_reporte_comparativo(
    stats_a: dict,
    stats_b: dict,
    S_a: float,
    S_b: float,
) -> dict:
    """
    Genera la tabla comparativa A vs B y una recomendación textual.

    Compara ambas políticas en todas las dimensiones relevantes para
    que el gerente tome una decisión informada sobre el nivel de cobertura.

    Parámetros
    ----------
    stats_a : estadísticas del Escenario A (cobertura = demanda pronosticada)
    stats_b : estadísticas del Escenario B (cobertura = demanda + stock seguridad)
    S_a, S_b: nivel de cobertura (order-up-to level) de cada escenario
    """
    tabla = [
        {
            "metrica": "Nivel de Cobertura S (unidades)",
            "escenario_a": round(S_a, 0),
            "escenario_b": round(S_b, 0),
            "mejor": _mejor_es(S_a, S_b, mayor_es_mejor=False),
            "nota": "S_A = demanda pronosticada; S_B = S_A + stock de seguridad",
        },
        {
            "metrica": "Utilidad Esperada (CRC)",
            "escenario_a": stats_a["media"],
            "escenario_b": stats_b["media"],
            "mejor": _mejor_es(stats_a["media"], stats_b["media"], mayor_es_mejor=True),
            "nota": "Promedio de los 10,000 escenarios simulados",
        },
        {
            "metrica": "Desviación Estándar (CRC)",
            "escenario_a": stats_a["desviacion_std"],
            "escenario_b": stats_b["desviacion_std"],
            "mejor": _mejor_es(stats_a["desviacion_std"], stats_b["desviacion_std"], mayor_es_mejor=False),
            "nota": "Menor desviación = resultado más predecible (menos riesgo)",
        },
        {
            "metrica": "VaR al 95% (CRC)",
            "escenario_a": stats_a["var_95"],
            "escenario_b": stats_b["var_95"],
            "mejor": _mejor_es(stats_a["var_95"], stats_b["var_95"], mayor_es_mejor=True),
            "nota": "Pérdida máxima esperada en el peor 5% de los escenarios",
        },
        {
            "metrica": "Probabilidad de Éxito (%)",
            "escenario_a": stats_a["prob_exito"],
            "escenario_b": stats_b["prob_exito"],
            "mejor": _mejor_es(stats_a["prob_exito"], stats_b["prob_exito"], mayor_es_mejor=True),
            "nota": "% de escenarios donde la utilidad es positiva",
        },
        {
            "metrica": "Probabilidad de Ruptura de Stock (%)",
            "escenario_a": stats_a["prob_ruptura"],
            "escenario_b": stats_b["prob_ruptura"],
            "mejor": _mejor_es(stats_a["prob_ruptura"], stats_b["prob_ruptura"], mayor_es_mejor=False),
            "nota": "% de escenarios donde la demanda supera el nivel de cobertura",
        },
    ]

    recomendacion = _generar_recomendacion(stats_a, stats_b)

    return {
        "tabla": tabla,
        "recomendacion": recomendacion,
    }


def _generar_recomendacion(stats_a: dict, stats_b: dict) -> str:
    """
    Compara A y B en 3 criterios clave con comparación estricta (sin empates).
    Si un escenario gana 2 o más criterios → es el recomendado.
    """
    puntos_a = sum([
        stats_a["media"]        > stats_b["media"],          # mayor utilidad esperada
        stats_a["var_95"]       > stats_b["var_95"],         # mejor VaR (menos pérdida)
        stats_a["prob_ruptura"] < stats_b["prob_ruptura"],   # menor riesgo de ruptura
    ])
    puntos_b = sum([
        stats_b["media"]        > stats_a["media"],
        stats_b["var_95"]       > stats_a["var_95"],
        stats_b["prob_ruptura"] < stats_a["prob_ruptura"],
    ])

    if puntos_a >= 2:
        return (
            "El Escenario A (cobertura sin stock de seguridad) domina en la mayoría "
            "de los indicadores. Es la opción más eficiente en costo, aunque "
            "implica mayor riesgo de quedarse sin inventario. Recomendado si el "
            "costo de una venta perdida es bajo o si la demanda es muy predecible."
        )
    if puntos_b >= 2:
        return (
            "El Escenario B (cobertura con stock de seguridad) es preferible según la "
            "mayoría de los indicadores de riesgo. Aunque mantiene más inventario, "
            "ofrece mayor protección ante picos de demanda. Recomendado si el costo "
            "de una ruptura de stock (reputación, clientes perdidos) supera el costo "
            "adicional de mantener el inventario extra."
        )
    return (
        "Los escenarios están equilibrados en los criterios principales. "
        "La decisión depende de la tolerancia al riesgo: prefiera A si prioriza "
        "eficiencia en costo, y B si prioriza continuidad del servicio al cliente."
    )
