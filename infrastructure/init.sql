-- =============================================================================
-- PostgreSQL DDL: simulates an Amazon Redshift clinical warehouse
-- =============================================================================
-- Schema mirrors the NHANES (National Health and Nutrition Examination Survey)
-- public data release from the U.S. CDC. Tables are intentionally split the
-- same way NHANES splits its files so analysts can practice realistic joins.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS clinical;
SET search_path TO clinical, public;

-- -----------------------------------------------------------------------------
-- 1. Demographics  (NHANES DEMO_*)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS demographics (
    seqn               BIGINT PRIMARY KEY,            -- Respondent sequence #
    gender             SMALLINT,                      -- 1=M, 2=F
    age_years          SMALLINT,
    race_ethnicity     SMALLINT,
    education_level    SMALLINT,
    marital_status     SMALLINT,
    income_to_poverty  NUMERIC(5,2),
    survey_cycle       VARCHAR(20),
    ingested_at        TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 2. Cardiovascular examinations (NHANES BPX_*)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cardiovascular (
    seqn               BIGINT REFERENCES demographics(seqn),
    exam_date          DATE,
    systolic_bp        NUMERIC(5,1),
    diastolic_bp       NUMERIC(5,1),
    pulse_rate_bpm     NUMERIC(5,1),
    pulse_regular      BOOLEAN,
    examiner_id        VARCHAR(20),
    ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (seqn, exam_date)
);

-- -----------------------------------------------------------------------------
-- 3. Lab results (NHANES TCHOL_*, GLU_*)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lab_results (
    seqn               BIGINT REFERENCES demographics(seqn),
    sample_date        DATE,
    total_cholesterol  NUMERIC(6,2),                  -- mg/dL
    hdl_cholesterol    NUMERIC(6,2),
    ldl_cholesterol    NUMERIC(6,2),
    triglycerides      NUMERIC(6,2),
    fasting_glucose    NUMERIC(6,2),
    hba1c              NUMERIC(4,2),                  -- %
    ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (seqn, sample_date)
);

-- -----------------------------------------------------------------------------
-- 4. Body measurements (NHANES BMX_*)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS body_measurements (
    seqn               BIGINT REFERENCES demographics(seqn),
    measure_date       DATE,
    height_cm          NUMERIC(5,1),
    weight_kg          NUMERIC(5,1),
    bmi                NUMERIC(4,1),
    waist_cm           NUMERIC(5,1),
    ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (seqn, measure_date)
);

-- -----------------------------------------------------------------------------
-- 5. Data Quality Log — every failed check writes a row here
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_quality_log (
    log_id             BIGSERIAL PRIMARY KEY,
    check_name         VARCHAR(100) NOT NULL,
    table_name         VARCHAR(100) NOT NULL,
    column_name        VARCHAR(100),
    record_id          VARCHAR(100),
    severity           VARCHAR(20),                   -- INFO/WARN/CRITICAL
    description        TEXT,
    flagged_value      TEXT,
    detected_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dq_log_severity ON data_quality_log(severity);
CREATE INDEX IF NOT EXISTS idx_dq_log_detected ON data_quality_log(detected_at);

-- -----------------------------------------------------------------------------
-- Role-Based Access Control — governance stub
-- -----------------------------------------------------------------------------
-- analyst_role:   SELECT-only on masked views
-- engineer_role:  SELECT on raw + dq_log
-- admin_role:     full
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='analyst_role') THEN
        CREATE ROLE analyst_role;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='engineer_role') THEN
        CREATE ROLE engineer_role;
    END IF;
END$$;

GRANT USAGE ON SCHEMA clinical TO analyst_role, engineer_role;
GRANT SELECT ON ALL TABLES IN SCHEMA clinical TO engineer_role;
