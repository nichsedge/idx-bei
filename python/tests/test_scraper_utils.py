"""Tests for idx.core.utils – schema validation, drift detection, and anomaly checks."""

import os
import tempfile

import pytest

import idx.core.utils as utils
from idx.core.utils import (
    SCHEMA_SNAPSHOT_FILE,
    SCRAPE_STATS_FILE,
    SchemaDriftError,
    _fingerprint,
    check_count_anomaly,
    check_records_total_consistency,
    check_schema_drift,
    validate_schema,
)

# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------

class TestValidateSchema:
    """Tests for required-key validation against registered schemas."""

    def test_valid_financial_ratio_page(self):
        """A well-formed financial ratio response should produce no warnings."""
        data = {
            "data": [
                {
                    "code": "BBCA",
                    "stockName": "Bank Central Asia",
                    "sector": "Financials",
                    "subSector": "Banks",
                    "assets": 1_000_000,
                    "liabilities": 500_000,
                    "equity": 500_000,
                    "sales": 100_000,
                    "eps": 250,
                    "per": 20.5,
                    "roa": 3.5,
                    "roe": 18.2,
                    "npm": 40.1,
                }
            ]
        }
        warnings = validate_schema(data, "financial_ratio_page")
        assert warnings == []

    def test_missing_top_level_key(self):
        """Removing 'data' should produce a warning about missing keys."""
        data = {"totalRecords": 0}
        warnings = validate_schema(data, "financial_ratio_page")
        assert len(warnings) == 1
        assert "data" in warnings[0]

    def test_missing_data_item_keys(self):
        """If the first record is missing required keys, we get a warning."""
        data = {
            "data": [
                {"code": "BBCA"}  # missing many keys
            ]
        }
        warnings = validate_schema(data, "financial_ratio_page")
        assert len(warnings) == 1
        assert "missing keys" in warnings[0].lower()

    def test_strict_mode_raises(self):
        """strict=True should raise SchemaDriftError on violations."""
        data = {"bad": True}
        with pytest.raises(SchemaDriftError):
            validate_schema(data, "financial_ratio_page", strict=True)

    def test_unknown_schema_passes(self):
        """Unknown schema name should return no warnings (no-op)."""
        warnings = validate_schema({"foo": 1}, "nonexistent_schema")
        assert warnings == []

    def test_valid_company_profiles_list(self):
        """A well-formed company list response should produce no warnings."""
        data = {
            "draw": 1,
            "recordsTotal": 1,
            "recordsFiltered": 1,
            "data": [
                {
                    "KodeEmiten": "BBCA",
                    "NamaEmiten": "Bank Central Asia",
                    "Sektor": "Financials",
                    "SubSektor": "Banks",
                }
            ],
        }
        warnings = validate_schema(data, "company_profiles_list")
        assert warnings == []

    def test_valid_company_detail(self):
        """A well-formed company detail response should pass."""
        data = {
            "ResultCount": 1,
            "Profiles": {"KodeEmiten": "BBCA"},
        }
        warnings = validate_schema(data, "company_detail")
        assert warnings == []


# ---------------------------------------------------------------------------
# _fingerprint
# ---------------------------------------------------------------------------

class TestFingerprint:
    """Tests for the structural fingerprinting helper."""

    def test_simple_dict(self):
        fp = _fingerprint({"a": 1, "b": "hello"})
        assert fp == {"a": "int", "b": "str"}

    def test_nested_list_takes_first(self):
        fp = _fingerprint({"data": [{"x": 1}, {"x": 2, "y": 3}]})
        # Only the first item's shape matters
        assert fp == {"data": [{"x": "int"}]}

    def test_empty_list(self):
        fp = _fingerprint({"data": []})
        assert fp == {"data": ["empty"]}


# ---------------------------------------------------------------------------
# check_schema_drift
# ---------------------------------------------------------------------------

class TestCheckSchemaDrift:
    """Tests for snapshot-based structural drift detection."""

    def setup_method(self):
        """Use a temp file for snapshot storage."""
        self._orig = SCHEMA_SNAPSHOT_FILE
        self._tmpdir = tempfile.mkdtemp()
        tmp_snap = os.path.join(self._tmpdir, "snap.json")
        utils.SCHEMA_SNAPSHOT_FILE = tmp_snap

    def teardown_method(self):
        utils.SCHEMA_SNAPSHOT_FILE = self._orig

    def test_first_call_saves_snapshot(self):
        result = check_schema_drift("test_endpoint", {"a": 1, "b": [{"x": 1}]})
        assert result is False  # no drift on first save
        assert os.path.exists(utils.SCHEMA_SNAPSHOT_FILE)

    def test_identical_call_no_drift(self):
        data = {"a": 1, "b": [{"x": 1}]}
        check_schema_drift("test_endpoint", data)
        result = check_schema_drift("test_endpoint", data)
        assert result is False

    def test_changed_structure_triggers_drift(self):
        check_schema_drift("test_endpoint", {"a": 1})
        result = check_schema_drift("test_endpoint", {"a": 1, "new_field": "hello"})
        assert result is True


# ---------------------------------------------------------------------------
# check_count_anomaly
# ---------------------------------------------------------------------------

class TestCheckCountAnomaly:
    """Tests for record-count anomaly detection."""

    def setup_method(self):
        self._orig = SCRAPE_STATS_FILE
        self._tmpdir = tempfile.mkdtemp()
        tmp_stats = os.path.join(self._tmpdir, "stats.json")
        utils.SCRAPE_STATS_FILE = tmp_stats

    def teardown_method(self):
        utils.SCRAPE_STATS_FILE = self._orig

    def test_first_run_no_anomaly(self):
        result = check_count_anomaly("test_ep", 100)
        assert result is False

    def test_stable_count_no_anomaly(self):
        check_count_anomaly("test_ep", 100)
        result = check_count_anomaly("test_ep", 105)  # +5% < 15%
        assert result is False

    def test_large_drop_triggers_anomaly(self):
        check_count_anomaly("test_ep", 1000)
        result = check_count_anomaly("test_ep", 500)  # -50%
        assert result is True

    def test_large_increase_triggers_anomaly(self):
        check_count_anomaly("test_ep", 100)
        result = check_count_anomaly("test_ep", 200)  # +100%
        assert result is True


# ---------------------------------------------------------------------------
# check_records_total_consistency
# ---------------------------------------------------------------------------

class TestRecordsTotalConsistency:

    def test_matching_counts(self):
        data = {"recordsTotal": 3, "data": [1, 2, 3]}
        assert check_records_total_consistency(data, "test") is True

    def test_mismatched_counts(self):
        data = {"recordsTotal": 10, "data": [1, 2, 3]}
        assert check_records_total_consistency(data, "test") is False

    def test_no_records_total_passes(self):
        """If recordsTotal is absent, the check should pass (nothing to compare)."""
        data = {"data": [1, 2]}
        assert check_records_total_consistency(data, "test") is True
