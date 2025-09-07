"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the structured warrant types from IDX.
 * @returns {Promise<string>} - A JSON string of the structured warrant types.
 * @throws {Error} If the request fails.
 */
export async function getSwTypes() {
  const url = "https://www.idx.co.id/primary/StructuredWarrant/GetSwTypes";
  const referrer = "https://www.idx.co.id/en/market-data/structured-warrant-sw/structured-warrant-information/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching structured warrant types:", error.message);
    throw new Error(`Failed to fetch structured warrant types: ${error.message}`);
  }
}
