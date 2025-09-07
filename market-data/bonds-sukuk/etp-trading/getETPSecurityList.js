"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves the list of ETP securities from IDX based on the given ticker.
 * @param {string} [ticker=''] - The ticker symbol to filter ETP securities. If empty, retrieves all securities.
 * @returns {Promise<string>} - A JSON string of the ETP securities list.
 * @throws {Error} If the request fails or invalid parameter is provided.
 */
export async function getETPSecurityList(ticker = '') {
  // Input validation
  if (typeof ticker !== 'string') {
    throw new Error('ticker must be a string');
  }

  const baseUrl = "https://www.idx.co.id/primary/BondSukuk/GetETPSecurityList";
  const queryParams = new URLSearchParams({
    ticker,
    length: 10,
    start: 0,
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
    console.error("Error fetching ETP security list:", error.message);
    throw new Error(`Failed to fetch ETP security list: ${error.message}`);
  }
}
