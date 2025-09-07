"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the broker summary for a specified date from IDX.
 * @param {string} [date=''] - The date for which to retrieve the broker summary (format: YYYYMMDD).
 * @returns {Promise<string>} - A JSON string of the broker summary data.
 * @throws {Error} If the request fails or invalid parameter is provided.
 */
export async function getBrokerSummary(date = '') {
  // Input validation
  if (date && !/^\d{8}$/.test(date)) {
    throw new Error('date must be in YYYYMMDD format if provided');
  }

  const baseUrl = "https://www.idx.co.id/primary/TradingSummary/GetBrokerSummary";
  const queryParams = new URLSearchParams({
    length: 9999,
    start: 0,
  date
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/trading-summary/broker-summary/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching broker summary:", error.message);
    throw new Error(`Failed to fetch broker summary: ${error.message}`);
  }
}
