"""
postgres_client.py
==================
Extraction layer for the clinical warehouse (Postgres / Redshift analogue).

Demonstrates the responsibility:
    "Extract data from databases (e.g., Redshift)"

Usage
-----
    from src.extraction.postgres_client import PostgresClient

    pg = PostgresClient.from_env()           # reads PG_* env vars
    df = pg.fetch_cardiovascular(year=2017)
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional

import pandas as pd

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:                          # pragma: no cover
    psycopg2 = None                          # allows import in Colab w/o lib

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class PostgresClient:
    """Thin, well-instrumented wrapper around psycopg2 + SQLAlchemy."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
    ) -> None:
        self._dsn = dict(
            host=host, port=port, dbname=database, user=user, password=password
        )
        self._engine: Optional[Engine] = None

    # ------------------------------------------------------------------ #
    # Constructors
    # ------------------------------------------------------------------ #
    @classmethod
    def from_env(cls) -> "PostgresClient":
        """Build a client from `PG_*` environment variables (12-factor style)."""
        return cls(
            host=os.getenv("PG_HOST", "localhost"),
            port=int(os.getenv("PG_PORT", "5432")),
            database=os.getenv("PG_DATABASE", "wellness_clinical"),
            user=os.getenv("PG_USER", "wellness_admin"),
            password=os.getenv("PG_PASSWORD", "change_me_in_prod"),
        )

    # ------------------------------------------------------------------ #
    # Connection plumbing
    # ------------------------------------------------------------------ #
    @property
    def engine(self) -> Engine:
        if self._engine is None:
            url = (
                f"postgresql+psycopg2://{self._dsn['user']}:{self._dsn['password']}"
                f"@{self._dsn['host']}:{self._dsn['port']}/{self._dsn['dbname']}"
            )
            self._engine = create_engine(url, pool_pre_ping=True)
        return self._engine

    @contextmanager
    def cursor(self) -> Iterator:
        """Raw cursor for power users — supports parameterized SQL."""
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is not installed in this environment.")
        conn = psycopg2.connect(**self._dsn)
        try:
            yield conn.cursor(cursor_factory=RealDictCursor)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Domain queries — what a real analyst would write
    # ------------------------------------------------------------------ #
    def fetch_demographics(self) -> pd.DataFrame:
        sql = """
            SELECT seqn, gender, age_years, race_ethnicity,
                   education_level, income_to_poverty, survey_cycle
              FROM clinical.demographics
        """
        logger.info("Fetching demographics from clinical warehouse")
        return pd.read_sql(sql, self.engine)

    def fetch_cardiovascular(self, min_age: int = 18) -> pd.DataFrame:
        """Join cardio with demographics — the canonical analyst query."""
        sql = """
            SELECT  c.seqn,
                    c.exam_date,
                    c.systolic_bp,
                    c.diastolic_bp,
                    c.pulse_rate_bpm,
                    d.age_years,
                    d.gender
              FROM  clinical.cardiovascular c
              JOIN  clinical.demographics  d USING (seqn)
             WHERE  d.age_years >= %(min_age)s
        """
        logger.info("Fetching cardio data for age >= %s", min_age)
        return pd.read_sql(sql, self.engine, params={"min_age": min_age})

    def fetch_lab_panel(self) -> pd.DataFrame:
        sql = "SELECT * FROM clinical.lab_results"
        return pd.read_sql(sql, self.engine)

    # ------------------------------------------------------------------ #
    # Quality logging
    # ------------------------------------------------------------------ #
    def log_quality_issue(
        self,
        check_name: str,
        table_name: str,
        column_name: str,
        record_id: str,
        severity: str,
        description: str,
        flagged_value: str,
    ) -> None:
        """Persist a failed data-quality check to the audit table."""
        sql = """
            INSERT INTO clinical.data_quality_log
                (check_name, table_name, column_name, record_id,
                 severity, description, flagged_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with self.cursor() as cur:
            cur.execute(sql, (
                check_name, table_name, column_name, record_id,
                severity, description, flagged_value,
            ))


if __name__ == "__main__":           # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    client = PostgresClient.from_env()
    print(client.fetch_demographics().head())
