"use strict";

import { fetchData } from "../../fetchUtil.js";

/**
 * Retrieves market history data from IDX.
 * @param {Object} [options] - Options for the market history data.
 * @param {string} [options.date=''] - The date for which to retrieve market history data (format: YYYY-MM-DD).
 * @param {number} [options.start=0] - The starting index for pagination.
 * @param {number} [options.length=9999] - The number of records to retrieve.
 * @returns {Promise<string>} - A JSON string of the market history data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getMarketHistory({
  date = '',
  start = 0,
  length = 9999
} = {}) {
  // Input validation
  if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    throw new Error('date must be in YYYY-MM-DD format if provided');
  }
  if (typeof start !== 'number' || typeof length !== 'number') {
    throw new Error('start and length must be numbers');
  }
  if (start < 0 || length < 1) {
    throw new Error('start must be >=0 and length must be positive');
  }

  const baseUrl = "https://www.idx.co.id/primary/DerivativesData/GetMarketHistory";
  const queryParams = new URLSearchParams({ start, length, date }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/derivatives-data/futures/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching market history data:", error.message);
    throw new Error(`Failed to fetch market history data: ${error.message}`);
  }
}
