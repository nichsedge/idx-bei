"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the ETP market snapshot from IDX for a specified date.
 * @param {string} [date='20240731'] - The date for which to retrieve the ETP market snapshot (format: YYYYMMDD).
 * @returns {Promise<string>} - A JSON string of the ETP market snapshot data.
 * @throws {Error} If the request fails or invalid parameter is provided.
 */
export async function getETPMarketSnapshot(date = '20240731') {
  // Input validation
  if (date && !/^\d{8}$/.test(date)) {
    throw new Error('date must be in YYYYMMDD format if provided');
  }

  const baseUrl = "https://www.idx.co.id/primary/BondSukuk/GetETPMarketSnapshot";
  const queryParams = new URLSearchParams({
    date,
    start: 0,
    length: 10,
    keyword: '',
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
    console.error("Error fetching ETP market snapshot:", error.message);
    throw new Error(`Failed to fetch ETP market snapshot: ${error.message}`);
  }
}
