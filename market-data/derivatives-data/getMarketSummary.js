"use strict";

import { fetchData } from "../../fetchUtil.js";

/**
 * Retrieves market summary data from IDX.
 * @returns {Promise<string>} - A JSON string of the market summary data.
 * @throws {Error} If the request fails.
 */
export async function getMarketSummary() {
  const url = "https://www.idx.co.id/primary/DerivativesData/GetMarketSummary";
  const referrer = "https://www.idx.co.id/en/market-data/derivatives-data/futures/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching market summary data:", error.message);
    throw new Error(`Failed to fetch market summary data: ${error.message}`);
  }
}
