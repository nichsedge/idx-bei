"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the index summary for a specified date from IDX.
 * @param {string} [date=''] - The date for which to retrieve the index summary (format: YYYYMMDD). Defaults to an empty string.
 * @returns {Promise<string>} - A JSON string of the index summary data.
 * @throws {Error} If the request fails or invalid parameter is provided.
 */
export async function getIndexSummary(date = '') {
  // Input validation
  if (date && !/^\d{8}$/.test(date)) {
    throw new Error('date must be in YYYYMMDD format if provided');
  }

  const baseUrl = "https://www.idx.co.id/primary/TradingSummary/GetIndexSummary";
  const queryParams = new URLSearchParams({
    date,
    length: 9999,
    start: 0
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/trading-summary/index-summary/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching index summary:", error.message);
    throw new Error(`Failed to fetch index summary: ${error.message}`);
  }
}
