"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the index group prevalues from IDX.
 * @returns {Promise<string>} - A JSON string of the index group prevalues data.
 * @throws {Error} If the request fails.
 */
export async function getIndexGroupPrevalues() {
  const baseUrl = "https://www.idx.co.id/primary/StockData/GetIndexGroupPrevalues";
  const queryParams = new URLSearchParams({}).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/stocks-data/stock-index/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching index group prevalues:", error.message);
    throw new Error(`Failed to fetch index group prevalues: ${error.message}`);
  }
}
