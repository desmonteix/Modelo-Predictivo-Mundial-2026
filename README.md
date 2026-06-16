# Predictor Fútbol 🏆

> Sistema de predicción de partidos de fútbol con modelos estadísticos y ML  
> Enfocado en el **Mundial FIFA** — Fase 1 de implementación

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy async |
| Modelos ML | Dixon-Coles, XGBoost ensemble, ELO |
| Base de datos | PostgreSQL 15 |
| Caché | Redis 7 |
| Frontend | React 18 + TypeScript + Vite |
| Contenedores | Docker + Docker Compose |

---

## Requisitos previos

- Docker Desktop instalado y corriendo
- API key de [football-data.org](https://www.football-data.org/client/register) (gratuita)

---

## Configuración inicial

```bash
# 1. Clonar el repositorio y entrar al directorio
cd "Predictor Futbol"

# 2. Copiar y editar las variables de entorno
copy .env.example .env
# Editar .env y poner tu API key de football-data.org

# 3. Levantar todos los servicios
docker-compose up -d

# 4. Esperar a que PostgreSQL esté listo (~15 segundos)
docker-compose logs -f postgres
```

## Ingestión de datos del Mundial

```bash
# Descargar datos del Mundial 2022 y 2026
docker-compose exec api python data/ingest_world_cup.py \
  --api-key TU_API_KEY \
  --seasons 2022 2026
```

> **Nota**: La API gratuita de football-data.org tiene un límite de 10 llamadas/minuto.
> El script respeta ese límite automáticamente (espera 6 segundos entre llamadas).

---

## Acceso a los servicios

| Servicio | URL |
|---------|-----|
| 🌐 Frontend (UI) | http://localhost:5173 |
| 🔌 API Backend | http://localhost:8000 |
| 📖 Documentación API | http://localhost:8000/api/docs |
| 🗄️ PostgreSQL | localhost:5432 |
| ⚡ Redis | localhost:6379 |

---

## API Key requerida

**football-data.org** — Plan gratuito:
- Registro en: https://www.football-data.org/client/register
- Incluye: Mundial FIFA, Champions League, Liga, Premier League
- Límite: 10 llamadas/minuto

---

## Estructura del proyecto

```
Predictor Futbol/
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── models/
│   │   ├── dixon_coles.py         # Poisson bivariada
│   │   ├── xgboost_result.py      # Ensemble 1X2
│   │   └── corners_fouls_model.py # Corners + Faltas
│   ├── features/
│   │   ├── temporal_decay.py      # w(t) = e^(-λ·Δt)
│   │   └── elo.py                 # Sistema ELO
│   ├── routers/
│   │   ├── predictions.py         # POST /predict
│   │   ├── matches.py             # GET /matches
│   │   └── teams.py               # GET /teams
│   ├── db/
│   │   ├── schema.sql             # Schema PostgreSQL
│   │   └── connection.py          # SQLAlchemy async
│   └── data/
│       └── ingest_world_cup.py    # Script de ingestión
├── frontend/
│   └── src/
│       ├── App.tsx                # Layout + routing
│       ├── pages/
│       │   ├── Dashboard.tsx      # Panel principal
│       │   ├── PrediccionPage.tsx # UI de predicción
│       │   └── EquiposPage.tsx    # Rankings ELO
│       └── components/
│           ├── GoalDistChart.tsx  # Distribución goles
│           ├── ProbabilityBar.tsx # Barra 1X2
│           ├── ConfidenceBadge.tsx
│           └── FormStrip.tsx
├── docker-compose.yml
└── .env.example
```

---

## Modelos implementados

### 1. Dixon-Coles (goles)
Poisson bivariada con corrección de dependencia para resultados 0-0, 1-0, 0-1, 1-1.
Parámetros: α (ataque), β (defensa), γ (ventaja local), ρ (correlación).

### 2. XGBoost Ensemble (resultado 1X2)
Stack de XGBoost + Random Forest + Logistic Regression.
Meta-learner logístico sobre las probabilidades de los modelos base.

### 3. Sistema ELO
Factor K diferenciado por competición (Mundial ×2.0, Champions ×1.5).
Ajuste por margen de victoria (×1.75 para diferencias ≥3 goles).

### 4. Ponderación temporal
`w(t) = e^(-0.02 · semanas_desde_partido)`  
Breakpoints duros por cambio de entrenador.  
Descarte automático cuando peso < 0.05.

---

## Siguiente fase (Phase 2)

- Integración con API-Football para xG, pressing (PPDA), jugadores lesionados
- Airflow DAGs para actualización automática cada 6 horas
- MLflow para versionado de modelos
- Entrenamiento automático tras cada jornada
