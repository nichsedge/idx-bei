"use strict";

import { fetchData } from "../../../../../fetchUtil.js";

/**
 * Retrieves performance summary for LQ45 companies from IDX.
 * @returns {Promise<string>} - A JSON string of the LQ45 company performance summary data.
 * @throws {Error} If the request fails.
 */
export async function getPerfSumLq45Company() {
  const url = "https://www.idx.co.id/primary/StockData/GetPerfSumLq45Company?length=10&start=0&year=2024&lang=en";
  const referrer = "https://www.idx.co.id/en/market-data/statistical-reports/company-fact-sheet-lq45";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const res = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(res, null, 2);
  } catch (error) {
    console.error("Error fetching LQ45 company performance summary:", error.message);
    throw new Error(`Failed to fetch LQ45 company performance summary: ${error.message}`);
  }
}
