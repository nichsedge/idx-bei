"use strict";

import { fetchData } from "../../../../../fetchUtil.js";

/**
 * Retrieves new listing information from IDX.
 * @returns {Promise<string>} - A JSON string of the new listing data.
 * @throws {Error} If the request fails.
 */
export async function getNewListing() {
  const url = "https://www.idx.co.id/primary/list/en/market-data/statistical-reports/new-listing-information/?lang=en&start=0&length=9999&year=2024";
  const referrer = "https://www.idx.co.id/en/market-data/statistical-reports/new-listing-information/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const res = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(res, null, 2);
  } catch (error) {
    console.error("Error fetching new listing data:", error.message);
    throw new Error(`Failed to fetch new listing data: ${error.message}`);
  }
}
