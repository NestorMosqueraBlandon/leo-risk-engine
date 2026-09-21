# Leo Risk Engine

> Student dropout risk prediction engine using survival analysis and machine learning.

## 1. Overview

Leo Risk Engine is a service that ingests student academic, financial, attendance, and engagement data to produce calibrated risk scores and survival curves. It predicts the probability of a student dropping out within configurable time horizons, explains the key drivers behind each prediction, and surfaces actionable recommendations.

The system is designed for educational institutions that need early-warning capabilities to intervene before students disengage or drop out.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Layer (FastAPI)                  │
│  /score  /models  /health                               │
├─────────────────────────────────────────────────────────┤
│                   Inference Pipeline                     │
│  Predictor ──► Model Loader ──► Calibration ──► Explain  │
├─────────────────────────────────────────────────────────┤
│                   Training Pipeline                     │
│  Datasets ──► Splits ──► Pipelines ──► Evaluation       │
├─────────────────────────────────────────────────────────┤
│                  Feature Engineering                     │
│  Academic │ Attendance │ Financial │ Engagement │ ...    │
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
- **Reproducibility** — all experiments are tracked via MLflow, dependencies pinned in `uv.lock`, Python version pinned in `.python-version`.

### 2.2 Key Design Decisions

| Decision | Rationale |
|---|---|
| Polars over Pandas | Columnar memory layout, 10-100x faster for the transformations we need on large student datasets |
| Survival analysis as baseline | Handles censored data (students still enrolled) — standard classifiers cannot |
| Isotonic + Platt calibration | Raw model outputs need calibration to be interpretable as probabilities |
| SHAP for explainability | Consistent, theoretically grounded feature attribution across all model types |
| FastAPI + Pydantic | Async-native, automatic OpenAPI spec, strict runtime validation |

## 3. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Package Manager | uv |
| HTTP Framework | FastAPI |
| Data Validation | Pydantic v2 |
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
├── Dockerfile                  # Container image definition
├── docker-compose.yml          # Local development stack
├── Makefile                    # Task automation
│
├── src/leo_risk/
│   │
│   ├── domain/                 # Core business logic (framework-agnostic)
│   │   ├── entities/           # Prediction, FeatureSnapshot, StudentOutcome, ModelVersion
│   │   ├── value_objects/      # Probability, Horizon, DataQuality
│   │   └── policies/          # MissingData, RecommendationGate
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
│   │   └── logging/            # Structured logging
│   │
│   └── interface/              # API layer
│       └── http/
│           ├── app.py          # FastAPI application factory
│           ├── dependencies.py # Dependency injection
│           └── routes/
│               ├── score.py    # POST /score
│               ├── models.py   # GET /models
│               └── health.py   # GET /health
│
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── features/               # Feature engineering tests
│   ├── training/               # Training pipeline tests
│   └── regression/             # Regression / snapshot tests
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
# Run linting
uv run ruff check src/ tests/

# Run type checking
uv run mypy src/

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=leo_risk --cov-report=term-missing

# Format code
uv run ruff format src/ tests/
```

### API Server

```bash
# Start development server
uv run uvicorn leo_risk.interface.http.app:app --reload

# The API is available at http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
```

### Docker

```bash
# Build and start services
docker compose up --build

# Run in detached mode
docker compose up -d
```

## 6. API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/score` | Compute risk score for a student |
| `GET` | `/models` | List available model versions |
| `GET` | `/health` | Service health check |

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

## 8. Development Roadmap

- [x] Project structure & tooling setup
- [ ] Domain entities and value objects
- [ ] Feature engineering pipeline
- [ ] Label construction (dropout + censoring)
- [ ] Baseline logistic survival model
- [ ] CatBoost / LightGBM models
- [ ] Survival analysis models
- [ ] Probability calibration
- [ ] SHAP explainability
- [ ] HTTP API implementation
- [ ] Training pipeline automation
- [ ] Monitoring & drift detection
- [ ] Docker deployment
- [ ] CI/CD pipeline

## 9. License

Proprietary — Internal use only.
# leo-risk-engine
