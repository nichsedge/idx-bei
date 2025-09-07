"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the structured warrant issuers dropdown list from IDX.
 * @returns {Promise<string>} - A JSON string of the issuer dropdown list.
 * @throws {Error} If the request fails.
 */
export async function getIssuerDDL() {
  const url = "https://www.idx.co.id/primary/StructuredWarrant/GetIssuerDDL";
  const referrer = "https://www.idx.co.id/en/market-data/structured-warrant-sw/structured-warrant-information/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching issuer dropdown list:", error.message);
    throw new Error(`Failed to fetch issuer dropdown list: ${error.message}`);
  }
}
