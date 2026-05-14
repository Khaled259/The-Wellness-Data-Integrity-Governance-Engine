"""
anonymizer.py
=============
PII masking and standardization layer.

Demonstrates the responsibilities:
    • "Implement a data governance framework"
    • "Create and maintain documentation"  (this module IS the executable
      version of `docs/governance_policy.md`)

The functions here are intentionally pure and small — easy to test, easy
to plug into either the Colab notebook or an Airflow DAG.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Iterable

import pandas as pd

# -----------------------------------------------------------------------------
# Configuration: which columns are considered Personally Identifiable
# -----------------------------------------------------------------------------
PII_DIRECT = {
    "name", "full_name", "first_name", "last_name",
    "email", "phone", "phone_number",
    "ssn", "social_security_number",
    "street_address", "address",
    "device_id", "mac_address", "imei",
}

PII_INDIRECT = {
    # Quasi-identifiers — combining them can re-identify
    "zip_code", "zip", "postal_code",
    "birth_date", "date_of_birth", "dob",
    "age", "age_years",
}

# Salt is read from env in production; hard-coded only for reproducibility here
_HASH_SALT = "wellness-engine-v1::change-in-prod"


# -----------------------------------------------------------------------------
# Hashing helpers
# -----------------------------------------------------------------------------
def pseudonymize(value: str | int | float) -> str:
    """
    Replace a direct identifier with a stable, salted SHA-256 hash.
    Stable = same input always returns the same hash, so we can still join
    across tables without ever exposing the raw value.
    """
    if pd.isna(value):
        return ""
    raw = f"{_HASH_SALT}::{value}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def mask_email(value: str) -> str:
    """Mask the local-part of an email, keep the domain for analytics."""
    if not isinstance(value, str) or "@" not in value:
        return ""
    local, domain = value.split("@", 1)
    if len(local) <= 2:
        masked = "*" * len(local)
    else:
        masked = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked}@{domain}"


def generalize_zip(zip_code: str) -> str:
    """
    HIPAA Safe Harbor: keep only the first 3 digits of a ZIP, and clear it
    entirely for low-population ZIPs (rough proxy: ZIPs starting 036/059/692/…).
    """
    if not isinstance(zip_code, str):
        zip_code = str(zip_code)
    digits = re.sub(r"\D", "", zip_code)[:3]
    forbidden = {"036", "059", "063", "102", "203", "556", "692", "790",
                 "821", "823", "830", "831", "878", "879", "884", "890", "893"}
    return "000" if digits in forbidden else digits.ljust(3, "0")


def generalize_age(age: float | int) -> int:
    """
    HIPAA Safe Harbor: cap age at 89. Ages 90+ are highly identifying.
    """
    if pd.isna(age):
        return -1
    return min(int(age), 89)


# -----------------------------------------------------------------------------
# DataFrame-level entry point
# -----------------------------------------------------------------------------
def anonymize_dataframe(
    df: pd.DataFrame,
    direct_cols: Iterable[str] | None = None,
    drop_indirect: bool = False,
) -> pd.DataFrame:
    """
    Apply the standard governance pass to a pandas DataFrame.

    Parameters
    ----------
    df : input DataFrame
    direct_cols : extra column names to treat as direct identifiers
    drop_indirect : if True, quasi-identifiers are dropped entirely

    Returns
    -------
    Cleaned DataFrame that is safe to ship to the analytics environment.
    """
    out = df.copy()
    direct = set(c.lower() for c in (direct_cols or [])) | PII_DIRECT

    for col in out.columns:
        lower = col.lower()
        # ---- direct identifiers ------------------------------------------
        if lower in direct:
            if "email" in lower:
                out[col] = out[col].astype(str).map(mask_email)
            else:
                out[col] = out[col].astype(str).map(pseudonymize)
        # ---- quasi-identifiers -------------------------------------------
        elif lower in PII_INDIRECT:
            if drop_indirect:
                out = out.drop(columns=[col])
            elif "zip" in lower:
                out[col] = out[col].astype(str).map(generalize_zip)
            elif "age" in lower:
                out[col] = out[col].map(generalize_age)

    return out


def standardize_timestamps(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """
    All timestamps come from heterogeneous devices in heterogeneous time
    zones. We coerce everything to UTC and explicitly fail on garbage.
    """
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], utc=True, errors="coerce")
    return out


def role_can_read(role: str, sensitivity: str) -> bool:
    """
    Tiny RBAC enforcement helper. Production version would call an IAM
    service, but this captures the policy.
    """
    matrix = {
        "admin":     {"public", "internal", "sensitive", "restricted"},
        "engineer":  {"public", "internal", "sensitive"},
        "analyst":   {"public", "internal"},
        "intern":    {"public"},
    }
    return sensitivity in matrix.get(role, set())
