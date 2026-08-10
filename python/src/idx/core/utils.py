"""
Shared utilities for IDX scrapers: Schema Validation, Drift Detection, Anomaly Tracking, and Archiving.
"""

import os
import json
import time
import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

def get_logger(name):
    """Returns a logger configured with a consistent format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

_log = get_logger("idx.core.utils")

# Absolute path resolving to repository's data/ directory
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../data"))
SCHEMA_SNAPSHOT_FILE = os.path.join(DATA_DIR, ".schema_snapshots.json")
SCRAPE_STATS_FILE = os.path.join(DATA_DIR, ".scrape_stats.json")
RAW_ARCHIVE_DIR = os.path.join(DATA_DIR, ".raw_archive")

def ensure_data_dir():
    """Ensures the data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)

def load_json(file_path, default=None):
    """Loads JSON data from a file or returns default."""
    if default is None:
        default = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return json.loads(content) if content else default
        except (json.JSONDecodeError, IOError) as exc:
            _log.warning("Error loading %s – using default. %s", file_path, exc)
            return default
    return default

def save_json(file_path, data):
    """Saves data to a JSON file atomically."""
    ensure_data_dir()
    tmp_path = file_path + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, file_path)
        _log.info("Saved %s", os.path.basename(file_path))
    except IOError as exc:
        _log.error("Error saving %s: %s", file_path, exc)

SCHEMAS = {
    "company_profiles_list": {
        "required_keys": {"draw", "recordsTotal", "recordsFiltered", "data"},
        "data_item_keys": {"KodeEmiten", "NamaEmiten", "Sektor", "SubSektor"},
    },
    "company_detail": {
        "required_keys": {"ResultCount", "Profiles"},
    },
    "financial_ratio_page": {
        "required_keys": {"data"},
        "data_item_keys": {
            "code", "stockName", "sector", "subSector",
            "assets", "liabilities", "equity", "sales",
            "eps", "per", "roa", "roe", "npm",
        },
    },
    "broker_search": {
        "required_keys": {"draw", "recordsTotal", "recordsFiltered", "data"},
        "data_item_keys": {"Code", "Name", "License"},
    },
    "stock_summary": {
        "required_keys": {"draw", "recordsTotal", "recordsFiltered", "data"},
        "data_item_keys": {
            "StockCode", "StockName", "OpenPrice", "High", "Low", "Close",
            "Volume", "Value", "Frequency", "ForeignBuy", "ForeignSell",
        },
    },
    "broker_summary": {
        "required_keys": {"draw", "recordsTotal", "recordsFiltered", "data"},
        "data_item_keys": {"IDFirm", "FirmName", "Volume", "Value", "Frequency"},
    },
    "index_summary": {
        "required_keys": {"draw", "recordsTotal", "recordsFiltered", "data"},
        "data_item_keys": {"IndexCode", "Close", "Volume", "Value", "Frequency", "MarketCapital"},
    },
    "news_search": {
        "required_keys": {"Items", "ItemCount", "PageSize", "PageNumber"},
    },
    "corporate_action": {
        "required_keys": {"draw", "recordsTotal", "recordsFiltered", "data"},
        "data_item_keys": {"KodeEmiten", "JenisTindakan", "TanggalPencatatan"},
    },
    "all_announcement": {
        "required_keys": {"Items", "ItemCount", "PageSize", "PageNumber"},
    },
}

class SchemaDriftError(Exception):
    """Raised when an API response violates expected schema."""

def validate_schema(data, schema_name, *, strict=False):
    """Checks data against declared SCHEMAS."""
    schema = SCHEMAS.get(schema_name)
    if schema is None:
        return []

    warnings = []
    required = schema.get("required_keys", set())
    missing_top = required - set(data.keys())
    if missing_top:
        warnings.append(f"Missing top-level keys: {missing_top}")

    expected_item_keys = schema.get("data_item_keys")
    if expected_item_keys and isinstance(data.get("data"), list) and data["data"]:
        first_item = data["data"][0]
        if isinstance(first_item, dict):
            missing_item = expected_item_keys - set(first_item.keys())
            if missing_item:
                warnings.append(f"First data record missing keys: {missing_item}")

    if warnings:
        for w in warnings:
            _log.warning("[SCHEMA DRIFT] %s – %s", schema_name, w)
        if strict:
            raise SchemaDriftError(f"Schema drift for '{schema_name}': {'; '.join(warnings)}")

    return warnings

def _fingerprint(obj, *, depth=0, max_depth=3):
    """Recursively extracts type skeleton."""
    if depth > max_depth:
        return type(obj).__name__

    if isinstance(obj, dict):
        return {k: _fingerprint(v, depth=depth + 1, max_depth=max_depth)
                for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        if obj:
            return [_fingerprint(obj[0], depth=depth + 1, max_depth=max_depth)]
        return ["empty"]
    return type(obj).__name__

def check_schema_drift(endpoint_name, data):
    """Compares response fingerprint against stored snapshot."""
    ensure_data_dir()
    snapshots = load_json(SCHEMA_SNAPSHOT_FILE, {})
    current = _fingerprint(data)

    if endpoint_name not in snapshots:
        snapshots[endpoint_name] = current
        save_json(SCHEMA_SNAPSHOT_FILE, snapshots)
        _log.info("[SCHEMA] Saved initial snapshot for '%s'", endpoint_name)
        return False

    stored = snapshots[endpoint_name]
    if stored != current:
        _log.warning("[SCHEMA DRIFT DETECTED] '%s'", endpoint_name)
        snapshots[endpoint_name] = current
        save_json(SCHEMA_SNAPSHOT_FILE, snapshots)
        return True

    return False

def check_count_anomaly(endpoint_name, current_count, *, threshold_pct=0.15):
    """Warns if current_count deviates from stored baseline by > threshold_pct."""
    ensure_data_dir()
    history = load_json(SCRAPE_STATS_FILE, {})
    prev_entry = history.get(endpoint_name, {})
    prev_count = prev_entry.get("last_count")
    anomaly = False

    if prev_count is not None and prev_count > 0:
        pct_change = (current_count - prev_count) / prev_count
        if abs(pct_change) > threshold_pct:
            _log.warning(
                "[COUNT ANOMALY] '%s': was %d, now %d (%+.1f%% change)",
                endpoint_name, prev_count, current_count, pct_change * 100,
            )
            anomaly = True
        else:
            _log.info(
                "[COUNT OK] '%s': %d records (%+.1f%% vs previous %d)",
                endpoint_name, current_count, pct_change * 100, prev_count,
            )
    else:
        _log.info("[COUNT] '%s': baseline set to %d", endpoint_name, current_count)

    history[endpoint_name] = {
        "last_count": current_count,
        "last_run": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    save_json(SCRAPE_STATS_FILE, history)
    return anomaly

def archive_raw_response(endpoint_name, raw_text):
    """Persists raw HTTP text for post-mortem debugging."""
    os.makedirs(RAW_ARCHIVE_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RAW_ARCHIVE_DIR, f"{endpoint_name}_{ts}.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(raw_text)
        _log.info("[ARCHIVE] Saved raw response → %s", os.path.basename(path))
    except IOError as exc:
        _log.error("[ARCHIVE] Failed to save: %s", exc)
    return path

def check_records_total_consistency(data, label=""):
    """Checks recordsTotal against len(data)."""
    records_total = data.get("recordsTotal")
    actual = len(data.get("data", []))
    if records_total is not None and records_total != actual:
        _log.warning("[RECORDS MISMATCH] %s: recordsTotal=%d but len(data)=%d", label, records_total, actual)
        return False
    return True
