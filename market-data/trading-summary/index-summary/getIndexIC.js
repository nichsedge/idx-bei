"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the Index IC data from IDX.
 * @returns {Promise<string>} - A JSON string of the Index IC data.
 * @throws {Error} If the request fails.
 */
export async function getIndexIC() {
  const baseUrl = "https://www.idx.co.id/primary/StockData/GetIndexIC";
  const queryParams = new URLSearchParams({}).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/trading-summary/index-summary/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching Index IC data:", error.message);
    throw new Error(`Failed to fetch Index IC data: ${error.message}`);
  }
}
