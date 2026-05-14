# 📖 Data Dictionary — Wellness Data Integrity Engine

> The single source of truth for every table, column, and metric in this
> project. Maintained jointly by Engineering, Analytics, and Operations.

**Last updated:** 2026-Q2 · **Owner:** Data Analyst
**Lineage standard:** every column must list its `source` and `transform`.

---

## 🔵 Schema 1 — `clinical` (PostgreSQL · Redshift analogue)

Source dataset: **NHANES** (CDC, U.S. National Health and Nutrition Examination Survey).

### Table `clinical.demographics`

| Column | Type | Source | Description | Sensitivity |
|---|---|---|---|---|
| `seqn` | `BIGINT` | NHANES DEMO_J | Respondent sequence number — pseudonymized join key | internal |
| `gender` | `SMALLINT` | NHANES DEMO_J `RIAGENDR` | 1=Male, 2=Female | public |
| `age_years` | `SMALLINT` | NHANES DEMO_J `RIDAGEYR` | Age at screening. **Capped at 89** (HIPAA Safe Harbor). | sensitive |
| `race_ethnicity` | `SMALLINT` | NHANES DEMO_J `RIDRETH3` | 1=Mexican Am.; 2=Other Hispanic; 3=NH White; 4=NH Black; 6=NH Asian; 7=Other | public |
| `education_level` | `SMALLINT` | NHANES DEMO_J `DMDEDUC2` | 1=<9th; 2=9-11; 3=HS; 4=Some college; 5=College+ | public |
| `income_to_poverty` | `NUMERIC(5,2)` | NHANES DEMO_J `INDFMPIR` | Ratio of family income to poverty threshold | sensitive |
| `survey_cycle` | `VARCHAR(20)` | NHANES filename | Survey wave (e.g. "2017-2018") | public |
| `ingested_at` | `TIMESTAMPTZ` | pipeline | When the row entered our warehouse | internal |

### Table `clinical.cardiovascular`

| Column | Type | Description | Valid Range | Sensitivity |
|---|---|---|---|---|
| `seqn` | `BIGINT` | FK → demographics | — | internal |
| `exam_date` | `DATE` | Date of physical exam | — | internal |
| `systolic_bp` | `NUMERIC(5,1)` | Systolic blood pressure (mmHg) | 50 – 260 | sensitive |
| `diastolic_bp` | `NUMERIC(5,1)` | Diastolic blood pressure (mmHg) | 30 – 160 | sensitive |
| `pulse_rate_bpm` | `NUMERIC(5,1)` | Pulse rate, beats per minute | 30 – 220 | sensitive |
| `pulse_regular` | `BOOLEAN` | Whether pulse was regular | — | sensitive |

### Table `clinical.lab_results`

| Column | Type | Description | Valid Range | Sensitivity |
|---|---|---|---|---|
| `seqn` | `BIGINT` | FK → demographics | — | internal |
| `total_cholesterol` | `NUMERIC(6,2)` | mg/dL | 50 – 500 | sensitive |
| `hdl_cholesterol` | `NUMERIC(6,2)` | "Good" cholesterol, mg/dL | 10 – 150 | sensitive |
| `ldl_cholesterol` | `NUMERIC(6,2)` | "Bad" cholesterol, mg/dL | 10 – 400 | sensitive |
| `triglycerides` | `NUMERIC(6,2)` | mg/dL | 20 – 1000 | sensitive |
| `fasting_glucose` | `NUMERIC(6,2)` | mg/dL | 30 – 600 | sensitive |
| `hba1c` | `NUMERIC(4,2)` | % | 3.0 – 20.0 | sensitive |

### Table `clinical.body_measurements`

| Column | Type | Description | Valid Range |
|---|---|---|---|
| `seqn` | `BIGINT` | FK → demographics | — |
| `height_cm` | `NUMERIC(5,1)` | Height in centimeters | 50 – 230 |
| `weight_kg` | `NUMERIC(5,1)` | Weight in kilograms | 20 – 300 |
| `bmi` | `NUMERIC(4,1)` | Body Mass Index | 10 – 70 |
| `waist_cm` | `NUMERIC(5,1)` | Waist circumference | 30 – 200 |

### Table `clinical.data_quality_log`

The audit trail. Every failed quality check writes a row here.

| Column | Type | Description |
|---|---|---|
| `log_id` | `BIGSERIAL` | Auto-incrementing PK |
| `check_name` | `VARCHAR(100)` | Name of the failing check (e.g. `range::systolic_bp`) |
| `table_name` | `VARCHAR(100)` | Source table |
| `column_name` | `VARCHAR(100)` | Source column |
| `record_id` | `VARCHAR(100)` | The pseudonymized `seqn` or `user_id` |
| `severity` | `VARCHAR(20)` | `INFO` / `WARN` / `CRITICAL` |
| `description` | `TEXT` | Why it failed |
| `flagged_value` | `TEXT` | The actual offending value (stringified) |
| `detected_at` | `TIMESTAMPTZ` | When the pipeline caught it |

---

## 🟢 Database 2 — `wellness_telemetry` (MongoDB)

Source dataset: **Fitbit Fitness Tracker Data** (Kaggle, Möbius release).

### Collection `user_profiles`

```jsonc
{
  "_id":          ObjectId,
  "user_id":      "u_abc123",        // pseudonymized
  "age":          34,                // capped at 89
  "gender":       "F",
  "dietary_pref": "mediterranean",
  "created_at":   ISODate("2024-01-15T00:00:00Z")
}
```

### Collection `daily_activity`

```jsonc
{
  "user_id":         "u_abc123",
  "date":            ISODate("2024-03-12"),
  "steps":           8421,           // 0 – 100,000
  "distance_km":     6.4,
  "calories":        2150,
  "active_minutes":  42,
  "sedentary_min":   720
}
```

### Collection `sleep_records`

```jsonc
{
  "user_id":           "u_abc123",
  "sleep_start":       ISODate("2024-03-12T22:45:00Z"),
  "sleep_end":         ISODate("2024-03-13T06:30:00Z"),
  "total_minutes":     465,          // 0 – 1440
  "minutes_rem":       95,
  "minutes_deep":      78,
  "minutes_light":     240,
  "minutes_awake":     52,
  "efficiency_pct":    88.6
}
```

### Collection `heart_rate`

Minute-resolution sensor data.

```jsonc
{
  "user_id":    "u_abc123",
  "timestamp":  ISODate("2024-03-12T14:23:00Z"),
  "bpm":        72,                  // 30 – 220
  "context":    "resting"            // resting | active | sleep | unknown
}
```

### Collection `ingestion_audit`

Raw API webhook log. Used for root-cause investigations.

| Field | Description |
|---|---|
| `request_id` | UUID from the device-sync API |
| `device_type` | `fitbit` / `apple_health` / `garmin` |
| `received_at` | UTC timestamp |
| `payload_bytes` | Size of payload |
| `status` | `success` / `retry` / `failed` |
| `error_code` | If `failed` |

---

## 📊 Derived Metrics (BI Layer)

These are computed on top of the raw tables and exposed to dashboards.

| Metric | Formula | Owner |
|---|---|---|
| **Completeness Rate** | `1 - (NULL rows / total rows)` per column | Engineering |
| **Uniqueness Score** | `1 - (duplicate rows / total rows)` per key | Engineering |
| **Data Quality Score (DQS)** | Weighted mean: 0.4 × completeness + 0.3 × uniqueness + 0.3 × validity | Engineering |
| **Wellness Index** | `0.4·sleep_score + 0.3·activity_score + 0.3·resting_hr_score`, normalized 0–100 | Product |
| **Cardio Risk Tier** | Rule-based: 5 tiers by systolic BP + LDL | Operations / Clinical |
| **DAU / WAU / MAU** | Distinct `user_id` in `daily_activity` over 1/7/30 days | Product |

---

## 🔗 Data Lineage

```
NHANES CSV release  ──▶  data/raw/         ──▶  PostgreSQL `clinical.*`
Kaggle Fitbit JSON  ──▶  data/raw/         ──▶  MongoDB `wellness_telemetry.*`
                                              │
                                              ▼
                                     src/governance/anonymizer.py
                                              │
                                              ▼
                                     src/quality_engine/
                                       ├── logic_rules.py
                                       └── stats_models.py
                                              │
                                              ▼
                                     data/processed/*.parquet
                                              │
                                              ▼
                                     Tableau / Power BI / Plotly
```

---

## 🚨 Versioning

This dictionary follows **semver**. Breaking column renames bump the major
version. The current schema version is `v1.0.0`.
