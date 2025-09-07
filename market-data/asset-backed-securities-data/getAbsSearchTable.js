"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves ABS search table data from IDX with optional filters.
 * @param {string} [bondId=''] - The bond ID to filter the search results.
 * @param {string} [yearMatured=''] - The year of maturity to filter the search results.
 * @returns {Promise<string>} - A JSON string of the ABS search table data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getAbsSearchTable(bondId = '', yearMatured = '') {
  // Input validation
  if (typeof bondId !== 'string' || typeof yearMatured !== 'string') {
    throw new Error('bondId and yearMatured must be strings');
  }

  const baseUrl = "https://www.idx.co.id/primary/MarketData/GetAbsSearchTable";
  const queryParams = new URLSearchParams({
    draw: 1,
    start: 0,
    length: 9999,
    bondId,
    yearMatured
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/asset-backed-securities-data/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response.data || response['data'], null, 2);
  } catch (error) {
    console.error("Error fetching ABS search table data:", error.message);
    throw new Error(`Failed to fetch ABS search table data: ${error.message}`);
  }
}
