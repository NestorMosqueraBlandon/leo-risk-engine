# Leo Risk Engine

> Student dropout risk prediction engine using survival analysis and machine learning.

## 1. Overview

Leo Risk Engine is a service that ingests student academic, financial, attendance, and engagement data to produce calibrated risk scores and survival curves. It predicts the probability of a student dropping out within configurable time horizons, explains the key drivers behind each prediction, and surfaces actionable recommendations.

The system is designed for educational institutions that need early-warning capabilities to intervene before students disengage or drop out.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Layer (FastAPI)                  │
│  /score  /models  /health  /ready                       │
├─────────────────────────────────────────────────────────┤
│                   Inference Pipeline                    │
│  Predictor ──► Model Loader ──► Calibration ──► Explain │
├─────────────────────────────────────────────────────────┤
│                   Training Pipeline                     │
│  Datasets ──► Splits ──► Pipelines ──► Evaluation       │
├─────────────────────────────────────────────────────────┤
│                  Feature Engineering                    │
│  Academic │ Attendance │ Financial │ Engagement │ ...   │
├─────────────────────────────────────────────────────────┤
│                     Domain Layer                        │
│  Entities │ Value Objects │ Policies                    │
├─────────────────────────────────────────────────────────┤
│                  Infrastructure Layer                   │
│  Database │ MLflow │ Storage │ Logging                  │
└─────────────────────────────────────────────────────────┘
```

### 2.1 Design Principles

- **Domain-Driven Design** — business logic lives in `domain/` with pure entities, value objects, and policies. No framework leakage.
- **Hexagonal Architecture** — the core is isolated from infrastructure (HTTP, DB, MLflow) via contracts and protocols.
- **Contract-First Interfaces** — Pydantic models define all API inputs/outputs in `contracts/`.
- **Separation of Concerns** — feature engineering, model training, inference, and monitoring are independent modules.
- **Modular Architecture** — flat composition over deep inheritance hierarchies. Functions over classes where possible.
- **No Premature Abstractions** — concrete implementations first, abstractions emerge from patterns.
- **Configuration via Environment Variables** — all settings loaded from env vars using Pydantic Settings.
- **Structured Logging** — JSON-formatted logs for machine parsing and observability.
- **Reproducibility** — all experiments tracked via MLflow, dependencies pinned in `uv.lock`, Python version pinned in `.python-version`.

### 2.2 Key Design Decisions

| Decision | Rationale |
|---|---|
| Polars over Pandas | Columnar memory layout, 10-100x faster for the transformations we need on large student datasets |
| Survival analysis as baseline | Handles censored data (students still enrolled) — standard classifiers cannot |
| Isotonic + Platt calibration | Raw model outputs need calibration to be interpretable as probabilities |
| SHAP for explainability | Consistent, theoretically grounded feature attribution across all model types |
| FastAPI + Pydantic | Async-native, automatic OpenAPI spec, strict runtime validation |
| Pydantic Settings | Type-safe environment variable loading with validation |
| JSON structured logging | Machine-parseable logs for aggregation and alerting |

## 3. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Package Manager | uv |
| HTTP Framework | FastAPI |
| Data Validation | Pydantic v2 + pydantic-settings |
| Data Processing | Polars |
| Numerical | NumPy |
| Machine Learning | scikit-learn |
| Gradient Boosting | CatBoost, LightGBM |
| Forecasting | TimesFM (Google) |
| Experiment Tracking | MLflow |
| Containerization | Docker + Docker Compose |
| Linting | Ruff |
| Type Checking | mypy (strict) |
| Testing | pytest + pytest-cov |

## 4. Project Structure

```
leo-risk-engine/
├── pyproject.toml              # Project metadata & dependencies
├── uv.lock                     # Locked dependency versions
├── .python-version             # Pinned Python version (3.12)
├── .gitignore                  # Git ignore rules
├── Dockerfile                  # Container image definition
├── docker-compose.yml          # Local development stack
├── Makefile                    # Task automation
│
├── src/leo_risk/
│   │
│   ├── domain/                 # Core business logic (framework-agnostic)
│   │   ├── enums.py            # OutcomeStatus enum
│   │   ├── exit_reason.py      # ExitReason enum + frozensets
│   │   ├── censorship.py       # CensorshipType enum
│   │   ├── academic_calendar.py # AcademicCalendar enum
│   │   ├── label_contract.py   # LabelContract + LabelRule
│   │   ├── label_version.py    # LabelVersion value object
│   │   ├── entities/
│   │   │   ├── student_outcome.py # StudentOutcome entity
│   │   │   ├── prediction.py
│   │   │   ├── feature_snapshot.py
│   │   │   └── model_version.py
│   │   ├── value_objects/
│   │   │   ├── probability.py
│   │   │   ├── horizon.py
│   │   │   └── data_quality.py
│   │   └── policies/
│   │       ├── missing_data.py
│   │       └── recommendation_gate.py
│   │
│   ├── contracts/              # Pydantic request/response schemas
│   │   ├── student_context.py
│   │   ├── score_request.py
│   │   └── score_response.py
│   │
│   ├── features/               # Feature engineering
│   │   ├── academic/           # GPA, credits, course completion
│   │   ├── attendance/         # Attendance rates, trends
│   │   ├── financial/          # Tuition status, payment history
│   │   ├── engagement/         # LMS activity, participation
│   │   ├── institutional/      # Institution-level features
│   │   ├── interventions/      # Prior interventions, tutoring
│   │   ├── temporal/           # Time-based aggregations
│   │   ├── registry.py         # Feature registration & catalog
│   │   └── pipeline.py         # Feature computation pipeline
│   │
│   ├── labels/                 # Target variable construction
│   │   ├── dropout.py          # Dropout event definition
│   │   ├── censorship.py       # Censoring handling for survival
│   │   └── builder.py          # Label assembly logic
│   │
│   ├── models/                 # Model implementations
│   │   ├── protocol.py         # ModelProtocol (abstract interface)
│   │   ├── baseline/           # Logistic Survival baseline
│   │   ├── catboost/           # CatBoost gradient boosting
│   │   ├── lightgbm/           # LightGBM gradient boosting
│   │   └── survival/           # Cox PH, Random Survival Forests
│   │
│   ├── calibration/            # Probability calibration
│   │   ├── isotonic.py         # Isotonic regression calibrator
│   │   ├── platt.py            # Platt scaling (sigmoid)
│   │   └── evaluator.py        # Calibration curve analysis
│   │
│   ├── explainability/         # Model interpretation
│   │   ├── shap_explainer.py   # SHAP value computation
│   │   ├── drivers.py          # Top risk/protective factor extraction
│   │   └── protections.py      # Sensitive attribute safeguards
│   │
│   ├── forecasting/            # Time-series forecasting
│   │   ├── baselines/          # Statistical baselines
│   │   │   ├── last_value.py
│   │   │   ├── moving_average.py
│   │   │   ├── ewma.py
│   │   │   └── linear_trend.py
│   │   └── timesfm/            # Google TimesFM foundation model
│   │       ├── model.py
│   │       └── adapter.py
│   │
│   ├── training/               # Model training orchestration
│   │   ├── datasets/           # Dataset loaders & builders
│   │   ├── splits/             # Cross-validation & temporal splits
│   │   ├── pipelines/          # Training pipeline definitions
│   │   ├── evaluation/         # Metrics (C-index, Brier, AUC)
│   │   ├── tuning/             # Hyperparameter optimization
│   │   └── train.py            # CLI entry point
│   │
│   ├── inference/              # Online prediction
│   │   ├── predictor.py        # Score computation logic
│   │   ├── model_loader.py     # Model artifact loading
│   │   └── service.py          # Inference service orchestration
│   │
│   ├── monitoring/             # Production monitoring
│   │   ├── drift.py            # Data & concept drift detection
│   │   ├── calibration.py      # Live calibration tracking
│   │   └── performance.py      # Prediction accuracy monitoring
│   │
│   ├── infrastructure/         # External integrations
│   │   ├── database/           # Database adapters
│   │   ├── mlflow/             # MLflow experiment tracking
│   │   ├── storage/            # Artifact storage
│   │   └── logging/            # Structured logging + config
│   │       ├── config.py       # Pydantic Settings (env vars)
│   │       └── logger.py       # JSON structured logging setup
│   │
│   └── interface/              # API layer
│       └── http/
│           ├── app.py          # FastAPI application factory
│           ├── dependencies.py # Dependency injection
│           └── routes/
│               ├── health.py   # GET /health, GET /ready
│               ├── score.py    # POST /score
│               └── models.py   # GET /models
│
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── features/               # Feature engineering tests
│   ├── training/               # Training pipeline tests
│   └── regression/             # Regression / snapshot tests
│
├── docs/                       # Documentation
│   └── dropout-label-definition.md  # Formal dropout label definition
│
├── scripts/                    # Operational scripts
│   ├── build_dataset.py        # Dataset construction
│   ├── train.py                # Model training
│   ├── evaluate.py             # Model evaluation
│   └── backfill_features.py    # Historical feature backfill
│
├── notebooks/
│   ├── exploration/            # EDA notebooks
│   └── experiments/            # Model experiments
│
└── datasets/                   # Data files (gitignored)
```

## 5. Getting Started

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd leo-risk-engine

# Install dependencies
uv sync

# Install with dev tools
uv sync --extra dev
```

### Development

```bash
# Using Make (recommended)
make help            # Show all available commands
make install         # Install dependencies
make dev             # Install with dev dependencies
make test            # Run tests
make test-cov        # Run tests with coverage
make lint            # Run linter
make typecheck       # Run type checker
make format          # Format code

# Or using uv directly
uv run pytest
uv run ruff check src/ tests/
uv run mypy src/
uv run ruff format src/ tests/
```

### Environment Variables

All configuration is managed via environment variables with the `LEO_` prefix:

| Variable | Default | Description |
|---|---|---|
| `LEO_APP_NAME` | `leo-risk-engine` | Application name |
| `LEO_APP_VERSION` | `0.1.0` | Application version |
| `LEO_ENVIRONMENT` | `development` | Environment name |
| `LEO_DEBUG` | `false` | Enable debug mode |
| `LEO_LOG_LEVEL` | `INFO` | Logging level |
| `LEO_HOST` | `0.0.0.0` | Server host |
| `LEO_PORT` | `8000` | Server port |

Create a `.env` file for local development:

```bash
LEO_ENVIRONMENT=development
LEO_LOG_LEVEL=DEBUG
LEO_DEBUG=true
```

### API Server

```bash
# Start development server
make run

# Or directly
uv run uvicorn leo_risk.interface.http.app:app --reload

# The API is available at http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs (debug mode only)
```

### Docker

```bash
# Build and start services
make docker-build
make docker-up

# Or using docker compose directly
docker compose up --build
docker compose up -d

# Stop services
make docker-down
```

## 6. API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — returns `{"status": "ok"}` |
| `GET` | `/ready` | Readiness check — returns version, environment, uptime |
| `POST` | `/score` | Compute risk score for a student (planned) |
| `GET` | `/models` | List available model versions (planned) |

### Example Responses

**GET /health**
```json
{
  "status": "ok"
}
```

**GET /ready**
```json
{
  "status": "ready",
  "version": "0.1.0",
  "environment": "development",
  "uptime_seconds": 123.456
}
```

## 7. Model Pipeline

```
Raw Data ──► Feature Engineering ──► Label Construction ──► Training
                                                          │
                                                          ▼
                                        ┌──────────────────────────┐
                                        │  Baseline (Log-Survival) │
                                        │  CatBoost                │
                                        │  LightGBM                │
                                        │  Survival (Cox/RSF)      │
                                        └──────────┬───────────────┘
                                                   │
                                                   ▼
                                        Calibration (Isotonic/Platt)
                                                   │
                                                   ▼
                                        Explainability (SHAP)
                                                   │
                                                   ▼
                                        Score Response (probability,
                                        horizon, drivers, recommendations)
```

## 8. Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=leo_risk --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_health.py

# Run with verbose output
uv run pytest -v
```

## 9. Label Definition

The dropout label is formally defined in [`docs/dropout-label-definition.md`](docs/dropout-label-definition.md). Key points:

- **Dropout** = enrolled in T, not enrolled in T+1 after T+1 closes, no recognized exit path
- Four outcome statuses: `CONTINUED`, `DROPPED_OUT`, `PENDING`, `UNKNOWN`
- Nine exit reasons with configurable dropout classification
- Censorship types for survival analysis (`OBSERVED`, `RIGHT_CENSORED`, etc.)
- Supports semester, trimester, quarter, quadrimester, annual, and custom calendars

## 10. Development Roadmap

- [x] Project structure & tooling setup
- [x] Configuration (Pydantic Settings + env vars)
- [x] Structured logging (JSON)
- [x] FastAPI app factory with lifespan
- [x] Health check endpoints (`/health`, `/ready`)
- [x] Unit tests for health endpoints
- [x] Docker setup (Dockerfile + docker-compose)
- [x] Makefile with dev commands
- [x] README with development docs
- [x] Domain enums (`OutcomeStatus`, `ExitReason`, `CensorshipType`, `AcademicCalendar`)
- [x] `StudentOutcome` entity with validation rules
- [x] `LabelContract` with exit reason resolution
- [x] `LabelVersion` with semantic versioning
- [x] Dropout label definition document (`docs/dropout-label-definition.md`)
- [x] 62 unit tests for domain model
- [ ] Feature engineering pipeline
- [ ] Label builder (applies `LabelContract` to raw data)
- [ ] Baseline logistic survival model
- [ ] CatBoost / LightGBM models
- [ ] Survival analysis models
- [ ] Probability calibration
- [ ] SHAP explainability
- [ ] Score API endpoint
- [ ] Training pipeline automation
- [ ] Monitoring & drift detection
- [ ] CI/CD pipeline

## 10. License

Proprietary — Internal use only.
