# 🩺 Wellness Data Integrity & Governance Engine

> An end-to-end data quality and governance pipeline that extracts raw user
> health telemetry and clinical profile data, sanitizes it using statistical
> methods, and serves it through high-fidelity dashboards to guide product
> development for a longevity & wellness platform.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]([https://colab.research.google.com/](https://colab.research.google.com/drive/1RVXNBgzPTRpj0y5sx9O9uZlNRLx1cSkY?usp=sharing))

---

## 📌 Project Overview

This project simulates the data infrastructure of a longevity & wellness
platform (think Whoop, Oura, Fitbit Premium). It demonstrates the full
responsibility stack of a modern **Data Analyst / Data Quality Engineer**:

| Responsibility | Where it lives |
|---|---|
| Implement a data governance framework | `src/governance/` + `docs/governance_policy.md` |
| Track and assess data quality | `src/quality_engine/logic_rules.py` |
| Automated checks for inconsistencies | `src/quality_engine/logic_rules.py` |
| Statistical techniques (Z-score, IQR, KNN imputation) | `src/quality_engine/stats_models.py` |
| Customized reports & dashboards | `notebooks/03_dashboards.ipynb` + `docs/dashboards/` |
| Extract from databases (Redshift/MongoDB analogues) | `src/extraction/` |
| Identify & resolve root causes | `notebooks/02_anomaly_investigation.ipynb` |
| Cross-functional collaboration | `docs/` (audience-specific writeups) |
| Maintain documentation | `docs/data_dictionary.md` |

---

## 🏗️ System Architecture

```
┌──────────────────────┐      ┌──────────────────────┐
│  PostgreSQL          │      │  MongoDB             │
│  (Redshift analogue) │      │  (NoSQL document)    │
│  NHANES clinical &   │      │  Fitbit-style daily  │
│  demographic data    │      │  wearable telemetry  │
└──────────┬───────────┘      └──────────┬───────────┘
           │                             │
           │   psycopg2 / SQLAlchemy     │   pymongo
           ▼                             ▼
       ┌────────────────────────────────────┐
       │  EXTRACTION LAYER  (src/extraction)│
       └─────────────────┬──────────────────┘
                         ▼
       ┌────────────────────────────────────┐
       │  GOVERNANCE LAYER  (src/governance)│
       │  • PII masking  • Standardization  │
       │  • Role-based access stub          │
       └─────────────────┬──────────────────┘
                         ▼
       ┌────────────────────────────────────┐
       │  QUALITY ENGINE  (src/quality_engine)│
       │  • Logic rules  (negative HR, etc.) │
       │  • Z-score / IQR outlier detection  │
       │  • Completeness / uniqueness KPIs   │
       │  • Statistical imputation (KNN)     │
       └─────────────────┬──────────────────┘
                         ▼
       ┌────────────────────────────────────┐
       │  ANALYTICS / DASHBOARDS            │
       │  Plotly  →  Tableau / Power BI     │
       └────────────────────────────────────┘
```

---

## 📂 Repository Structure

```
wellness-data-integrity-engine/
│
├── .github/workflows/         # CI: linting + tests on every push
├── data/
│   ├── raw/                   # Downloaded NHANES/Fitbit datasets (gitignored)
│   └── processed/             # Cleaned outputs for BI tools
│
├── infrastructure/            # Database simulation setup
│   ├── docker-compose.yml     # PostgreSQL + MongoDB local stack
│   ├── init.sql               # PostgreSQL DDL for NHANES tables
│   └── init-mongo.js          # MongoDB collection initialization
│
├── src/
│   ├── extraction/            # Phase 1: Database connectors
│   │   ├── postgres_client.py
│   │   └── mongo_client.py
│   ├── governance/            # Phase 2: PII masking, RBAC stubs
│   │   └── anonymizer.py
│   └── quality_engine/        # Phase 3: Quality + statistical checks
│       ├── logic_rules.py
│       └── stats_models.py
│
├── notebooks/                 # The end-to-end Colab story
│   └── wellness_data_integrity_engine.ipynb   ← run this in Colab
│
├── docs/
│   ├── data_dictionary.md     # Every table, column, definition
│   ├── governance_policy.md   # PII / RBAC / lineage rules
│   └── dashboards/            # Exported BI screenshots
│
├── tests/
│   └── test_quality_checks.py # pytest suite
│
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### Option A: Google Colab (zero setup)

Open `notebooks/wellness_data_integrity_engine.ipynb` in Colab and click
**Runtime → Run all**. The notebook is fully self-contained: it generates
realistic mock data, spins up an in-process SQLite database (Redshift
analogue) and TinyDB document store (MongoDB analogue), and runs every phase
of the pipeline end-to-end.

### Option B: Local with Docker (enterprise-style)

```bash
# 1. Spin up PostgreSQL + MongoDB
cd infrastructure
docker compose up -d

# 2. Install Python dependencies
cd ..
pip install -r requirements.txt

# 3. Run the quality pipeline
python -m src.quality_engine.stats_models

# 4. Run the test suite
pytest tests/
```

---

## 📊 Datasets

| Dataset | Source | Used to simulate |
|---|---|---|
| NHANES (cardio + demographics) | CDC public release | Redshift / clinical warehouse |
| Fitbit Fitness Tracker Data | Kaggle (Möbius dataset) | MongoDB / wearable telemetry |

The Colab notebook generates **statistically faithful mock data** that
mirrors the schema of both datasets, so the project is fully reproducible
without API keys or downloads. Swap in the real CSVs by dropping them into
`data/raw/` — the extraction layer auto-detects them.

---

## 🧪 What This Project Demonstrates

- **SQL + NoSQL fluency** — psycopg2 against Postgres, pymongo against Mongo
- **Statistical rigor** — Z-scores, IQR, KNN imputation, completeness KPIs
- **Production hygiene** — Docker, modular Python, unit tests, CI
- **Cross-functional communication** — separate writeups for Engineering,
  Product, and Operations audiences in `docs/`
- **Data storytelling** — interactive Plotly dashboards + a Data Health
  dashboard built for the engineers, not just the executives

---

## 📜 License

MIT — see `LICENSE` for details.
