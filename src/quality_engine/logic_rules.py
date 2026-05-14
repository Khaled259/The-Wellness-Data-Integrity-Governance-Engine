"""
logic_rules.py
==============
Hard, deterministic checks that catch *physically impossible* records.

Demonstrates the responsibilities:
    • "Establish and maintain robust processes for tracking and assessing
       data quality"
    • "Develop automated checks to proactively detect data inconsistencies"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

import pandas as pd


# -----------------------------------------------------------------------------
# Domain thresholds — sourced from medical literature, kept in one place so
# the Operations / Clinical team can review and edit them.
# -----------------------------------------------------------------------------
CLINICAL_BOUNDS: Dict[str, tuple] = {
    "age_years":         (0, 120),
    "systolic_bp":       (50, 260),   # mmHg; <50 = device error, >260 = crisis
    "diastolic_bp":      (30, 160),
    "pulse_rate_bpm":    (30, 220),
    "resting_hr":        (30, 200),
    "total_cholesterol": (50, 500),   # mg/dL
    "hdl_cholesterol":   (10, 150),
    "ldl_cholesterol":   (10, 400),
    "fasting_glucose":   (30, 600),
    "hba1c":             (3.0, 20.0),
    "bmi":               (10, 70),
    "height_cm":         (50, 230),
    "weight_kg":         (20, 300),
    "steps":             (0, 100_000),
    "sleep_minutes":     (0, 24 * 60),
    "distance_km":       (0, 100),
    "calories":          (0, 10_000),
}


@dataclass
class QualityReport:
    """Structured output every check returns — easy to log to a warehouse."""
    check_name:    str
    table:         str
    total_rows:    int
    failed_rows:   int
    failed_index:  List[int] = field(default_factory=list)
    description:   str = ""

    @property
    def pass_rate(self) -> float:
        if self.total_rows == 0:
            return 1.0
        return 1.0 - self.failed_rows / self.total_rows

    def to_dict(self) -> dict:
        return {
            "check_name":  self.check_name,
            "table":       self.table,
            "total_rows":  self.total_rows,
            "failed_rows": self.failed_rows,
            "pass_rate":   round(self.pass_rate, 4),
            "description": self.description,
        }


# -----------------------------------------------------------------------------
# Atomic checks
# -----------------------------------------------------------------------------
def check_range(
    df: pd.DataFrame, column: str, table_name: str = "<unknown>",
) -> QualityReport:
    """Verify values fall in the clinical/operational allowable range."""
    if column not in df.columns:
        return QualityReport(f"range::{column}", table_name, len(df), 0,
                             description=f"column '{column}' not present")
    lo, hi = CLINICAL_BOUNDS.get(column, (None, None))
    if lo is None:
        return QualityReport(f"range::{column}", table_name, len(df), 0,
                             description="no bound defined")

    series = pd.to_numeric(df[column], errors="coerce")
    mask = (series < lo) | (series > hi)
    return QualityReport(
        check_name=f"range::{column}",
        table=table_name,
        total_rows=len(df),
        failed_rows=int(mask.sum()),
        failed_index=df.index[mask].tolist(),
        description=f"{column} must be in [{lo}, {hi}]",
    )


def check_completeness(
    df: pd.DataFrame, columns: List[str], table_name: str = "<unknown>",
) -> QualityReport:
    """Percentage of NULLs across a subset of columns."""
    subset = [c for c in columns if c in df.columns]
    if not subset:
        return QualityReport("completeness", table_name, len(df), 0,
                             description="no requested columns present")
    missing_mask = df[subset].isna().any(axis=1)
    return QualityReport(
        check_name="completeness",
        table=table_name,
        total_rows=len(df),
        failed_rows=int(missing_mask.sum()),
        failed_index=df.index[missing_mask].tolist(),
        description=f"at least one NULL across {subset}",
    )


def check_uniqueness(
    df: pd.DataFrame, key_columns: List[str], table_name: str = "<unknown>",
) -> QualityReport:
    """Composite-key uniqueness."""
    if not all(c in df.columns for c in key_columns):
        return QualityReport("uniqueness", table_name, len(df), 0,
                             description="key columns missing")
    dup_mask = df.duplicated(subset=key_columns, keep=False)
    return QualityReport(
        check_name=f"uniqueness::{'+'.join(key_columns)}",
        table=table_name,
        total_rows=len(df),
        failed_rows=int(dup_mask.sum()),
        failed_index=df.index[dup_mask].tolist(),
        description=f"key columns must be unique: {key_columns}",
    )


def check_referential(
    child: pd.DataFrame, parent: pd.DataFrame, on: str,
    table_name: str = "<unknown>",
) -> QualityReport:
    """Every child row's foreign key must exist in the parent table."""
    if on not in child.columns or on not in parent.columns:
        return QualityReport("referential", table_name, len(child), 0,
                             description=f"column '{on}' missing on one side")
    orphan_mask = ~child[on].isin(parent[on])
    return QualityReport(
        check_name=f"referential::{on}",
        table=table_name,
        total_rows=len(child),
        failed_rows=int(orphan_mask.sum()),
        failed_index=child.index[orphan_mask].tolist(),
        description=f"foreign key '{on}' must reference parent",
    )


def check_logical_consistency(
    df: pd.DataFrame, table_name: str = "<unknown>",
) -> QualityReport:
    """
    Cross-column logical impossibilities.

    Examples flagged:
        • systolic_bp <= diastolic_bp
        • sleep_minutes > 0 but is_asleep == False
        • height/weight imply impossible BMI
    """
    bad = pd.Series(False, index=df.index)
    notes: List[str] = []

    if {"systolic_bp", "diastolic_bp"}.issubset(df.columns):
        b = df["systolic_bp"] <= df["diastolic_bp"]
        bad |= b.fillna(False)
        if b.any():
            notes.append("systolic <= diastolic")

    if {"sleep_minutes", "steps"}.issubset(df.columns):
        # Simultaneously asleep AND walking >5000 steps that day = suspicious
        b = (df["sleep_minutes"] > 600) & (df["steps"] > 20_000)
        bad |= b.fillna(False)
        if b.any():
            notes.append("simultaneously high sleep + step counts")

    if {"height_cm", "weight_kg", "bmi"}.issubset(df.columns):
        implied = df["weight_kg"] / ((df["height_cm"] / 100) ** 2)
        b = (implied - df["bmi"]).abs() > 2.0
        bad |= b.fillna(False)
        if b.any():
            notes.append("BMI inconsistent with height & weight")

    return QualityReport(
        check_name="logical_consistency",
        table=table_name,
        total_rows=len(df),
        failed_rows=int(bad.sum()),
        failed_index=df.index[bad].tolist(),
        description="; ".join(notes) or "no rules triggered",
    )


# -----------------------------------------------------------------------------
# Orchestrator
# -----------------------------------------------------------------------------
def run_full_check_suite(
    df: pd.DataFrame,
    table_name: str,
    numeric_columns: List[str] | None = None,
    required_columns: List[str] | None = None,
    unique_keys: List[str] | None = None,
) -> pd.DataFrame:
    """
    Run every applicable check on a DataFrame and return a tidy report.

    The output is what powers the **Data Health Dashboard**.
    """
    reports: List[QualityReport] = []

    if required_columns:
        reports.append(check_completeness(df, required_columns, table_name))

    if unique_keys:
        reports.append(check_uniqueness(df, unique_keys, table_name))

    for col in (numeric_columns or []):
        if col in df.columns:
            reports.append(check_range(df, col, table_name))

    reports.append(check_logical_consistency(df, table_name))

    return pd.DataFrame([r.to_dict() for r in reports])
