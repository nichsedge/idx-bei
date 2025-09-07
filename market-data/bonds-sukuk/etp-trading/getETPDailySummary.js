"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the ETP daily summary from IDX for a specified date.
 * @param {string} [date='20240731'] - The date for which to retrieve the ETP daily summary (format: YYYYMMDD).
 * @returns {Promise<string>} - A JSON string of the ETP daily summary data.
 * @throws {Error} If the request fails or invalid parameter is provided.
 */
export async function getETPDailySummary(date = '20240731') {
  // Input validation
  if (date && !/^\d{8}$/.test(date)) {
    throw new Error('date must be in YYYYMMDD format if provided');
  }

  const baseUrl = "https://www.idx.co.id/primary/BondSukuk/GetETPDailySummary";
  const queryParams = new URLSearchParams({
    start: 0,
    length: 10,
    keyword: '',
    date,
    _: Date.now() // Use current timestamp to avoid caching issues
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/etp-trading/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching ETP daily summary:", error.message);
    throw new Error(`Failed to fetch ETP daily summary: ${error.message}`);
  }
}
