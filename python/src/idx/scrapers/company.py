"""
Company profiles & company details scraper module.
"""

import os
from idx.core.client import IDXClient
from idx.core.utils import (
    DATA_DIR,
    get_logger,
    validate_schema,
    check_schema_drift,
    check_records_total_consistency,
)

log = get_logger("idx.scrapers.company")

def fetch_company_profiles(client=None, start=0, length=9999):
    """Fetches full list of listed company profiles."""
    if client is None:
        client = IDXClient()
    
    endpoint = "/ListedCompany/GetCompanyProfiles"
    params = {"start": start, "length": length}
    
    log.info("Fetching company profiles list...")
    data = client.get_json(endpoint, params=params)
    
    if data:
        validate_schema(data, "company_profiles_list")
        check_schema_drift("company_profiles_list", data)
        check_records_total_consistency(data, label="company_profiles_list")
        return data
    return None

def fetch_company_detail(kode_emiten, client=None, language="id-id"):
    """Fetches details for a single company ticker."""
    if client is None:
        client = IDXClient()
        
    endpoint = "/ListedCompany/GetCompanyProfilesDetail"
    params = {"KodeEmiten": kode_emiten, "language": language}
    
    return client.get_json(endpoint, params=params)
