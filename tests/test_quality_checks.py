"""
Unit tests for the quality engine.

Run with:
    pytest tests/ -v
"""
import numpy as np
import pandas as pd
import pytest

from src.governance.anonymizer import (
    anonymize_dataframe,
    generalize_age,
    generalize_zip,
    mask_email,
    pseudonymize,
    role_can_read,
)
from src.quality_engine.logic_rules import (
    check_completeness,
    check_logical_consistency,
    check_range,
    check_uniqueness,
    run_full_check_suite,
)
from src.quality_engine.stats_models import (
    detect_outliers_iqr,
    detect_outliers_modified_zscore,
    detect_outliers_zscore,
    flag_group_outliers,
    impute_simple,
)


# =============================================================================
# Governance
# =============================================================================
class TestAnonymizer:

    def test_pseudonymize_is_deterministic(self):
        assert pseudonymize("alice") == pseudonymize("alice")
        assert pseudonymize("alice") != pseudonymize("bob")

    def test_pseudonymize_length(self):
        assert len(pseudonymize("any_value")) == 16

    def test_mask_email_keeps_domain(self):
        masked = mask_email("alice.smith@example.com")
        assert masked.endswith("@example.com")
        assert "alice" not in masked

    def test_mask_email_short_local_part(self):
        assert mask_email("ab@x.com").startswith("**")

    def test_generalize_zip_truncates_to_three(self):
        assert generalize_zip("12345") == "123"

    def test_generalize_zip_blocks_low_population(self):
        assert generalize_zip("03601") == "000"

    def test_generalize_age_caps_at_89(self):
        assert generalize_age(95) == 89
        assert generalize_age(45) == 45
        assert generalize_age(np.nan) == -1

    def test_anonymize_dataframe_masks_pii(self):
        df = pd.DataFrame({
            "email":   ["alice@x.com", "bob@y.com"],
            "age":     [25, 100],
            "steps":   [5000, 8000],
        })
        out = anonymize_dataframe(df)
        assert "alice" not in out["email"].iloc[0]
        assert out["age"].iloc[1] == 89                # capped
        assert out["steps"].tolist() == [5000, 8000]   # untouched

    def test_role_rbac(self):
        assert role_can_read("analyst", "internal")
        assert not role_can_read("analyst", "sensitive")
        assert role_can_read("admin", "restricted")


# =============================================================================
# Logic rules
# =============================================================================
class TestLogicRules:

    @pytest.fixture
    def cardio_df(self):
        return pd.DataFrame({
            "seqn":          [1, 2, 3, 4, 5],
            "systolic_bp":   [120, 240, 999, 110, 115],
            "diastolic_bp":  [80, 130, 70, 70, 75],
            "pulse_rate_bpm":[70, 80, 25, 65, np.nan],
        })

    def test_range_flags_out_of_bound(self, cardio_df):
        r = check_range(cardio_df, "systolic_bp")
        assert r.failed_rows == 1                          # only 999 fails
        assert r.pass_rate == 0.8

    def test_range_flags_pulse_too_low(self, cardio_df):
        r = check_range(cardio_df, "pulse_rate_bpm")
        assert r.failed_rows == 1                          # the 25 bpm

    def test_completeness_flags_nulls(self, cardio_df):
        r = check_completeness(cardio_df, ["pulse_rate_bpm"])
        assert r.failed_rows == 1

    def test_uniqueness_flags_duplicates(self):
        df = pd.DataFrame({"id": [1, 2, 2, 3, 3, 3]})
        r = check_uniqueness(df, ["id"])
        assert r.failed_rows == 5                          # all dup rows

    def test_logical_consistency_systolic_under_diastolic(self):
        df = pd.DataFrame({"systolic_bp": [120, 60], "diastolic_bp": [80, 80]})
        r = check_logical_consistency(df)
        assert r.failed_rows == 1

    def test_run_full_check_suite_returns_dataframe(self, cardio_df):
        result = run_full_check_suite(
            cardio_df, table_name="cardio",
            numeric_columns=["systolic_bp", "diastolic_bp"],
            required_columns=["pulse_rate_bpm"],
            unique_keys=["seqn"],
        )
        assert isinstance(result, pd.DataFrame)
        assert "pass_rate" in result.columns
        assert len(result) > 0


# =============================================================================
# Statistical models
# =============================================================================
class TestStatsModels:

    @pytest.fixture
    def skewed_data(self):
        rng = np.random.default_rng(42)
        clean = rng.normal(120, 10, 1000)
        outliers = np.array([300, 350, 20, 25, 400])
        return pd.Series(np.concatenate([clean, outliers]), name="systolic_bp")

    def test_zscore_detects_outliers(self, skewed_data):
        r = detect_outliers_zscore(skewed_data, threshold=3.0)
        assert r.n_outliers >= 4

    def test_iqr_detects_outliers(self, skewed_data):
        r = detect_outliers_iqr(skewed_data)
        assert r.n_outliers >= 4

    def test_modified_zscore_works(self, skewed_data):
        r = detect_outliers_modified_zscore(skewed_data)
        assert r.n_outliers >= 4

    def test_group_outliers(self):
        df = pd.DataFrame({
            "bp":     np.concatenate([
                np.random.normal(110, 5, 100),
                np.random.normal(140, 5, 100),
                [9999, 8888],
            ]),
            "group":  ["A"] * 100 + ["B"] * 100 + ["A", "B"],
        })
        outliers = flag_group_outliers(df, "bp", "group")
        assert len(outliers) >= 2

    def test_simple_imputation_removes_nans(self):
        df = pd.DataFrame({"x": [1.0, 2.0, np.nan, 4.0, 5.0]})
        out = impute_simple(df, ["x"], strategy="median")
        assert not out["x"].isna().any()
        assert out["x"].iloc[2] == pytest.approx(3.0)
