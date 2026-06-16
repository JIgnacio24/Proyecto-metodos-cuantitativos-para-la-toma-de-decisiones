"""
Motor de Pronóstico — Regresión Lineal Simple
=============================================
Aplica regresión lineal sobre los datos históricos de demanda para:
  1. Estimar la demanda del próximo período (pronóstico puntual).
  2. Calcular el error estándar de los residuos (σ), que representa la
     "incertidumbre" del modelo y es la base de la simulación Monte Carlo.

La conexión clave del DSS:
  σ (error estándar del pronóstico) → Stock de Seguridad (inventario)
                                    → Desviación de Monte Carlo (simulación)
Así la incertidumbre del sistema no es inventada: surge de los datos reales.
"""

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score


def calcular_pronostico(demanda_historica: list[float]) -> dict:
    """
    Ajusta un modelo de regresión lineal Y = β0 + β1·X sobre los períodos.

    Parámetros
    ----------
    demanda_historica : list[float]
        Demanda observada por período (mínimo 3 puntos para regresión válida).

    Retorna
    -------
    dict con:
      - periodos            : números de período [1, 2, ..., n]
      - demanda_historica   : los datos tal como se recibieron
      - valores_ajustados   : Ŷ = β0 + β1·X para cada período histórico
      - demanda_pronosticada: Ŷ para el período n+1
      - error_estandar      : √(SSE / (n-2)) — desviación de los residuos
      - r_cuadrado          : coeficiente de determinación R²
      - pendiente           : β1 (tendencia por período)
      - intercepto          : β0
    """
    n = len(demanda_historica)

    # X: índice de período (1, 2, ..., n) — variable independiente (tiempo)
    X = np.arange(1, n + 1).reshape(-1, 1)
    # Y: demanda observada — variable dependiente
    Y = np.array(demanda_historica, dtype=float)

    # Ajuste del modelo de regresión lineal con scikit-learn
    modelo = LinearRegression()
    modelo.fit(X, Y)

    # Valores ajustados por el modelo (Y sombrero): lo que el modelo "predice" para cada período
    y_ajustados = modelo.predict(X)

    # Residuos: diferencia entre la demanda real y la demanda modelada
    # Un residuo grande indica que el modelo no captura bien ese período
    residuos = Y - y_ajustados

    # Error estándar de los residuos (σ)
    # Fórmula: √(SSE / (n - 2))
    # Se divide entre (n-2) porque el modelo tiene 2 parámetros libres (β0 y β1)
    # Este σ mide qué tan dispersa es la demanda real alrededor de la línea de regresión
    if n > 2:
        error_estandar = float(np.sqrt(np.sum(residuos ** 2) / (n - 2)))
    else:
        # Con exactamente 2 puntos la regresión es perfecta; usamos std muestral como fallback
        error_estandar = float(np.std(Y, ddof=1))

    # Pronóstico para el siguiente período (n+1)
    siguiente_periodo = np.array([[n + 1]])
    demanda_pronosticada = float(modelo.predict(siguiente_periodo)[0])
    # La demanda no puede ser negativa (garantía mínima)
    demanda_pronosticada = max(demanda_pronosticada, 0.0)

    # R² mide qué porcentaje de la variabilidad de la demanda explica el modelo lineal
    # R² = 1.0 es ajuste perfecto; R² cercano a 0 indica que el tiempo no explica la demanda
    r_cuadrado = float(r2_score(Y, y_ajustados))

    return {
        "periodos": list(range(1, n + 1)),
        "demanda_historica": [float(d) for d in demanda_historica],
        "valores_ajustados": [round(float(v), 2) for v in y_ajustados],
        "demanda_pronosticada": round(demanda_pronosticada, 2),
        "error_estandar": round(error_estandar, 2),
        "r_cuadrado": round(r_cuadrado, 4),
        "pendiente": round(float(modelo.coef_[0]), 4),
        "intercepto": round(float(modelo.intercept_), 4),
        "n_periodos": n,
        "periodo_pronosticado": n + 1,
    }
