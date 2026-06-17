# Decisión Core DSS — IF7200

Sistema de Soporte a Decisiones para una PyME importadora de repuestos.
Integra **Pronóstico** (Regresión Lineal), **Optimización de Inventario** (EOQ) y **Simulación de Riesgo** (Monte Carlo) en un pipeline cuantitativo completo, donde la incertidumbre del pronóstico alimenta directamente la optimización y la simulación.

---

## Estructura del Repositorio

```
Proyecto-metodos-cuantitativos-para-la-toma-de-decisiones/
│
├── README.md
│
├── backend/                          ← Motor de cálculo (Python + FastAPI)
│   ├── main.py                       ← Servidor REST · CORS · validación Pydantic
│   ├── requirements.txt              ← fastapi, uvicorn, numpy, scipy, scikit-learn
│   └── motor/
│       ├── __init__.py
│       ├── pronostico.py             ← Regresión lineal Y=β₀+β₁X (scikit-learn)
│       ├── inventario.py             ← EOQ, Stock de Seguridad, Punto de Reorden
│       ├── simulacion.py             ← Monte Carlo 10,000 iter. · modelo Order-Up-To
│       └── reportes.py               ← Media, IC 95%, VaR, Prob. Éxito/Ruptura, tabla A vs B
│
└── Frontend/
    └── Frontend-Metodos_Cuantitativos/   ← UI (Angular 21 · Tailwind 4 · Chart.js)
        ├── package.json
        ├── angular.json
        ├── tsconfig.json / tsconfig.app.json
        └── src/
            ├── main.ts
            ├── styles.css                ← @import "tailwindcss"
            ├── index.html
            └── app/
                ├── app.ts               ← Componente raíz
                ├── app.html             ← <router-outlet />
                ├── app.config.ts        ← provideRouter + provideHttpClient
                ├── app.routes.ts        ← Ruta "/" → DashboardComponent
                ├── models/
                │   └── dss.models.ts    ← Interfaces TypeScript del contrato con la API
                ├── services/
                │   └── dss.service.ts   ← HttpClient → POST /api/analizar
                └── components/
                    └── dashboard/
                        ├── dashboard.ts    ← Lógica · Chart.js · señales Angular
                        ├── dashboard.html  ← Panel gerencial (4 tabs · sliders sensibilidad)
                        └── dashboard.css
```

---

## Arquitectura del Pipeline (cadena lógica)

El DSS ejecuta los tres módulos **en secuencia**: la salida de cada uno alimenta al siguiente.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MÓDULO 1 — PRONÓSTICO (pronostico.py)                                  │
│                                                                         │
│  Entrada : demanda histórica [d₁, d₂, ..., dₙ]                         │
│  Modelo  : Regresión Lineal   Y = β₀ + β₁ · t                          │
│  Salidas : μ = demanda pronosticada para t = n+1                        │
│            σ = error estándar de los residuos  √(SSE / (n−2))          │
└──────────────────────┬──────────────────────────┬───────────────────────┘
                       │ μ                         │ σ  (vínculo clave)
                       ▼                           │
┌──────────────────────────────────────┐           │
│  MÓDULO 2 — INVENTARIO (inventario.py)│           │
│                                      │           │
│  EOQ = √(2 · μ · S / H)             │           │
│  SS  = Z · σ · √(lead_time) ◄───────────────────┘
│  ROP = μ · lead_time + SS            │
│                                      │
│  Salidas: EOQ, SS, ROP, costo total  │
└──────────────────────┬───────────────┘
                       │ EOQ, SS
                       │
┌──────────────────────▼───────────────────────────────────────────────────┐
│  MÓDULO 3 — SIMULACIÓN MONTE CARLO (simulacion.py)                       │
│                                                                          │
│  Modelo  : Order-Up-To (nivel de cobertura S)                            │
│  Demanda : D_sim ~ Normal(μ, σ · factor_incertidumbre)   [10,000 iter.]  │
│                                                                          │
│  Escenario A — S_A = μ           (sin colchón de seguridad)             │
│  Escenario B — S_B = μ + SS      (con colchón de seguridad)             │
│                                                                          │
│  Por iteración:                                                          │
│    vendido  = min(D_sim, S)                                              │
│    sobrante = max(S − D_sim, 0)   → costo de mantener                   │
│    perdido  = max(D_sim − S, 0)   → costo de ruptura                    │
│    Utilidad = vendido × margen                                           │
│               − sobrante × costo_mantener                               │
│               − (μ/EOQ) × costo_por_pedido                              │
│               − perdido × costo_ruptura                                  │
│                                                                          │
│  Salidas: distribución de 10,000 utilidades para A y B                  │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────────┐
│  MÓDULO 4 — REPORTE (reportes.py)                                        │
│                                                                          │
│  · Media y Desviación Estándar                                           │
│  · Intervalo de Confianza al 95%                                         │
│  · VaR al 95% (percentil 5 de las utilidades)                           │
│  · Probabilidad de Éxito (utilidad > 0)                                  │
│  · Probabilidad de Ruptura de Stock                                      │
│  · Tabla comparativa A vs B + recomendación gerencial                    │
└──────────────────────────────────────────────────────────────────────────┘
```

> **El σ no es arbitrario:** surge del error estándar de la regresión lineal aplicada a los datos históricos. Esto conecta matemáticamente los tres módulos y hace que la incertidumbre de la simulación sea trazable a los datos reales.

---

## Requisitos Previos

| Herramienta | Versión mínima |
|---|---|
| Python | 3.11+ |
| pip | cualquiera reciente |
| Node.js | 20+ |
| npm | 10+ |
| Angular CLI | 21 (`npm install -g @angular/cli`) |

---

## Cómo Ejecutar

### 1. Backend (FastAPI)

```bash
cd backend

# Crear entorno virtual (recomendado)
python -m venv venv

# Activar — Windows:
venv\Scripts\activate
# Activar — macOS/Linux:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Iniciar el servidor
uvicorn main:app --reload --port 8000
```

El backend queda disponible en `http://localhost:8000`

| URL | Descripción |
|---|---|
| `http://localhost:8000/docs` | Documentación interactiva Swagger |
| `http://localhost:8000/api/salud` | Verificar que el servidor está activo |

### 2. Frontend (Angular)

```bash
cd Frontend/Frontend-Metodos_Cuantitativos

npm install
ng serve
```

La aplicación queda disponible en `http://localhost:4200`

> Ambos procesos deben estar corriendo al mismo tiempo. El frontend llama al backend en `localhost:8000`.

---

## Uso Rápido

1. Abrí `http://localhost:4200` en el navegador.
2. Presioná **"Cargar ejemplo"** para pre-llenar los datos de la PyME importadora.
3. Presioná **"▶ Analizar"** para ejecutar el pipeline completo.
4. Explorá las cuatro pestañas de resultados:

| Pestaña | Contenido |
|---|---|
| 📈 Pronóstico | Gráfico de regresión lineal · R² · σ · demanda estimada |
| 📦 Inventario | EOQ · Stock de Seguridad · Punto de Reorden · desglose de costos |
| 🎲 Simulación | Histogramas A y B · CDF comparativa · métricas de riesgo |
| ⚖️ Comparación | Tabla A vs B · VaR · recomendación gerencial |

5. Mové el slider **"Factor de incertidumbre"** — al soltar, el sistema re-analiza automáticamente.

---

## Endpoints del Backend

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/salud` | Verifica que el servidor está activo |
| GET | `/api/datos-ejemplo` | Parámetros precargados (repuestos PyME) |
| POST | `/api/analizar` | Pipeline completo: pronóstico → EOQ → Monte Carlo → reporte |

### Cuerpo de la solicitud a `POST /api/analizar`

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

Todos los montos están en **Colones Costarricenses (CRC)**. Los tiempos están en períodos (meses en el escenario de ejemplo).
