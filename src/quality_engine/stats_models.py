"""
stats_models.py
===============
Statistical anomaly detection and imputation.

Demonstrates the responsibility:
    "Apply statistical techniques to enhance data quality"

Techniques implemented
----------------------
    • Z-score outlier detection (parametric)
    • Interquartile-Range outlier detection (non-parametric, robust)
    • Modified Z-score (MAD-based, robust to extreme outliers)
    • Mean / median imputation
    • K-Nearest-Neighbors imputation for multivariate time-series gaps
    • Group-wise standardization (e.g. blood pressure by age bracket)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

import numpy as np
import pandas as pd
from scipy import stats

try:
    from sklearn.impute import KNNImputer, SimpleImputer
    _SKLEARN_OK = True
except ImportError:                                          # pragma: no cover
    _SKLEARN_OK = False


# =============================================================================
# Outlier detection
# =============================================================================
@dataclass
class OutlierResult:
    method:        str
    column:        str
    threshold:     float
    n_outliers:    int
    outlier_idx:   list
    lower_bound:   Optional[float] = None
    upper_bound:   Optional[float] = None

    def __repr__(self) -> str:                              # pragma: no cover
        return (f"<OutlierResult {self.method}::{self.column} "
                f"flagged={self.n_outliers} "
                f"in [{self.lower_bound:.2f}, {self.upper_bound:.2f}]>")


def detect_outliers_zscore(
    series: pd.Series, threshold: float = 3.0,
) -> OutlierResult:
    """Classic parametric Z-score. Assumes (roughly) normal data."""
    s = pd.to_numeric(series, errors="coerce")
    z = np.abs(stats.zscore(s, nan_policy="omit"))
    mask = pd.Series(False, index=s.index)
    mask.loc[s.dropna().index] = z > threshold
    mu, sd = s.mean(), s.std()
    return OutlierResult(
        method="zscore",
        column=str(series.name),
        threshold=threshold,
        n_outliers=int(mask.sum()),
        outlier_idx=series.index[mask].tolist(),
        lower_bound=float(mu - threshold * sd),
        upper_bound=float(mu + threshold * sd),
    )


def detect_outliers_iqr(
    series: pd.Series, k: float = 1.5,
) -> OutlierResult:
    """Tukey's fences — robust to skew."""
    s = pd.to_numeric(series, errors="coerce")
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    mask = (s < lo) | (s > hi)
    return OutlierResult(
        method="iqr",
        column=str(series.name),
        threshold=k,
        n_outliers=int(mask.sum()),
        outlier_idx=series.index[mask].tolist(),
        lower_bound=float(lo),
        upper_bound=float(hi),
    )


def detect_outliers_modified_zscore(
    series: pd.Series, threshold: float = 3.5,
) -> OutlierResult:
    """
    Iglewicz–Hoaglin modified Z-score based on the Median Absolute Deviation.
    Recommended for small samples or heavy-tailed distributions.
    """
    s = pd.to_numeric(series, errors="coerce")
    med = s.median()
    mad = (s - med).abs().median()
    if mad == 0:
        mod_z = pd.Series(0, index=s.index)
    else:
        mod_z = 0.6745 * (s - med) / mad
    mask = mod_z.abs() > threshold
    return OutlierResult(
        method="modified_zscore",
        column=str(series.name),
        threshold=threshold,
        n_outliers=int(mask.sum()),
        outlier_idx=series.index[mask].tolist(),
        lower_bound=float(med - threshold * mad / 0.6745),
        upper_bound=float(med + threshold * mad / 0.6745),
    )


# =============================================================================
# Group-wise Z-scores (NHANES-style)
# =============================================================================
def zscore_by_group(
    df: pd.DataFrame, value_col: str, group_col: str,
) -> pd.Series:
    """
    Compute Z-scores *within each group* — e.g. systolic BP normalized by
    age bracket. This is exactly what the project blueprint asks for.
    """
    def _z(s: pd.Series) -> pd.Series:
        sd = s.std(ddof=0)
        return (s - s.mean()) / sd if sd else s * 0

    return df.groupby(group_col)[value_col].transform(_z)


def flag_group_outliers(
    df: pd.DataFrame, value_col: str, group_col: str, threshold: float = 3.0,
) -> pd.DataFrame:
    """Return only the rows that are outliers within their own group."""
    z = zscore_by_group(df, value_col, group_col)
    return df.loc[z.abs() > threshold].assign(group_zscore=z)


# =============================================================================
# Imputation
# =============================================================================
def impute_simple(
    df: pd.DataFrame, columns: List[str],
    strategy: Literal["mean", "median", "most_frequent"] = "median",
) -> pd.DataFrame:
    """Univariate mean/median/mode imputation."""
    out = df.copy()
    if _SKLEARN_OK:
        imp = SimpleImputer(strategy=strategy)
        out[columns] = imp.fit_transform(out[columns])
    else:                                                  # graceful fallback
        for c in columns:
            if strategy == "mean":
                out[c] = out[c].fillna(out[c].mean())
            elif strategy == "median":
                out[c] = out[c].fillna(out[c].median())
            else:
                out[c] = out[c].fillna(out[c].mode().iloc[0])
    return out


def impute_knn(
    df: pd.DataFrame, columns: List[str], n_neighbors: int = 5,
) -> pd.DataFrame:
    """
    Multivariate KNN imputation — recommended for correlated wearable
    time-series (e.g. when sleep_minutes is missing but steps + HR exist).
    """
    if not _SKLEARN_OK:
        raise RuntimeError("scikit-learn is required for impute_knn()")
    out = df.copy()
    imp = KNNImputer(n_neighbors=n_neighbors, weights="distance")
    out[columns] = imp.fit_transform(out[columns])
    return out


# =============================================================================
# Convenience: full statistical sweep
# =============================================================================
def run_statistical_audit(
    df: pd.DataFrame,
    numeric_columns: List[str],
    z_threshold: float = 3.0,
    iqr_k: float = 1.5,
) -> pd.DataFrame:
    """
    Run all three outlier detectors against every numeric column and
    return a tidy summary table — ready to push to the Data Health Dashboard.
    """
    rows = []
    for col in numeric_columns:
        if col not in df.columns:
            continue
        s = df[col]
        for fn, name in [
            (lambda x: detect_outliers_zscore(x, z_threshold),         "zscore"),
            (lambda x: detect_outliers_iqr(x, iqr_k),                  "iqr"),
            (lambda x: detect_outliers_modified_zscore(x),  "modified_zscore"),
        ]:
            r = fn(s)
            rows.append({
                "column":       col,
                "method":       name,
                "n_outliers":   r.n_outliers,
                "lower_bound":  round(r.lower_bound, 2),
                "upper_bound":  round(r.upper_bound, 2),
                "outlier_pct":  round(100 * r.n_outliers / max(len(s), 1), 2),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":                                  # pragma: no cover
    rng = np.random.default_rng(42)
    demo = pd.DataFrame({
        "systolic_bp":  np.concatenate([rng.normal(120, 12, 990),
                                        [240, 250, 30, 35, 999,
                                         260, 28, 220, 290, 10]]),
        "age_bracket":  np.repeat(["18-30", "31-50", "51-70", "70+"], 250),
    })
    print(run_statistical_audit(demo, ["systolic_bp"]))
    print("\nGroup outliers:")
    print(flag_group_outliers(demo, "systolic_bp", "age_bracket").head())
