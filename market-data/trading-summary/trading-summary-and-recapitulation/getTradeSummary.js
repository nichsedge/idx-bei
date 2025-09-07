"use strict";

import { fetchData } from "../../../../../fetchUtil.js";

/**
 * Retrieves the trade summary from IDX.
 * @returns {Promise<string>} - A JSON string of the trade summary data.
 * @throws {Error} If the request fails.
 */
export async function getTradeSummary() {
  const baseUrl = "https://www.idx.co.id/primary/Home/GetTradeSummary";
  const queryParams = new URLSearchParams({
    lang: 'en'
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/trading-summary/trading-summary-and-recapitulation/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching trade summary:", error.message);
    throw new Error(`Failed to fetch trade summary: ${error.message}`);
  }
}
