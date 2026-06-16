# Decisión Core DSS — IF7200

Sistema de Soporte a Decisiones para una PyME importadora de repuestos.
Integra **Pronóstico** (Regresión Lineal), **Optimización de Inventario** (EOQ) y **Simulación de Riesgo** (Monte Carlo) en un pipeline cuantitativo completo.

## Arquitectura

```
├── backend/          ← Motor de cálculo (Python + FastAPI)
│   ├── main.py       ← Servidor REST con CORS
│   ├── requirements.txt
│   └── motor/
│       ├── pronostico.py   ← Regresión lineal (scikit-learn)
│       ├── inventario.py   ← EOQ, Stock de Seguridad, Punto de Reorden
│       ├── simulacion.py   ← Monte Carlo 10,000 iteraciones
│       └── reportes.py     ← VaR, IC 95%, comparación A vs B
│
└── Frontend/Frontend-Metodos_Cuantitativos/   ← UI (Angular 21)
    └── src/app/
        ├── services/dss.service.ts   ← Llamadas HTTP al backend
        ├── models/dss.models.ts      ← Tipos TypeScript
        └── components/dashboard/    ← Panel gerencial principal
```

## Requisitos Previos

- **Python 3.11+** con `pip`
- **Node.js 20+** con `npm`
- **Angular CLI 21**: `npm install -g @angular/cli`

## Cómo Ejecutar

### 1. Backend (FastAPI)

```bash
cd backend

# Crear entorno virtual (recomendado)
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Iniciar el servidor
uvicorn main:app --reload --port 8000
```

El backend queda en: `http://localhost:8000`
- Documentación interactiva (Swagger): `http://localhost:8000/docs`
- Verificar estado: `http://localhost:8000/api/salud`

### 2. Frontend (Angular)

```bash
cd Frontend/Frontend-Metodos_Cuantitativos

npm install
ng serve
```

La aplicación queda en: `http://localhost:4200`

> Ambos deben estar corriendo al mismo tiempo. El frontend llama al backend en `localhost:8000`.

## Uso Rápido

1. Abrí `http://localhost:4200` en el navegador.
2. Presioná **"Cargar ejemplo"** para pre-llenar los datos de la PyME importadora.
3. Presioná **"Analizar"** para ejecutar el pipeline completo.
4. Explorá los resultados en las pestañas: Pronóstico, Inventario, Simulación, Comparación.
5. Mové el slider de **"Factor de incertidumbre"** para ver el análisis de sensibilidad en tiempo real.

## Endpoints del Backend

| Método | Ruta                | Descripción                              |
|--------|---------------------|------------------------------------------|
| GET    | `/api/salud`        | Verifica que el servidor está activo     |
| GET    | `/api/datos-ejemplo`| Parámetros de ejemplo (repuestos PyME)   |
| POST   | `/api/analizar`     | Pipeline completo: pronóstico → EOQ → MC |

### Ejemplo de llamada a `/api/analizar`

```json
{
  "demanda_historica": [420, 445, 410, 460, 480, 435, 500, 470, 515, 490, 530, 505],
  "costo_unitario": 15000,
  "precio_venta": 28000,
  "costo_por_pedido": 85000,
  "costo_mantener": 2500,
  "costo_ruptura": 12000,
  "lead_time": 2,
  "nivel_servicio": 0.95,
  "n_iteraciones": 10000,
  "factor_incertidumbre": 1.0
}
```

## Cadena Lógica del DSS

```
Datos históricos
      │
      ▼
Regresión Lineal ──→ demanda pronosticada (μ) + error estándar (σ)
                                    │                    │
                                    ▼                    │
                              EOQ = √(2Dμ S/H)           │
                              SS  = Z·σ·√(lead_time) ◄───┘
                              ROP = D·lead_time + SS
                                    │
                                    ▼
                      Monte Carlo: D_sim ~ Normal(μ, σ·factor)
                      Evaluado para A (EOQ) y B (EOQ + SS)
                                    │
                                    ▼
                      Media, Desv., IC 95%, VaR, Prob. Éxito/Ruptura
```

El σ del pronóstico no es un número arbitrario: **surge de los datos históricos** y conecta los tres módulos.
