"""
IDX-BEI Python SDK & Pipeline Suite.

Structured toolkit for scraping, processing, and analyzing Indonesia Stock Exchange (IDX) data.
"""

from idx.core.client import IDXClient
from idx.pipelines.daily import ingest_daily
from idx.pipelines.parquet import export_all as export_all_parquet
from idx.pipelines.parquet import (
    export_broker_timeseries,
    export_corporate_actions,
    export_financial_ratios,
    export_index_timeseries,
    export_stock_timeseries,
)
from idx.scrapers.company import fetch_company_detail, fetch_company_profiles
from idx.scrapers.corporate import fetch_corporate_actions
from idx.scrapers.financial import fetch_financial_ratios
from idx.scrapers.historical import (
    backfill_broker_summary,
    backfill_index_summary,
    backfill_stock_summary,
)
from idx.scrapers.members import fetch_broker_search
from idx.scrapers.news import fetch_all_announcements, fetch_news_search
from idx.scrapers.trading import fetch_broker_summary, fetch_index_summary, fetch_stock_summary

__all__ = [
    # Core
    "IDXClient",
    # Snapshot Scrapers
    "fetch_company_profiles",
    "fetch_company_detail",
    "fetch_financial_ratios",
    "fetch_stock_summary",
    "fetch_broker_summary",
    "fetch_index_summary",
    "fetch_corporate_actions",
    "fetch_broker_search",
    "fetch_news_search",
    "fetch_all_announcements",
    # Historical Backfill
    "backfill_stock_summary",
    "backfill_broker_summary",
    "backfill_index_summary",
    # Parquet Export
    "export_stock_timeseries",
    "export_broker_timeseries",
    "export_index_timeseries",
    "export_financial_ratios",
    "export_corporate_actions",
    "export_all_parquet",
    # Daily Pipeline
    "ingest_daily",
]
